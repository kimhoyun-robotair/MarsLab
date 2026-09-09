# MarsLab project page

This directory contains the static project page and browser demo. Serve this directory over HTTP:

```sh
python3 -m http.server 8766 --bind 127.0.0.1
```

Open `http://localhost:8766/`, or `/demo/` for the full-window interactive lab. No build step, npm install, Isaac Sim or ROS installation is needed for playback. The introduction video loads from YouTube on demand.

`asset/` contains the referenced images and clips; `demo/` contains the viewer, vendored Three.js and recorded data. Retain the vendor license, [demo provenance](demo/DATA.md) and [clip sources](asset/showcase/SOURCES.md).
