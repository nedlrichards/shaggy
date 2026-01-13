"""Publish audio, options for recording and video."""

from __future__ import annotations

import gi
gi.require_version("Gst", "1.0")
gi.require_version("GstVideo", "1.0")
from gi.repository import Gst  # noqa E402

Gst.init(None)
from contextlib import contextmanager
import time

from omegaconf import DictConfig
import zmq

from shaggy.proto.samples_pb2 import Samples
from shaggy.transport import library

class GStreamerSrc:
    """Stream audio from interface to local buffer."""

    def __init__(self, thread_id: str, rate, num_channels, context, num_bytes=4) -> Self:
        self.thread_id = thread_id
        self.rate = rate
        self.num_channels = num_channels
        self.num_bytes = num_bytes
        self.context = context
        self.format = f"S{8*num_bytes}LE"
        self.pipeline = None
        self.recordpipe = None
        self.frame_number = 0
        self.pub_socket = None
        self.control_socket = None
        self.run_loop = True

    @classmethod
    def from_cfg(cls, cfg: DictConfig, thread_id: str, context: zmq.Context = None) -> Self:
        context = context or zmq.Context.instance()
        return cls(
                thread_id=thread_id,
                rate=cfg['gstreamer_src']['sample_rate'],
                num_channels=cfg['gstreamer_src']['channels'],
                context = context,
                )
 
    @contextmanager
    def start_audio(self) -> None:
        self.pub_socket = self.context.socket(zmq.PUB)
        self.pub_socket.bind(
            library.get_block_socket(library.BlockName.GStreamerSrc.value, self.thread_id)
        )
        self.control_socket = self.context.socket(zmq.PAIR)
        self.control_socket.bind(library.get_control_socket(self.thread_id))

        pipeline = (
                "audiotestsrc"
                f" ! audio/x-raw, rate={self.rate}, channels={self.num_channels}, format={self.format}"
                " ! tee name='audio_source'"
                " ! audioconvert"
                f" ! audio/x-raw, rate={self.rate}, channels={self.num_channels}, format=F32LE"
                " ! appsink name=audio_sink emit-signals=true"
                )
        pipeline = Gst.parse_launch(pipeline)
        assert pipeline
        pipeline.get_by_name("audio_sink").connect("new-sample", self._on_gstreamer_audio_sample)

        self.frame_number = 0
        pipeline.set_state(Gst.State.PLAYING)

        try:
            yield pipeline
        finally:
            pipeline.set_state(Gst.State.NULL)
            self.pub_socket.close(0)
            self.control_socket.close(0)

    def run(self):
        with self.start_audio() as pipeline:
            poller = zmq.Poller()
            poller.register(self.control_socket, zmq.POLLIN)
            self.run_loop = True
            while self.run_loop:
                socks = dict(poller.poll())
                if socks.get(self.control_socket) == zmq.POLLIN:
                    message = self.control_socket.recv()
                    self.parse_control(message)

    def parse_control(self, message):
        self.run_loop = False

    def _on_gstreamer_audio_sample(self, sink):
        """Call on audio sample."""
        sample = sink.emit("pull-sample")
        if sample:
            buffer = sample.get_buffer()
            result, map_info = buffer.map(Gst.MapFlags.READ)
            if result:
                try:
                    self.audio_callback(map_info.data)
                finally:
                    buffer.unmap(map_info)
        return Gst.FlowReturn.OK

    def audio_callback(self, data) -> None:
        """Publish data from acoustic source over 0MQ."""
        self.pub_socket.send_string(library.BlockName.GStreamerSrc.value, zmq.SNDMORE)
        timestamp_ns = time.monotonic_ns()
        self.pub_socket.send_string(f"{time.monotonic_ns()}", zmq.SNDMORE)
        msg = Samples()
        msg.frame_number = self.frame_number
        msg.num_samples_0 = len(data) // (4 * self.num_channels)
        msg.num_channels_1 = self.num_channels
        msg.samples = data
        self.pub_socket.send_multipart([msg.SerializeToString()])

        self.frame_number += 1
