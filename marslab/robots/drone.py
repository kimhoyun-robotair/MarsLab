"""Rigid-body Ingenuity adapter ported from ingenuity_isaac51/sim/run_sim.py."""

from dataclasses import dataclass
import math

import numpy as np

from marslab.config.schema.drone import DroneConfig

ASSET_SUFFIX = "/Isaac/Robots/NASA/Ingenuity/ingenuity.usd"


@dataclass
class SpawnedDrone:
    body: object
    rotor_animation: object
    prim_path: str
    asset_url: str


def spawn_drone(world, stage, config: DroneConfig, position, rpy) -> SpawnedDrone:
    from isaacsim.core.prims import RigidPrim
    from isaacsim.storage.native import get_assets_root_path
    from pxr import Gf, PhysxSchema, Usd, UsdGeom, UsdPhysics

    from marslab.robots.rotor_animation import RotorAnimator

    asset_url = config.asset_url
    if not asset_url:
        root = get_assets_root_path()
        if not root:
            raise RuntimeError("Set drone.asset_url to the installed NVIDIA Ingenuity USD")
        asset_url = root.rstrip("/") + ASSET_SUFFIX
    source = Usd.Stage.Open(asset_url, load=Usd.Stage.LoadAll)
    if source is None or not source.GetDefaultPrim():
        raise RuntimeError(f"Cannot open Ingenuity USD: {asset_url}")
    scale = config.asset_scale or UsdGeom.GetStageMetersPerUnit(source)

    def xform(path, translation, quaternion=None, scaling=None):
        prim = UsdGeom.Xform.Define(stage, path).GetPrim()
        transform = UsdGeom.Xformable(prim)
        transform.AddTranslateOp().Set(Gf.Vec3d(*translation))
        if quaternion is not None:
            transform.AddOrientOp().Set(Gf.Quatf(quaternion[0], Gf.Vec3f(*quaternion[1:])))
        if scaling is not None:
            transform.AddScaleOp().Set(Gf.Vec3f(*scaling))
        return prim

    cr, sr = math.cos(rpy[0]/2), math.sin(rpy[0]/2)
    cp, sp = math.cos(rpy[1]/2), math.sin(rpy[1]/2)
    cy, sy = math.cos(rpy[2]/2), math.sin(rpy[2]/2)
    orientation = (cr*cp*cy + sr*sp*sy, sr*cp*cy - cr*sp*sy,
                   cr*sp*cy + sr*cp*sy, cr*cp*sy - sr*sp*cy)
    path = config.prim_path
    carrier = xform(path, position, orientation)
    axis_rotation = ((math.sqrt(0.5), math.sqrt(0.5), 0.0, 0.0)
                     if UsdGeom.GetStageUpAxis(source) == UsdGeom.Tokens.y
                     else (1.0, 0.0, 0.0, 0.0))
    mount = xform(path + "/VisualMount", (0.0, 0.0, 0.0), axis_rotation, (scale,)*3)
    visual = stage.DefinePrim(path + "/VisualMount/Model", "Xform")
    visual.GetReferences().AddReference(asset_url)
    stage.Load(visual.GetPath())
    for _ in range(8):
        instances = [prim for prim in Usd.PrimRange(visual) if prim.IsInstance()]
        if not instances:
            break
        for prim in instances:
            prim.SetInstanceable(False)

    rotor_joints = []
    for prim in list(Usd.PrimRange(visual)):
        if prim.IsA(UsdPhysics.Scene):
            prim.SetActive(False)
            continue
        if prim.IsA(UsdPhysics.Joint):
            joint = UsdPhysics.Joint(prim)
            if prim.IsA(UsdPhysics.RevoluteJoint) and "rotor_visual" in prim.GetName():
                rotor_joints.append(joint)
            joint.CreateJointEnabledAttr(False)
            prim.SetActive(False)
            continue
        if prim.HasAPI(UsdPhysics.RigidBodyAPI):
            UsdPhysics.RigidBodyAPI(prim).CreateRigidBodyEnabledAttr(False)
            for api in (UsdPhysics.RigidBodyAPI, PhysxSchema.PhysxRigidBodyAPI, UsdPhysics.MassAPI):
                prim.RemoveAPI(api)
        for api in (UsdPhysics.ArticulationRootAPI, PhysxSchema.PhysxArticulationAPI,
                    UsdPhysics.CollisionAPI, UsdPhysics.MeshCollisionAPI,
                    PhysxSchema.PhysxCollisionAPI):
            if prim.HasAPI(api):
                prim.RemoveAPI(api)
        if prim.IsA(UsdGeom.Xformable):
            UsdGeom.Xformable(prim).SetResetXformStack(False)

    bound = UsdGeom.BBoxCache(Usd.TimeCode.Default(),
                              [UsdGeom.Tokens.default_, UsdGeom.Tokens.render],
                              useExtentsHint=False).ComputeRelativeBound(mount, carrier)
    lower, upper = np.asarray(bound.ComputeAlignedRange().GetMin()), np.asarray(bound.ComputeAlignedRange().GetMax())
    mount.GetAttribute("xformOp:translate").Set(Gf.Vec3d(
        -0.5*(lower[0]+upper[0]), -0.5*(lower[1]+upper[1]),
        config.foot_z_m - config.foot_radius_m - lower[2],
    ))
    actuators = config.actuators
    animation = RotorAnimator(stage, mount, rotor_joints, actuators.rotor_rpm,
                               actuators.spool_up_seconds, actuators.spool_down_seconds)
    rigid = UsdPhysics.RigidBodyAPI.Apply(carrier)
    rigid.CreateRigidBodyEnabledAttr(True)
    rigid.CreateKinematicEnabledAttr(False)
    mass = UsdPhysics.MassAPI.Apply(carrier)
    mass.CreateMassAttr(config.mass_kg)
    mass.CreateCenterOfMassAttr(Gf.Vec3f(0.0, 0.0, 0.0))
    mass.CreateDiagonalInertiaAttr(Gf.Vec3f(*config.inertia_kgm2))
    mass.CreatePrincipalAxesAttr(Gf.Quatf(1.0, Gf.Vec3f(0.0, 0.0, 0.0)))
    physics = PhysxSchema.PhysxRigidBodyAPI.Apply(carrier)
    physics.CreateEnableCCDAttr(True)
    physics.CreateLinearDampingAttr(0.0)
    physics.CreateAngularDampingAttr(0.0)
    physics.CreateSolverPositionIterationCountAttr(16)
    physics.CreateSolverVelocityIterationCountAttr(4)
    extent = config.foot_xy_m
    for index, (x, y) in enumerate(((extent, extent), (extent, -extent),
                                    (-extent, extent), (-extent, -extent))):
        foot = UsdGeom.Sphere.Define(stage, path + f"/FootCollider{index}")
        foot.CreateRadiusAttr(config.foot_radius_m)
        UsdGeom.Xformable(foot.GetPrim()).AddTranslateOp().Set(Gf.Vec3d(x, y, config.foot_z_m))
        foot.CreateVisibilityAttr(UsdGeom.Tokens.invisible)
        UsdPhysics.CollisionAPI.Apply(foot.GetPrim())
    body = world.scene.add(RigidPrim(path, name="ingenuity_rigid_body", reset_xform_properties=False))
    return SpawnedDrone(body, animation, path, asset_url)
