import threading
import time

from shaggy.proto.command_pb2 import Command

from shaggy.blocks import channel_levels, gstreamer_src, heartbeat, noise_floor, short_time_fft
from shaggy.transport import library

import zmq

class BlockHub:

    def __init__(self, address, context: zmq.Context = None):
        self.context = context or zmq.Context.instance()
        self.address = address
        self.command_pairs = {}
        self.block_threads = {}

    def start_heartbeat(self, thread_id):
        instance = heartbeat.Heartbeat(thread_id, self.context)
        return self._start_block(instance, library.BlockName.Heartbeat.value, thread_id)

    def start_gstreamer_src(self, cfg, thread_id):
        instance = gstreamer_src.GStreamerSrc.from_cfg(cfg, thread_id, self.address, self.context)
        return self._start_block(instance, library.BlockName.GStreamerSrc.value, thread_id)

    def start_channel_levels(self, gstreamer_src_id, cfg, thread_id):
        instance = channel_levels.ChannelLevels(cfg, gstreamer_src_id, thread_id, self.context)
        return self._start_block(instance, library.BlockName.ChannelLevels.value, thread_id)

    def start_short_time_fft(self, gstreamer_src_id, cfg, thread_id):
        instance = short_time_fft.ShortTimeFFT(cfg, gstreamer_src_id, thread_id, self.context)
        return self._start_block(instance, library.BlockName.ShortTimeFFT.value, thread_id)

    def start_noise_floor(self, short_time_fft_id, cfg, thread_id):
        instance = noise_floor.NoiseFloor(cfg, short_time_fft_id, thread_id, self.context)
        return self._start_block(instance, library.BlockName.NoiseFloor.value, thread_id)

    def _start_block(self, instance, block_name, thread_id):
        thread_name = library.get_thread_name(block_name, thread_id)
        thread = threading.Thread(target=instance.run)
        self.block_threads[thread_name] = thread

        command = self.context.socket(zmq.PAIR)
        command.connect(library.get_control_socket(thread_id))
        self.command_pairs[thread_name] = command

        self.block_threads[thread_name].start()
        return thread_name

    def passthrough(self, command: Command):
        thread_name = library.get_thread_name(command.block_name, command.thread_id)
        command_pair = self.command_pairs[thread_name]
        msg = command.SerializeToString()
        command_pair.send_string(f"{time.monotonic_ns()}", zmq.SNDMORE)
        command_pair.send(msg)

    def shutdown(self, command: Command):
        thread_name = library.get_thread_name(command.block_name, command.thread_id)
        if thread_name != "":
            command_pairs = {thread_name: self.command_pairs[thread_name]}
            block_threads = {thread_name: self.block_threads[thread_name]}
            del self.command_pairs[thread_name]
            del self.block_threads[thread_name]
        else:
            command_pairs = self.command_pairs
            block_threads = self.block_threads
            self.command_pairs = {
                    library.BlockName.Heartbeat.value:
                    self.command_pairs[library.BlockName.Heartbeat.value]
                    }
            self.block_threads = {
                    library.BlockName.Heartbeat.value:
                    self.block_threads[library.BlockName.Heartbeat.value]
                    }

        for id, command_pair in command_pairs.items():
            thread_info = id.split('-')
            if thread_info[0] == library.BlockName.Heartbeat.value:
                continue
            block_name = '-'.join(thread_info[:-1])
            command = Command()
            command.command = 'shutdown'
            command.block_name = block_name
            command.thread_id = thread_info[-1]
            msg = command.SerializeToString()

            command_pair.send_string(f"{time.monotonic_ns()}", zmq.SNDMORE)
            command_pair.send(msg)

        for id, block_thread in block_threads.items():
            thread_info = id.split('-')
            if thread_info[0] == library.BlockName.Heartbeat.value:
                continue
            #block_thread.join()
