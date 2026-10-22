"""Reduced collective/cyclic mixer, pitch servos and direct-drive rotor motors.

Grip 2019, X / Fig. 16 motivates the collective-to-motor feedforward path.
Selected linear effectiveness and motor constants are simulation assumptions;
this model omits blade aerodynamics, flapping and structural modes.
"""

import math

import numpy as np

from marslab.config.schema.drone import DroneConfig


class CoaxialActuators:
    def __init__(self, config: DroneConfig, gravity: float):
        self.config = config.actuators
        self.weight = config.mass_kg * abs(gravity)
        self.nominal_speed = self.config.rotor_rpm * math.tau / 60.0
        self.thrust_per_deg = self.weight / (
            self.config.collective_hover_deg - self.config.collective_min_deg
        )
        self.cyclic_effectiveness = np.asarray(self.config.max_torque_nm[:2]) / (
            2.0 * self.config.cyclic_limit_deg
        )
        self.reset()

    def reset(self):
        self.pitch = np.array([self.config.collective_min_deg]*2 + [0.0]*4)
        self.pitch_rate = np.zeros(6)
        self.speed = np.zeros(2)
        self.speed_integral = np.zeros(2)
        self.reference_speed = 0.0

    @property
    def rpm(self):
        return float(self.speed.mean() * 60.0 / math.tau)

    def step(self, force, torque, dt, powered):
        cfg = self.config
        force = np.asarray(force, dtype=float)
        torque = np.clip(np.asarray(torque, dtype=float),
                         -np.asarray(cfg.max_torque_nm), np.asarray(cfg.max_torque_nm))
        thrust = float(np.clip(force[2], 0.0, cfg.max_thrust_ratio*self.weight)) if powered else 0.0
        symmetric = cfg.collective_min_deg + thrust / self.thrust_per_deg
        antisymmetric = torque[2] / (2.0 * cfg.rotor_drag_per_collective_deg) if powered else 0.0
        # Order: upper/lower collective; upper roll/pitch; lower roll/pitch.
        target = np.zeros(6)
        target[:2] = np.clip([symmetric-antisymmetric, symmetric+antisymmetric],
                             cfg.collective_min_deg, cfg.collective_max_deg)
        if powered:
            cyclic = np.clip(torque[:2] / (2.0*self.cyclic_effectiveness),
                              -cfg.cyclic_limit_deg, cfg.cyclic_limit_deg)
            target[2:4] = target[4:6] = cyclic
        return self._advance(target, dt, powered, 1.0 if powered else 0.0)

    def step_servos(self, pwm, dt, rsc_setpoint):
        """Invert AP's H3-120 swashplate geometry into blade-pitch commands.

        SERVO1..3: upper CCW rotor; SERVO4..6: lower CW rotor; SERVO8: RSC.
        AP uses FRD, so a positive AP pitch input has negative FLU Y moment.
        H_SW*_COL_DIR=0, LIN_SVO=0 and servo trims/ranges are generated together
        with this decoder. No position/attitude/rate feedback is implemented here.
        """
        values = np.asarray(pwm, dtype=float)
        throttle = float(np.clip((values[7]-1000.0)/1000.0, 0.0, 1.0))
        angles = np.deg2rad([-60.0, 60.0, 180.0])
        mapping = np.column_stack((0.45*np.cos(angles+math.pi/2),
                                   0.45*np.cos(angles), np.ones(3)))
        swash = (values[:6].reshape(2, 3)-1000.0)/1000.0
        controls = np.linalg.solve(mapping, swash.T).T
        span = self.config.collective_max_deg-self.config.collective_min_deg
        target = np.array([
            self.config.collective_min_deg+span*controls[0, 2],
            self.config.collective_min_deg+span*controls[1, 2],
            controls[0, 0]*self.config.cyclic_limit_deg,
            -controls[0, 1]*self.config.cyclic_limit_deg,
            controls[1, 0]*self.config.cyclic_limit_deg,
            -controls[1, 1]*self.config.cyclic_limit_deg,
        ])
        target[:2] = np.clip(target[:2], self.config.collective_min_deg, self.config.collective_max_deg)
        target[2:] = np.clip(target[2:], -self.config.cyclic_limit_deg, self.config.cyclic_limit_deg)
        return self._advance(target, dt, throttle > 0.0, min(1.0, throttle/rsc_setpoint))

    def _advance(self, target, dt, powered, speed_fraction):
        cfg = self.config
        # Integrate at small intervals even when physics_hz is configured lower.
        substeps = max(1, math.ceil(dt / 0.001))
        step = dt / substeps
        natural = math.tau * cfg.servo_frequency_hz
        motor_torque = np.zeros(2)
        for _ in range(substeps):
            self.pitch_rate += step * (natural**2*(target-self.pitch)
                                      - 2.0*cfg.servo_damping_ratio*natural*self.pitch_rate)
            self.pitch += step*self.pitch_rate
            self.pitch[:2] = np.clip(self.pitch[:2], cfg.collective_min_deg, cfg.collective_max_deg)
            self.pitch[2:] = np.clip(self.pitch[2:], -cfg.cyclic_limit_deg, cfg.cyclic_limit_deg)
            previous_reference = self.reference_speed
            ramp = self.nominal_speed / (cfg.spool_up_seconds if powered else cfg.spool_down_seconds)
            destination = self.nominal_speed*speed_fraction if powered else 0.0
            self.reference_speed += float(np.clip(destination-self.reference_speed, -ramp*step, ramp*step))
            drag_at_nominal = np.maximum(0.0, cfg.rotor_drag_hover_nm
                + cfg.rotor_drag_per_collective_deg*(self.pitch[:2]-cfg.collective_hover_deg))
            drag = drag_at_nominal * (self.speed/self.nominal_speed)**2
            error = self.reference_speed - self.speed
            proposed_integral = self.speed_integral + error*step
            feedforward = drag if cfg.collective_feedforward else np.zeros(2)
            acceleration_ff = cfg.rotor_inertia_kgm2 * (
                self.reference_speed-previous_reference
            ) / step
            raw = feedforward + acceleration_ff + cfg.motor_speed_kp*error + cfg.motor_speed_ki*proposed_integral
            motor_torque = np.clip(raw, -cfg.motor_max_torque_nm, cfg.motor_max_torque_nm)
            self.speed_integral = np.where(abs(raw) <= cfg.motor_max_torque_nm,
                                           proposed_integral, self.speed_integral)
            self.speed += step*(motor_torque-drag) / cfg.rotor_inertia_kgm2
            self.speed = np.maximum(self.speed, 0.0)
        if not powered:
            # Disarm/emergency removes the applied wrench while visuals coast down.
            return np.zeros(3), np.zeros(3)
        speed_scale = (self.speed/self.nominal_speed)**2
        lift = 0.5*self.thrust_per_deg * np.sum(
            np.maximum(0.0, self.pitch[:2]-cfg.collective_min_deg)*speed_scale
        )
        moment = np.zeros(3)
        moment[:2] = self.cyclic_effectiveness * (
            self.pitch[2:4]*speed_scale[0] + self.pitch[4:6]*speed_scale[1]
        )
        # Counter-rotation: upper motor reacts in -Z, lower in +Z on the fuselage.
        moment[2] = motor_torque[1]-motor_torque[0]
        return (np.array([0.0, 0.0, min(lift, cfg.max_thrust_ratio*self.weight)]),
                np.clip(moment, -np.asarray(cfg.max_torque_nm), np.asarray(cfg.max_torque_nm)))
