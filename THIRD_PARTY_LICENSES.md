# Third-Party Licenses

MarsLab vendors third-party software whose licenses must be preserved
and reproduced.  The list below covers every third-party artifact
that ships with the MarsLab repository (either as files committed
to the repo or as a git submodule).

Runtime dependencies installed via ``pip`` / ``apt`` are governed by
their respective upstream licenses and are **not** listed here; see
``pyproject.toml`` for the Python dependency set and the system-wide
``/usr/share/doc/<pkg>/copyright`` for ROS2 / Isaac Sim packages.

---

## NASA JPL m2020-urdf-models

* **Vendored at:** ``assets/m2020-urdf-models/`` (git submodule)
* **Upstream:** https://github.com/nasa-jpl/m2020-urdf-models
* **MarsLab fork:** https://github.com/kimhoyun-robotair/m2020-urdf-models
  (pinned commit; see ``.gitmodules``)
* **Release IDs:** URS307049, URS309682
* **Attribution:** "Models courtesy of the Mars 2020 Perseverance and
  Ingenuity teams and URDF conversion by JPL RSVP team. This work was
  carried out at the Jet Propulsion Laboratory, California Institute
  of Technology, under a contract with the National Aeronautics and
  Space Administration. Released June 10th, 2022. Credit
  NASA/JPL-Caltech. Rover modeling and texturing by Zareh Gorjian."
  (Source: ``assets/m2020-urdf-models/README.md``.)
* **License terms:** The upstream repository does **not** ship an
  explicit ``LICENSE`` / ``NOTICE`` file.  US Federal government works
  prepared by NASA employees are typically not subject to copyright in
  the United States (17 U.S.C. § 105) and are released under the
  NASA Open Source Agreement v1.3 or in the public domain by default.
  **MarsLab v1.0 release blocker:** verify with the JPL Open Source
  Office (https://opensource.jpl.nasa.gov/) and replace this paragraph
  with the upstream-confirmed license text before tagging v1.0.

### What MarsLab uses

* The Perseverance rover URDF (``rover/m2020.urdf``).
* The associated glTF mesh assets under ``rover/meshes/``.

The URDF is consumed two ways:

1. **Offline** — converted once to USD via
   ``scripts/phase1/convert_urdf_to_usd.py`` and the USD is loaded by
   the runtime.
2. **Runtime** — read at Stage-3 boot, mesh paths are rewritten from
   ``./meshes/`` to absolute ``file://`` URIs (see
   ``marslab.ros2_bridge.robot_description_publisher.rewrite_mesh_paths_to_file_uri``)
   and the result is published on the latched
   ``/<ns>/robot_description`` topic for RViz / ``robot_state_publisher``.

The submodule files themselves are **not** modified by MarsLab.  Any
required changes (for example, baked-in ``package://`` mesh paths)
are applied either in the fork's own commits or at runtime by the
publisher's text rewrite.
