import threading

from shaggy.blocks import channel_levels, gstreamer_src, heartbeat, short_time_fft
from shaggy.transport import library

class CommandHandler:

    def __init__(self, address, context: zmq.Context = None):
        self.context = context or zmq.Context.instance()
        self.address = address
        self.handler = CommandHandler(self.context)
        self.command_pairs = {}
        self.block_threads = {}

    def start_heartbeat(self, thread_id):
        instance = heartbeat.Heartbeat(thread_id, self.context)
        return self._start_block(instance, heartbeat.BLOCK_NAME, thread_id)

    def start_gstreamer_src(self, cfg, thread_id):
        instance = gstreamer_src.GStreamerSrc.from_cfg(cfg, thread_id, self.context)
        return self._start_block(instance, gstreamer_src.BLOCK_NAME, thread_id)

    def start_channel_levels(self, gstreamer_src_id, cfg, thread_id):
        instance = channel_levels.ChannelLevels(cfg, gstreamer_src_id, thread_id, self.context)
        return self._start_block(instance, channel_levels.BLOCK_NAME, thread_id)

    def start_short_time_fft(self, gstreamer_src_id, cfg, thread_id):
        instance = short_time_fft.ShortTimeFFT(cfg, gstreamer_src_id, thread_id, self.context)
        return self._start_block(instance, short_time_fft.BLOCK_NAME, thread_id)

    def _start_block(self, instance, block_name, thread_id):
        thread_name = library.get_thread_name(block_name, thread_id)
        thread = threading.Thread(target=thread_target)
        self.block_threads[thread_name] = thread

        command = self.context.socket(zmq.PAIR)
        command.bind(library.get_control_socket(thread_id))
        self.command_pairs[thread_name] = command

        self.block_threads[thread_name].start()
        return thread_name

    def shutdown(self, thread_name=None):
        if thread_name is not None:
            command_pairs = {thread_name: self.command_pairs[thread_name]}
            block_threads = {thread_name: self.block_threads[thread_name]}
        else:
            command_pairs = self.command_pairs
            block_threads = self.block_threads

        for id, pair_socket in command_pairs.items():
            pair_socket.send_string("shutdown", zmq.SNDMORE)
            pair_socket.send_string(f"{time.monotonic_ns()}", zmq.SNDMORE)
            pair_socket.send_string("")
            del self.command_pairs[id]

        for id, block_thread in block_threads.items():
            block_thread.join()
            del self.block_thread[id]
