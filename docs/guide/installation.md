---
title: Installation
description: Prepare Isaac Sim, the scene assets and the separate ROS companion environment.
permalink: /guide/installation/
---

## Requirements

| Component | Requirement |
|:---|:---|
| **Operating system** | Linux supported by Isaac Sim 5.x |
| **NVIDIA Isaac Sim** | 5.x |
| **ROS 2** | Jazzy, optional and required only for ROS interfaces |
| **Python** | 3.11+ for offline configuration and utility work |
| **GPU** | NVIDIA GPU supported by the selected Isaac Sim renderer |
| **Rover assets** | Runtime USD, URDF, meshes, and textures included in this repository |
| **Scene asset** | A downloaded Mars scene referenced by `scene.usdz_path` |

> **Separate environments:**
> Isaac Sim and system ROS 2 are separate environments. Do not source the
> system ROS setup script in the terminal used to launch MarsLab.

---

## Set up the checkout

## Clone MarsLab

```bash
git clone https://github.com/kimhoyun-robotair/MarsLab.git
cd MarsLab
```

The Perseverance USD and companion URDF are included under
`assets/robots/perseverance/`, alongside the URDF's meshes and textures in
`meshes/`. Their source and rights are recorded in
[the M2020 notice](https://github.com/kimhoyun-robotair/MarsLab/blob/main/assets/robots/perseverance/LICENSE.md).

## Download the Mars scenes

Download the scene package from
[**Google Drive — MarsLab Scene Assets**](https://drive.google.com/drive/folders/1evy98zVN0zn-F4Ga3ATRxnYj0xcarkEK?usp=drive_link),
then extract or copy the scene directories into `assets/scene/`.

The supplied configuration expects this default file:

```text
assets/scene/
└── jezero_plain/
    └── jezero_plain.usdz
```

Other downloaded environments can be stored beside `jezero_plain`. Select one
by changing `scene.usdz_path` in `configs/config.yaml`. MarsLab consumes these
assets as inputs; it does not generate or convert terrain during startup.

## Install Python dependencies

Run MarsLab from this checkout. [requirements.txt](https://github.com/kimhoyun-robotair/MarsLab/blob/main/requirements.txt) declares
the Python dependencies for the simulator, configuration tools, and ROS
companion. Install them into each Python environment you use.

By default, the launcher looks for Isaac Sim at `$HOME/isaacsim`. If Isaac Sim
is installed elsewhere, set its installation directory for the current shell:

```bash
export ISAAC_SIM_PATH=/path/to/isaacsim
```

In the Isaac terminal, install the dependencies using its bundled Python:

```bash
marslab/isaac_python.sh -m pip install -r requirements.txt
```

For the ROS companion or offline configuration tools, create a separate virtual
environment using the system Python. The `python3-venv` OS package is required.
System packages remain visible so the environment can use the installed ROS 2
Jazzy packages:

```bash
/usr/bin/python3 -m venv --system-site-packages .venv
.venv/bin/python -m pip install -r requirements.txt
```

The [first-run commands]({{ "/guide/quickstart/" | relative_url }}) explicitly use this environment's Python. Installing
dependencies there does not install them into Isaac Sim's bundled Python.

---


Next: [launch your first run]({{ "/guide/quickstart/" | relative_url }}).
