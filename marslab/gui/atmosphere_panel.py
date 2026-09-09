"""Control tau (0.05–6), sun mode, and manual sun angles through shared runtime state."""

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
    """Interactive atmosphere controls and irradiance readouts."""

    def __init__(self, atmosphere_state: Dict[str, Any]) -> None:
        missing = [k for k in _REQUIRED_STATE_KEYS if k not in atmosphere_state]
        if missing:
            raise KeyError(
                "AtmospherePanel requires atmosphere_state to be populated by "
                "build_atmosphere_loop_state(); missing keys: " + ", ".join(missing)
            )
        self._state = atmosphere_state
        self._build_ui()

    def _build_ui(self) -> None:
        """Construct the panel layout."""
        self._window = ui.Window("MarsLab Atmosphere Control", width=420, height=420)
        with self._window.frame, ui.VStack(spacing=6):
            ui.Spacer(height=4)

            # --- Tau slider ---
            ui.Label(
                "Dust Optical Depth (tau)",
                style={"font_size": 16, "color": 0xFFDDDDDD},
            )
            self._tau_model = ui.SimpleFloatModel(self._state["tau"])
            ui.FloatSlider(model=self._tau_model, min=0.05, max=6.0)
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
            self._az_model = ui.SimpleFloatModel(self._state["sun_azimuth_deg"])
            self._az_slider = ui.FloatSlider(model=self._az_model, min=0.0, max=360.0)
            self._az_model.add_value_changed_fn(self._on_azimuth_changed)

            ui.Label("Sun Elevation (deg)", style={"font_size": 13})
            self._el_model = ui.SimpleFloatModel(self._state["sun_elevation_deg"])
            self._el_slider = ui.FloatSlider(model=self._el_model, min=0.0, max=90.0)
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
        if self._state["sun_mode"] == "manual":
            self._state["sun_azimuth_deg"] = model.as_float

    def _on_elevation_changed(self, model: ui.SimpleFloatModel) -> None:
        if self._state["sun_mode"] == "manual":
            self._state["sun_elevation_deg"] = model.as_float

    def _set_sun_mode(self, mode: str) -> None:
        self._state["sun_mode"] = mode
        self._update_slider_enabled()
        if self._mode_label:
            self._mode_label.text = self._format_mode_status()

    def _update_slider_enabled(self) -> None:
        is_manual = self._state["sun_mode"] == "manual"
        # Model callbacks still gate manual changes if a widget proxy expires.
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
        tau = self._state["tau"]
        intensity = self._state["direct_intensity"]
        return f"  tau = {tau:.2f}  |  Direct normal: {intensity:.0f} W/m2"

    def _format_mode_status(self) -> str:
        mode = self._state["sun_mode"]
        if mode == "auto":
            t = self._state["time_of_sol"]
            sol_seconds = self._state["sol_duration_seconds"]
            hours = t * (sol_seconds / 3600.0)
            return f"  Mode: Auto Sweep  |  Sol time: {hours:.1f}h ({t:.2f})"
        else:
            az = self._state["sun_azimuth_deg"]
            el = self._state["sun_elevation_deg"]
            return f"  Mode: Manual  |  Az={az:.1f} deg, El={el:.1f} deg"

    def _format_full_status(self) -> str:
        diffuse = self._state["diffuse_fraction"]
        return f"  Diffuse fraction: {diffuse:.2f}"

    def update_display(self) -> None:
        """Refresh status and auto-mode sliders after the atmosphere update."""
        if self._tau_label:
            self._tau_label.text = self._format_tau_status()
        if self._mode_label:
            self._mode_label.text = self._format_mode_status()
        if self._status_label:
            self._status_label.text = self._format_full_status()

        # Sync manual sliders with auto-computed values (when in auto mode)
        if self._state["sun_mode"] == "auto":
            self._az_model.set_value(self._state["sun_azimuth_deg"])
            self._el_model.set_value(self._state["sun_elevation_deg"])
