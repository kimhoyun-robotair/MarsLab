"""ArduPilot's official UDP JSON physics backend, with frame-count lockstep.

Protocol: libraries/SITL/examples/JSON/readme.md in ArduPilot Copter-4.6.3.
Only complete new PWM frames advance physics. Retransmitted frames receive the
last sensor response without advancing the simulator a second time.
"""

import json
import logging
import socket
import struct

from marslab.flight.frames import ENU_TO_NED, FLU_TO_FRD, convert_quaternion
from marslab.flight.types import ServoCommand

_LOG = logging.getLogger(__name__)
_PACKETS = {18458: struct.Struct("<HHI16H"), 29569: struct.Struct("<HHI32H")}


class ArduPilotJsonBackend:
    lockstep = True

    def __init__(self, config):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self.socket.bind((config.json_bind, config.json_port))
            self.socket.setblocking(False)
        except BaseException:
            self.socket.close()
            raise
        self.reset()
        _LOG.info("Waiting for ArduPilot JSON PWM at %s:%d", config.json_bind, config.json_port)

    def reset(self):
        self.peer = self.frame_count = self.last_response = None
        while True:
            try:
                self.socket.recvfrom(1024)
            except BlockingIOError:
                break

    def poll(self):
        while True:
            try:
                data, peer = self.socket.recvfrom(1024)
            except BlockingIOError:
                return None
            if len(data) < 8:
                continue
            packet = _PACKETS.get(struct.unpack_from("<H", data)[0])
            if packet is None or len(data) != packet.size:
                continue
            _, rate, count, *pwm = packet.unpack(data)
            if rate == 0:
                continue
            if peer == self.peer and count == self.frame_count:
                if self.last_response is not None:
                    self.socket.sendto(self.last_response, peer)
                continue
            if self.peer is None or peer != self.peer or count < self.frame_count:
                _LOG.info("ArduPilot JSON connected from %s; frame rate %d Hz", peer, rate)
                self.last_response = None
            self.peer, self.frame_count = peer, count
            return ServoCommand(tuple(pwm), count, rate)

    def send_state(self, state, range_m=None):
        if self.peer is None:
            return
        payload = {
            "timestamp": float(state.timestamp),
            "imu": {"gyro": (FLU_TO_FRD@state.body_rates).tolist(),
                    "accel_body": (FLU_TO_FRD@state.specific_force).tolist()},
            "position": (ENU_TO_NED@state.position).tolist(),
            "quaternion": convert_quaternion(state.quaternion).tolist(),
            "velocity": (ENU_TO_NED@state.velocity).tolist(),
            # Simulated receiver resting state; operator interlock arrives via
            # MAVLink RC override. It is refreshed by the command adapter.
            "rc": {"rc_1": 1500, "rc_2": 1500, "rc_3": 1000, "rc_4": 1500,
                   "rc_5": 1500, "rc_6": 1000, "rc_7": 1000, "rc_8": 1000},
        }
        if range_m is not None:
            payload["rng_1"] = float(range_m)
        self.last_response = ("\n"+json.dumps(payload, allow_nan=False, separators=(",", ":"))+"\n").encode()
        self.socket.sendto(self.last_response, self.peer)

    def close(self):
        self.socket.close()


class ExternalWrenchBackend:
    """Direct body wrench endpoint for future controller implementations."""
    lockstep = False

    def __init__(self):
        self.reset()

    def reset(self):
        self.command = None

    def poll(self):
        return self.command

    def send_state(self, state, range_m=None):
        pass

    def close(self):
        pass
