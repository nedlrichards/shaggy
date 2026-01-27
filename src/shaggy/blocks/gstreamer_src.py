"""Publish audio, options for recording and video."""

from __future__ import annotations

import gi
gi.require_version("Gst", "1.0")
gi.require_version("GstVideo", "1.0")
from gi.repository import Gst  # noqa E402

Gst.init(None)
from contextlib import contextmanager
import datetime
import json
import pathlib
import os
import time

from omegaconf import OmegaConf, DictConfig
import zmq

from shaggy.proto.command_pb2 import Command
from shaggy.proto.samples_pb2 import Samples
from shaggy.transport import library

class GStreamerSrc:
    """Stream audio from interface to local buffer."""

    def __init__(self, thread_id: str, rate, num_channels, address: str, context: zmq.Context = None, num_bytes=4) -> Self:
        self.thread_id = thread_id
        self.rate = rate
        self.num_channels = num_channels
        self.num_bytes = num_bytes
        self.address = address
        self.context = context
        self.port = 51234
        self.format = f"S{8*num_bytes}LE"
        self.base_folder = pathlib.Path.home() / "data" / "camera"
        self.pipeline = None
        self.record_bin = None
        self.record_pad = None
        self.frame_number = 0
        self.pub_socket = None
        self.control_socket = None
        self.run_loop = True

    @classmethod
    def from_cfg(cls, cfg: DictConfig, thread_id: str, address: str, context: zmq.Context = None) -> Self:
        context = context or zmq.Context.instance()
        return cls(
                thread_id=thread_id,
                rate=cfg['gstreamer_src']['sample_rate'],
                num_channels=cfg['gstreamer_src']['channels'],
                address = address,
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
        udp_address = library.LOCAL_HOST if self.address == library.LOCAL_HOST else library.EXTERNAL_HOST

        pipeline = (
                "    alsasrc device=plughw:S18,0"
                "  ! audioconvert"
                f" ! audio/x-raw, rate={self.rate}, channels={self.num_channels}, format=F32LE"
                "  ! tee name=audio_source"
                " audio_source. ! queue ! appsink name=audio_sink emit-signals=true"
                " v4l2src device=/dev/video0"
                "  ! videoconvert"
                "  ! video/x-raw,framerate=15/1"
                "  ! x264enc speed-preset=veryfast tune=zerolatency"
                "  ! h264parse"
                "  ! rtph264pay"
                f" ! udpsink host={udp_address} port={self.port}"
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

    def _on_gstreamer_audio_sample(self, sink):
        """Call on audio sample."""
        sample = sink.emit("pull-sample")
        if sample:
            buffer = sample.get_buffer()
            result, map_info = buffer.map(Gst.MapFlags.READ)
            if result:
                try:
                    self._audio_callback(map_info.data)
                finally:
                    buffer.unmap(map_info)
        return Gst.FlowReturn.OK

    def _audio_callback(self, data) -> None:
        """Publish data from acoustic source over 0MQ."""
        self.pub_socket.send_string(library.BlockName.GStreamerSrc.value, zmq.SNDMORE)
        timestamp_ns = time.monotonic_ns()
        self.pub_socket.send_string(f"{time.monotonic_ns()}", zmq.SNDMORE)
        msg = Samples()
        msg.frame_number = self.frame_number
        msg.num_samples_0 = len(data) // (self.num_bytes * self.num_channels)
        msg.num_channels_1 = self.num_channels
        msg.samples = data
        self.pub_socket.send_multipart([msg.SerializeToString()])

        self.frame_number += 1

    def start_record(self, pipeline, command) -> None:
        utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
        utc_string = utc_now.strftime("%Y-%m-%dT%H_%M_%S")
        save_folder = self.base_folder / utc_string
        save_folder.mkdir(parents=True, exist_ok=True)

        with open(os.path.join(save_folder, "logging_config.json"), "w") as f:
            json.dump(command.config, f, indent=2)
        with open(os.path.join(save_folder, "audio_timestamp.txt"), "w") as f:
            collect_time = datetime.datetime.now(datetime.timezone.utc)
            f.write(collect_time.strftime("%Y-%m-%dT%H_%M_%S"))
            f.write(str(int(collect_time.timestamp() * 1e9)))
            f.write(f"{time.monotonic()}")

        bin_str = (
                    "queue ! audioconvert ! wavenc"
                    f"! filesink location={save_folder}/audio.wav"
            )
        self.record_bin = Gst.parse_bin_from_description(bin_str, True,)

        tee = pipeline.get_by_name("audio_source")
        record_sink_pad = self.record_bin.get_static_pad("sink")
        self.record_pad = tee.get_request_pad("src_%u")
        pipeline.set_state(Gst.State.PAUSED)
        pipeline.add(self.record_bin)
        self.record_pad.link(record_sink_pad)
        pipeline.set_state(Gst.State.PLAYING)

    def stop_record(self, pipeline):
        """Stop recording."""
        if not self.record_bin:
            return
        pipeline.set_state(Gst.State.PAUSED)

        self.record_pad.unlink(self.record_bin.get_static_pad("sink"))
        pipeline.get_by_name("audio_source").release_request_pad(self.record_pad)
        self.record_pad = None

        self.record_bin.set_state(Gst.State.NULL)
        pipeline.remove(self.record_bin)
        self.record_bin = None

        pipeline.set_state(Gst.State.PLAYING)

    def run(self):
        with self.start_audio() as pipeline:
            poller = zmq.Poller()
            poller.register(self.control_socket, zmq.POLLIN)
            self.run_loop = True
            while self.run_loop:
                socks = dict(poller.poll())
                if socks.get(self.control_socket) == zmq.POLLIN:
                    _, message = self.control_socket.recv_multipart()
                    self.parse_control(message, pipeline)

    def parse_control(self, message, pipeline):
        command = Command()
        command.ParseFromString(message)
        if command.command == 'shutdown':
            self.run_loop = False
        elif command.command == 'start-record':
            self.start_record(pipeline, command)
        elif command.command == 'stop-record':
            self.stop_record(pipeline)
