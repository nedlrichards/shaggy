"""Convience serialize and deserialize functions."""

import time

import numpy as np
from shaggy.proto.detections_pb2 import Detections
from shaggy.proto.samples_pb2 import Samples
from torch import Tensor


def samples_to_protobuf(
    audio_samples: np.ndarray,
    frame_number: int,
) -> Samples:
    """Convert a numpy array to a Samples protobuf message.

    audio_samples: (num_samples, num_channels) with float32 dtype.
    """
    num_samples, num_channels = audio_samples.shape

    msg = Samples()
    msg.frame_number = frame_number
    msg.num_samples_0 = num_samples
    msg.num_channels_1 = num_channels
    msg.samples = audio_samples.tobytes()

    return msg.SerializeToString()


def detections_to_proto(
    detections: Tensor,
    angles: Tensor,
    frame_number: int,
    publish_rate: int,
) -> bytes:
    """Convert a detection tensor into a serialized Detections protobuf."""
    num_times, num_beams = map(int, detections.shape)

    msg = Detections()
    msg.frame_number = int(frame_number)
    msg.time_reference_ns = time.time_ns()
    msg.publish_rate = float(publish_rate)
    msg.num_beams = num_beams
    msg.num_times = num_times
    msg.samples.extend(detections.flatten().astype(np.float32).tolist())
    msg.num_angles = angles.shape[0]
    msg.angles.extend(angles.flatten().astype(np.float32).tolist())

    return msg.SerializeToString()


def proto_to_detections(msg):
    """Return a detection array from a protobuff message."""
    pb = Detections()
    pb.ParseFromString(msg)
    detections = np.array(pb.samples).reshape(pb.num_beams, pb.num_times)
    angles = np.array(pb.angles).reshape(pb.num_angles, 2)
    return detections, angles
