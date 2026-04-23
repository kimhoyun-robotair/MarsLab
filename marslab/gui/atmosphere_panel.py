"""Interactive atmosphere control panel for Isaac Sim.

Provides an omni.ui-based window with sliders and toggles for real-time
control of Mars atmospheric parameters during simulation:

- Dust optical depth (tau): slider 0.1--6.0, affects fog/sky/irradiance
- Sun control mode: "Auto Sweep" (east-to-west diurnal) or "Manual"
- Manual sun position: azimuth (0--360) and elevation (0--90) sliders

The panel reads and writes a shared ``atmosphere_state`` dict. The render
loop in run_stage2.py checks this dict every N frames and updates the
renderers accordingly.

Requires Isaac Sim runtime (omni.ui). Guarded by try/except at import
time in run_stage2.py so headless or non-GUI environments degrade
gracefully.
"""

from __future__ import annotations

from typing import Any, Dict

import omni.ui as ui


class AtmospherePanel:
    """omni.ui window for interactive atmosphere parameter control.

    Args:
        atmosphere_state: Mutable dict shared with the render loop.
            Expected keys: tau, sun_mode, sun_azimuth_deg,
            sun_elevation_deg, time_of_sol, direct_intensity,
            diffuse_fraction.
    """

    def __init__(self, atmosphere_state: Dict[str, Any]) -> None:
        self._state = atmosphere_state
        self._build_ui()

    def _build_ui(self) -> None:
        """Construct the panel layout."""
        self._window = ui.Window("MarsLab Atmosphere Control", width=420, height=340)
        with self._window.frame:
            with ui.VStack(spacing=6):
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
        self._az_slider.enabled = is_manual
        self._el_slider.enabled = is_manual

    # --- Status formatting ---

    def _format_tau_status(self) -> str:
        tau = self._state.get("tau", 0.3)
        intensity = self._state.get("direct_intensity", 0.0)
        return f"  tau = {tau:.2f}  |  Direct irradiance: {intensity:.0f} W/m2"

    def _format_mode_status(self) -> str:
        mode = self._state.get("sun_mode", "auto")
        if mode == "auto":
            t = self._state.get("time_of_sol", 0.0)
            # P6 G5 (2026-04-23): previously ``self._state.get(..., 88642.0)``.
            # ``build_atmosphere_state`` / ``run_stage3_monolithic_new.py``
            # always seed ``sol_duration_seconds`` from the pydantic
            # ``MarsEnvConfig.sol_duration_seconds`` default, so the local
            # fallback literal duplicated the schema and is now gone.
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
