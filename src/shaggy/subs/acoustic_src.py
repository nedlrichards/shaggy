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
import numpy as np
import zmq

from shaggy.proto import codec

class AcousticSrc:
    """Stream audio from interface to local buffer."""

    def __init__(self, rate, num_channels, num_bytes=4) -> Self:
        self.rate = rate
        self.num_channels = num_channels
        self.num_bytes = num_bytes
        self.format = f"S{8*num_bytes}LE"
        self.pipeline = None
        self.recordpipe = None
        self.address = "inproc://acoustic-samples-pair"
        self.frame_number = 0
        self.pub = None

    @classmethod
    def from_cfg(cls, cfg: DictConfig) -> Self:
        return cls(
                rate=cfg['acoustic_src']['sample_rate'],
                num_channels=cfg['acoustic_src']['channels'],
                )
 
    @contextmanager
    def start_audio(self, context: zmq.Context = None) -> None:
        context = context or zmq.Context.instance()
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
        self.pub = context.socket(zmq.PAIR)
        self.pub.bind(self.address)
        self.frame_number = 0
        pipeline.set_state(Gst.State.PLAYING)

        try:
            yield pipeline
        finally:
            self.pub.close(0)
            pipeline.set_state(Gst.State.NULL)

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
        sample_array = np.frombuffer(data, dtype=np.float32)
        sample_array = sample_array.reshape((-1, self.num_channels))
        msg = codec.samples_to_protobuf(sample_array, self.frame_number)

        timestamp_ns = time.monotonic_ns()
        timestamp_bytes = timestamp_ns.to_bytes(8, "little")
        self.pub.send(timestamp_bytes, zmq.SNDMORE)
        self.pub.send_multipart([msg])

        self.frame_number += 1
