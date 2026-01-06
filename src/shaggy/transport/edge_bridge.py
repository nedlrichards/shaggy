from omegaconf import OmegaConf
import zmq

from shaggy.transport import library
from shaggy.proto.command_pb2 import Command
from shaggy.blocks import heartbeat, gstreamer_src, channel_levels, short_time_fft
from shaggy.transport.command_handler import CommandHandler

class EdgeBridge:
    """ZMQ bridge that runs on the device side and manages block threads."""

    def __init__(self, address, context: zmq.Context = None):
        self.address = address
        self.context = context or zmq.Context.instance()
        self.command_socket = self.context.socket(zmq.PAIR)
        self.frontend = self.context.socket(zmq.SUB)
        self.backend = self.context.socket(zmq.PUB)
        self._running = False
        self.command_handler = CommandHandler(address, self.context)
        self._poller = None

        self.heartbeat_id = None
        self.gstreamer_src_id = None
        self.channel_levels_id = None
        self.short_time_fft_id = None

    def run(self):

        self.command_socket.bind(library.get_command_connection(self.address))
        self.frontend.bind(library.FRONTEND_ADDRESS)
        self.backend.bind(library.get_bridge_connection(self.address))

        self._poller = zmq.Poller()
        self._poller.register(self.command_socket, zmq.POLLIN)
        self._poller.register(self.frontend, zmq.POLLIN)

        self._running = True

        while self._running:
            socks = dict(self._poller.poll())
            if socks.get(self.frontend) == zmq.POLLIN:
                topic, timestamp, msg = self.frontend.recv_multipart()
                if topic.decode() in library.TRANSPORT_TOPICS:
                    self.backend.send_multipart((topic, timestamp, msg))
                    print(f'sending {topic}')
            elif socks.get(self.command_socket) == zmq.POLLIN:
                print('hello from startup')
                timestamp, message = self.command_socket.recv_multipart()
                command = Command()
                command.ParseFromString(message)
                if command.command == 'startup':
                    self.startup(command)
                elif command.command == 'shutdown':
                    self.shutdown(command)
                else:
                    self.command_handler.passthrough(command)
            else:
                for pair_socket in self.command_handler.command_pairs.values():
                    if socks.get(pair_socket) == zmq.POLLIN:
                        timestamp, message = pair_socket.recv_multipart()
                        command = Command()
                        command.ParseFromString(message)
                        print(f"Command from block: {command.command}.")
                        if command.block_name == 'heartbeat' and command.command == 'shutdown':
                            self.shutdown(command)

    def startup(self, command):
        block_socket = library.get_block_socket(command.block_name, command.thread_id)
        cfg = OmegaConf.create(command.config)

        if command.block_name == library.BlockName.Heartbeat.value:
            thread_name = self.command_handler.start_heartbeat(command.thread_id)
            self.heartbeat_id = thread_name
        elif command.block_name == library.BlockName.GStreamerSrc.value:
            thread_name = self.command_handler.start_gstreamer_src(cfg, command.thread_id)
            self.gstreamer_src_id = thread_name
        elif command.block_name == library.BlockName.ChannelLevels.value:
            thread_name = self.command_handler.start_channel_levels(self.gstreamer_src_id, cfg, command.thread_id)
            self.channel_levels_id = thread_name
        elif command.block_name == library.BlockName.ShortTimeFFT.value:
            thread_name = self.command_handler.start_short_time_fft(self.gstreamer_src_id, cfg, command.thread_id)
            self.short_time_fft_id = thread_name

        pair_socket = self.command_handler.command_pairs[thread_name]
        self._poller.register(pair_socket, zmq.POLLIN)

        self.frontend.connect(block_socket)
        self.frontend.setsockopt_string(zmq.SUBSCRIBE, command.block_name)

    def shutdown(self, command):
        self.command_handler.shutdown(command)
        if command.block_name is None:
            # TODO: determine if we ever want to terminate main loop
            self._running = False
