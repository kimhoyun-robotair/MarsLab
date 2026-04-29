"""Interactive atmosphere control panel for Isaac Sim.

Provides an omni.ui-based window with sliders and toggles for real-time
control of Mars atmospheric parameters during simulation:

- Dust optical depth (tau): slider 0.1--6.0, affects fog/sky/irradiance
- Sun control mode: "Auto Sweep" (east-to-west diurnal) or "Manual"
- Manual sun position: azimuth (0--360) and elevation (0--90) sliders

The panel reads and writes a shared ``atmosphere_state`` dict. The render
loop in :func:`marslab.runtime.main_loop.run_main_loop` checks this dict
every N frames and updates the renderers accordingly.

Requires Isaac Sim runtime (omni.ui). Guarded by try/except at import
time in ``scripts/phase1/main.py`` so headless or non-GUI environments
degrade gracefully.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

import omni.ui as ui

_LOG = logging.getLogger(__name__)

_REQUIRED_STATE_KEYS = (
    "tau",
    "sun_mode",
    "sun_azimuth_deg",
    "sun_elevation_deg",
    "time_of_sol",
    "direct_intensity",
    "diffuse_fraction",
    "sol_duration_seconds",
)


class AtmospherePanel:
    """omni.ui window for interactive atmosphere parameter control.

    Widget references (sliders, labels, buttons) are stored as attributes
    on the instance so they can be updated from the render loop. They are
    constructed inside an ``omni.ui`` ``with`` block; once that builder
    scope exits, Kit's C++ proxy lifetime is independent of the Python
    reference. This means the ``.enabled`` setter on a stored slider may
    later raise ``AttributeError`` or ``RuntimeError`` if the underlying
    proxy has been finalized. ``_update_slider_enabled`` catches and
    logs those cases instead of crashing the GUI thread; see the
    rationale block in that method.

    Args:
        atmosphere_state: Mutable dict shared with the render loop.
            Must contain the keys listed in ``_REQUIRED_STATE_KEYS``;
            ``__init__`` raises ``KeyError`` if any are missing so that
            misconfiguration surfaces immediately rather than as a later
            ``KeyError`` deep inside the render loop.
    """

    def __init__(self, atmosphere_state: Dict[str, Any]) -> None:
        missing = [k for k in _REQUIRED_STATE_KEYS if k not in atmosphere_state]
        if missing:
            raise KeyError(
                "AtmospherePanel requires atmosphere_state to be populated by "
                "build_atmosphere_state(); missing keys: " + ", ".join(missing)
            )
        self._state = atmosphere_state
        self._build_ui()

    def _build_ui(self) -> None:
        """Construct the panel layout."""
        self._window = ui.Window("MarsLab Atmosphere Control", width=420, height=340)
        with self._window.frame, ui.VStack(spacing=6):
            ui.Spacer(height=4)

            # --- Tau slider ---
            ui.Label(
                "Dust Optical Depth (tau)",
                style={"font_size": 16, "color": 0xFFDDDDDD},
            )
            self._tau_model = ui.SimpleFloatModel(self._state.get("tau", 0.3))
            ui.FloatSlider(model=self._tau_model, min=0.1, max=6.0)
            self._tau_model.add_value_changed_fn(self._on_tau_changed)

            self._tau_label = ui.Label(
                self._format_tau_status(),
                style={"font_size": 12, "color": 0xFFAAAAAA},
            )

            ui.Spacer(height=8)
            ui.Line(style={"color": 0xFF444444}, height=1)
            ui.Spacer(height=4)

            # --- Sun mode toggle ---
            ui.Label(
                "Sun Control",
                style={"font_size": 16, "color": 0xFFDDDDDD},
            )
            with ui.HStack(spacing=10):
                ui.Label("Mode:", width=50)
                self._auto_btn = ui.Button(
                    "Auto Sweep",
                    clicked_fn=lambda: self._set_sun_mode("auto"),
                    width=120,
                )
                self._manual_btn = ui.Button(
                    "Manual",
                    clicked_fn=lambda: self._set_sun_mode("manual"),
                    width=120,
                )

            self._mode_label = ui.Label(
                self._format_mode_status(),
                style={"font_size": 12, "color": 0xFFAAAAAA},
            )

            ui.Spacer(height=4)

            # --- Manual sun sliders ---
            ui.Label("Sun Azimuth (deg)", style={"font_size": 13})
            self._az_model = ui.SimpleFloatModel(self._state.get("sun_azimuth_deg", 180.0))
            self._az_slider = ui.FloatSlider(model=self._az_model, min=0.0, max=360.0)
            self._az_model.add_value_changed_fn(self._on_azimuth_changed)

            ui.Label("Sun Elevation (deg)", style={"font_size": 13})
            self._el_model = ui.SimpleFloatModel(self._state.get("sun_elevation_deg", 45.0))
            self._el_slider = ui.FloatSlider(model=self._el_model, min=0.5, max=89.5)
            self._el_model.add_value_changed_fn(self._on_elevation_changed)

            ui.Spacer(height=4)
            ui.Line(style={"color": 0xFF444444}, height=1)
            ui.Spacer(height=2)

            # --- Status readout ---
            self._status_label = ui.Label(
                self._format_full_status(),
                style={"font_size": 11, "color": 0xFF888888},
            )

        # Initial slider enable/disable
        self._update_slider_enabled()

    # --- Callbacks ---

    def _on_tau_changed(self, model: ui.SimpleFloatModel) -> None:
        self._state["tau"] = model.as_float

    def _on_azimuth_changed(self, model: ui.SimpleFloatModel) -> None:
        if self._state.get("sun_mode") == "manual":
            self._state["sun_azimuth_deg"] = model.as_float

    def _on_elevation_changed(self, model: ui.SimpleFloatModel) -> None:
        if self._state.get("sun_mode") == "manual":
            self._state["sun_elevation_deg"] = model.as_float

    def _set_sun_mode(self, mode: str) -> None:
        self._state["sun_mode"] = mode
        self._update_slider_enabled()
        if self._mode_label:
            self._mode_label.text = self._format_mode_status()

    def _update_slider_enabled(self) -> None:
        is_manual = self._state.get("sun_mode") == "manual"
        # omni.ui FloatSlider widgets are owned by the VStack context; once
        # the Python-side reference outlives the builder scope the C++ proxy
        # may be finalized, so `.enabled` can raise AttributeError/RuntimeError
        # even though the attribute binding still exists. Model-level gating
        # in _on_{azimuth,elevation}_changed already enforces state safety,
        # so logging-and-skipping here is behaviourally equivalent.
        for attr in ("_az_slider", "_el_slider"):
            widget = getattr(self, attr, None)
            if widget is None:
                continue
            try:
                widget.enabled = is_manual
            except (AttributeError, RuntimeError) as exc:
                _LOG.debug(
                    "Widget %r enable/disable failed (proxy likely finalized): %s",
                    widget,
                    exc,
                )
                continue

    # --- Status formatting ---

    def _format_tau_status(self) -> str:
        tau = self._state.get("tau", 0.3)
        intensity = self._state.get("direct_intensity", 0.0)
        return f"  tau = {tau:.2f}  |  Direct irradiance: {intensity:.0f} W/m2"

    def _format_mode_status(self) -> str:
        mode = self._state.get("sun_mode", "auto")
        if mode == "auto":
            t = self._state.get("time_of_sol", 0.0)
            # ``sol_duration_seconds`` is seeded by ``build_atmosphere_state``
            # from the pydantic ``MarsEnvConfig.sol_duration_seconds`` default,
            # so no local fallback literal is needed here. ``__init__``
            # validated its presence already.
            sol_seconds = self._state["sol_duration_seconds"]
            hours = t * (sol_seconds / 3600.0)
            return f"  Mode: Auto Sweep  |  Sol time: {hours:.1f}h ({t:.2f})"
        else:
            az = self._state.get("sun_azimuth_deg", 180.0)
            el = self._state.get("sun_elevation_deg", 45.0)
            return f"  Mode: Manual  |  Az={az:.1f} deg, El={el:.1f} deg"

    def _format_full_status(self) -> str:
        diffuse = self._state.get("diffuse_fraction", 0.0)
        return f"  Diffuse fraction: {diffuse:.2f}"

    def update_display(self) -> None:
        """Refresh status labels from current atmosphere_state.

        Called from the render loop after atmosphere parameters are
        recomputed, so the panel shows up-to-date values.
        """
        if self._tau_label:
            self._tau_label.text = self._format_tau_status()
        if self._mode_label:
            self._mode_label.text = self._format_mode_status()
        if self._status_label:
            self._status_label.text = self._format_full_status()

        # Sync manual sliders with auto-computed values (when in auto mode)
        if self._state.get("sun_mode") == "auto":
            self._az_model.set_value(self._state.get("sun_azimuth_deg", 180.0))
            self._el_model.set_value(self._state.get("sun_elevation_deg", 45.0))
