# M2020 source rights and attribution

The `meshes/` directory contains the mesh, buffer and texture files required by
the current MarsLab Perseverance companion URDF. They were copied without byte
changes from the following source:

- Source repository: <https://github.com/kimhoyun-robotair/m2020-urdf-models>
- Source commit: `8b591ec417d34d3b152e067b378fe45f2b5810dc`
- Original NASA/JPL repository: <https://github.com/nasa-jpl/m2020-urdf-models>
- Per-file source paths and SHA-256 hashes: [manifest.json](manifest.json)

## Upstream attribution

The [source README at the pinned commit](https://github.com/kimhoyun-robotair/m2020-urdf-models/blob/8b591ec417d34d3b152e067b378fe45f2b5810dc/README.md)
provides the following credits and release information:

- Credit NASA/JPL-Caltech.
- Rover modeling and texturing by Zareh Gorjian.
- Models courtesy of the Mars 2020 Perseverance and Ingenuity teams;
  URDF conversion by the JPL RSVP team.
- Work carried out at the Jet Propulsion Laboratory, California Institute
  of Technology, under a contract with the National Aeronautics and
  Space Administration.
- Released June 10, 2022; release identifiers URS307049 and URS309682.

## License status

The pinned source tree contains no standalone license file. Its README
provides the attribution above but does not state a software license or a
complete redistribution grant. This notice preserves the available rights
information; it does not supply additional permissions or assign a license
that the source did not specify. Consult the source rights holders for uses
that require an explicit license grant.

The [NASA-3D-Resources notice](../../../LICENSE-NASA-3D-RESOURCES.txt), including its
NASA Open Source Agreement record, describes a different source repository. It does not establish
the license of these M2020 files. MarsLab's own code licensing likewise does
not relicense this third-party content.

## MarsLab adaptations and scope

The pinned fork contains adaptations to the original NASA model. These files
are an unchanged subset of that fork, not a claim of an unchanged NASA release.
MarsLab's derived URDF and USD composition are included alongside `meshes/`.
The research LiDAR attachments are shared assets in `../sensors/`.
NASA review or endorsement of those adaptations is not claimed.

The source subset in `meshes/` contains only the currently referenced 20 glTF
meshes, their 20 binary buffers and the shared texture. The original URDF,
helicopter model, unused meshes and alternate-resolution textures are not part
of this runtime subset. The existing Isaac USD layers, physics configuration
and USD texture are retained in this directory outside that source subset.
