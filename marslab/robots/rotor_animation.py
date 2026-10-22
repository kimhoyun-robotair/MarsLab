"""Motor spin-up and USD rotor visuals driven by the accepted actuator wrench."""
from __future__ import annotations

from dataclasses import dataclass
import math
from statistics import median


@dataclass
class RotorMotor:
    """A visual motor model; it does not calculate aerodynamic forces."""

    nominal_rpm: float = 2400.0
    spool_up_sec: float = 1.0
    spool_down_sec: float = 1.5
    rpm: float = 0.0
    phase: float = 0.0
    last_time: float | None = None

    def __post_init__(self):
        if not all(math.isfinite(value) and value > 0 for value in
                   (self.nominal_rpm, self.spool_up_sec, self.spool_down_sec)):
            raise ValueError("Rotor speed and spool times must be finite and positive")

    def update(self, now: float, powered: bool):
        if not math.isfinite(now):
            raise ValueError("Rotor animation time must be finite")
        if self.last_time is None or now < self.last_time:
            self.rpm = self.phase = 0.0
            self.last_time = now
            return
        dt = now - self.last_time
        self.last_time = now
        target = self.nominal_rpm if powered else 0.0
        rate = self.nominal_rpm / (self.spool_up_sec if powered else self.spool_down_sec)
        ramp_time = min(dt, abs(target - self.rpm) / rate)
        next_rpm = self.rpm + math.copysign(rate * ramp_time, target - self.rpm)
        # Integrate the ramp and any remaining time at the target speed separately.
        revolutions = ((self.rpm + next_rpm) * 0.5 * ramp_time + next_rpm * (dt - ramp_time)) / 60.0
        self.phase = (self.phase + math.tau * revolutions) % math.tau
        self.rpm = min(self.nominal_rpm, max(0.0, next_rpm))


class RotorAnimator:
    """Animate the original visual rotor links without re-enabling articulation."""

    def __init__(self, stage, visual_mount, rotor_joints, nominal_rpm=2400.0, spool_up_sec=1.0, spool_down_sec=1.5):
        from pxr import Gf, Sdf, Usd, UsdGeom, UsdShade

        self.motor = RotorMotor(nominal_rpm, spool_up_sec, spool_down_sec)
        self.rotors = []
        self._last_opacity = None
        self._Gf = Gf
        self._UsdGeom = UsdGeom
        cache = UsdGeom.XformCache(Usd.TimeCode.Default())
        material = UsdShade.Material.Define(stage, str(visual_mount.GetPath()) + "/RotorBlurMaterial")
        shader = UsdShade.Shader.Define(stage, str(material.GetPath()) + "/Shader")
        shader.CreateIdAttr("OmniPBR")
        shader.GetImplementationSourceAttr().Set(UsdShade.Tokens.sourceAsset)
        shader.SetSourceAsset(Sdf.AssetPath("OmniPBR.mdl"), "mdl")
        shader.SetSourceAssetSubIdentifier("OmniPBR", "mdl")
        shader.CreateInput("diffuse_color_constant", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(0.12, 0.14, 0.16))
        shader.CreateInput("reflection_roughness_constant", Sdf.ValueTypeNames.Float).Set(0.85)
        shader.CreateInput("metallic_constant", Sdf.ValueTypeNames.Float).Set(0.0)
        shader.CreateInput("enable_opacity", Sdf.ValueTypeNames.Bool).Set(True)
        shader.CreateInput("opacity_threshold", Sdf.ValueTypeNames.Float).Set(0.0)
        self.opacity = shader.CreateInput("opacity_constant", Sdf.ValueTypeNames.Float)
        self.opacity.Set(0.0)
        material.CreateSurfaceOutput("mdl").ConnectToSource(shader.CreateOutput("out", Sdf.ValueTypeNames.Token))

        for index, joint in enumerate(sorted(rotor_joints, key=lambda item: str(item.GetPath()))):
            targets = joint.GetBody1Rel().GetTargets()
            if len(targets) != 1:
                raise RuntimeError("Expected one visual rotor link for " + str(joint.GetPath()))
            prim = stage.GetPrimAtPath(targets[0])
            pivot = Gf.Vec3d(joint.GetLocalPos1Attr().Get())
            axis_name = joint.GetPrim().GetAttribute("physics:axis").Get()
            basis = {"X": Gf.Vec3d(1, 0, 0), "Y": Gf.Vec3d(0, 1, 0), "Z": Gf.Vec3d(0, 0, 1)}[axis_name]
            axis = Gf.Rotation(Gf.Quatd(joint.GetLocalRot1Attr().Get())).TransformDir(basis).GetNormalized()

            # Locate the blade tips and their plane in the rotor link's coordinates.
            # The asset's blade meshes have their own scale and orientation offsets.
            samples = []
            for child in Usd.PrimRange(prim):
                if not child.IsA(UsdGeom.Mesh) or UsdGeom.Imageable(child).ComputeVisibility() == UsdGeom.Tokens.invisible:
                    continue
                transform, _ = cache.ComputeRelativeTransform(child, prim)
                for point in UsdGeom.Mesh(child).GetPointsAttr().Get():
                    relative = transform.Transform(Gf.Vec3d(point)) - pivot
                    height = Gf.Dot(relative, axis)
                    radius = (relative - height * axis).GetLength()
                    samples.append((radius, height))
            if not samples:
                raise RuntimeError("No visible blade geometry for " + str(prim.GetPath()))
            radius = max(sample[0] for sample in samples)
            height = median(sample[1] for sample in samples if sample[0] >= 0.7 * radius)
            center = pivot + height * axis
            mount_transform, _ = cache.ComputeRelativeTransform(prim, visual_mount)

            xform = UsdGeom.Xformable(prim)
            xform.AddTranslateOp(opSuffix="rotorPivot").Set(pivot)
            spin = xform.AddOrientOp(precision=UsdGeom.XformOp.PrecisionDouble, opSuffix="rotorSpin")
            spin.Set(Gf.Quatd(1.0))
            xform.AddTranslateOp(opSuffix="rotorPivot", isInverseOp=True)

            # A transparent annulus keeps high-speed rotation visible at 60 FPS.
            # It is a visual exposure approximation, with no collision geometry.
            helper = Gf.Vec3d(1, 0, 0) if abs(axis[0]) < 0.9 else Gf.Vec3d(0, 1, 0)
            u = Gf.Cross(axis, helper).GetNormalized()
            v = Gf.Cross(axis, u).GetNormalized()
            segments = 96
            points = []
            for ring in (0.12 * radius, radius):
                for segment in range(segments):
                    angle = math.tau * segment / segments
                    point = center + ring * (math.cos(angle) * u + math.sin(angle) * v)
                    points.append(Gf.Vec3f(mount_transform.Transform(point)))
            indices = []
            for segment in range(segments):
                following = (segment + 1) % segments
                indices.extend((segment, following, segments + following, segments + segment))
            # Keep effects outside the referenced model's material binding tree.
            # The visual mount still carries them with the aircraft's body pose.
            blur = UsdGeom.Mesh.Define(stage, str(visual_mount.GetPath()) + f"/RotorBlur{index}")
            blur.CreatePointsAttr(points)
            blur.CreateFaceVertexCountsAttr([4] * segments)
            blur.CreateFaceVertexIndicesAttr(indices)
            blur.CreateSubdivisionSchemeAttr("none")
            blur.CreateDoubleSidedAttr(True)
            visibility = blur.CreateVisibilityAttr(UsdGeom.Tokens.invisible)
            UsdShade.MaterialBindingAPI.Apply(blur.GetPrim()).Bind(material)
            self.rotors.append((spin, axis, 1.0 if index == 0 else -1.0, visibility))
        if len(self.rotors) != 2:
            raise RuntimeError("Expected two visual rotors in the official Ingenuity asset")

    def update(self, now, powered, rpm=None):
        if rpm is None:
            self.motor.update(float(now), bool(powered))
            return
        now = float(now)
        if self.motor.last_time is None or now < self.motor.last_time:
            self.motor.phase = 0.0
        else:
            dt = now - self.motor.last_time
            self.motor.phase = (self.motor.phase + math.tau * 0.5 *
                                (self.motor.rpm + float(rpm)) * dt / 60.0) % math.tau
        self.motor.rpm = max(0.0, float(rpm))
        self.motor.last_time = now

    def reset(self):
        self.motor.rpm = self.motor.phase = 0.0
        self.motor.last_time = None
        self.apply()

    def apply(self):
        """Write scene transforms once per render, after physics has advanced."""
        fraction = min(1.0, max(0.0, (self.motor.rpm / self.motor.nominal_rpm - 0.1) / 0.6))
        opacity = 0.14 * fraction * fraction * (3.0 - 2.0 * fraction)
        changed_opacity = self._last_opacity is None or abs(opacity - self._last_opacity) > 1e-6
        for spin, axis, direction, visibility in self.rotors:
            spin.Set(self._Gf.Rotation(axis, direction * math.degrees(self.motor.phase)).GetQuat())
            if changed_opacity:
                visibility.Set(self._UsdGeom.Tokens.inherited if opacity > 0.0 else self._UsdGeom.Tokens.invisible)
        if changed_opacity:
            self.opacity.Set(opacity)
            self._last_opacity = opacity
