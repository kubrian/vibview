"""3D molecular viewer built on vispy — thin orchestrator.

Delegates camera, scene, and animation to focused sub-controllers.
"""

import sys
from collections.abc import Callable
from pathlib import Path

from PyQt6.QtWidgets import QMessageBox
from vispy import app

from vibview.renderers.animation_controller import AnimationController
from vibview.renderers.camera_controller import CameraController
from vibview.renderers.export import (
    save_gif,
    save_mp4,
    save_png_sequence,
)
from vibview.renderers.qt_window import VibviewWindow
from vibview.renderers.scene_builder import SceneBuilder
from vibview.storage import update_labels


class VispyViewer:
    """Interactive 3D viewer for molecular vibrations — thin orchestrator."""

    def __init__(
        self,
        structure,
        config,
        mode_type: str,
        mode_index: int = 0,
        qpoint_index: int = 0,
        create_window: bool = True,
        supercell: tuple[int, int, int] | None = None,
        source_path: str | None = None,
    ):
        self.structure = structure
        self.mode_index = mode_index
        self.qpoint_index = qpoint_index
        self.mode_type = mode_type
        self.supercell = tuple(supercell) if supercell is not None else None
        self._source_path = source_path

        self.fps = config.animation.fps
        self.period = config.animation.period
        self.gif_fps = config.export.gif_fps
        self.mp4_fps = config.export.mp4_fps
        self.cycles = config.export.cycles
        self.show_axis = config.display.show_axis

        self.mode_amplitudes = {
            "animate": config.animation.default_amplitude,
            "static": config.static.amplitude,
            "overlay": config.overlay.amplitude,
        }
        self.amplitude = self.mode_amplitudes[self.mode_type]

        # ── Sub-controllers ──
        self.camera = CameraController(structure, config)
        self.scene = SceneBuilder(structure, config, self.camera.view.scene)
        self.scene.set_camera(self.camera)
        self.scene.supercell = self.supercell
        self.animation = AnimationController(
            structure, config, self.scene, self.camera.view.scene
        )

        self.camera.setup_interaction()
        self.scene.build_base()
        if self.show_axis:
            self.camera.add_axis_indicators()
        self._reset_positions_to_equilibrium()
        self._apply_mode_state()

        if create_window:
            self._setup_window(config, mode_index, qpoint_index)

    # ── Helpers ──
    def _reset_positions_to_equilibrium(self) -> None:
        eq_xyz = self.scene.get_equilibrium_xyz()
        self.scene.atoms.apply_positions(eq_xyz)
        self.scene.bonds.update_transforms(eq_xyz)

    # ── Mode state ──
    def _apply_mode_state(self) -> None:
        self.animation.show_base_visuals()
        self.scene.rebuild_overlays(self.mode_type, self.mode_index, self.amplitude)
        if self.mode_type == "animate":
            self.animation.start(
                mode_index=self.mode_index,
                amplitude=self.amplitude,
                qpoint_index=self.qpoint_index,
                supercell=self.supercell,
            )
        self.camera.canvas.update()

    # ── Window ──
    def _setup_window(self, config, mode_index, qpoint_index) -> None:
        qpoints = self.structure.data.qpoints or []
        frequency_units = self.structure.data.frequency_units
        self.window = VibviewWindow(
            self.camera.canvas,
            self.structure.modes,
            initial_index=mode_index,
            initial_mode=self.mode_type,
            initial_amplitudes=self.mode_amplitudes,
            initial_period=self.period,
            frequency_units=frequency_units,
            imaginary_color=config.display.imaginary_color,
            qpoints=qpoints,
            initial_qpoint=qpoint_index,
            initial_supercell=self.supercell or (1, 1, 1),
            source_path=self._source_path,
        )
        self.window.on_camera_reset = self.camera.reset_camera
        self.window.on_toggle_hud = self.camera.toggle_hud
        self.window.panel.on_apply = self._on_apply
        self.window.panel.on_save_animation = lambda fmt, name, progress_callback: (
            self.export_animation(fmt, name, self.cycles, progress_callback)
        )
        self.window.panel.on_save_labels = self._on_save_labels

    # ── Q-point switching ──
    def switch_qpoint(self, qpoint_index) -> None:
        if qpoint_index == self.qpoint_index:
            return
        panel = self.window.panel
        if panel._labels_dirty:
            reply = QMessageBox.question(
                panel,
                "Unsaved Labels",
                "You have unsaved label changes. Save before switching?",
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
            )
            if reply == QMessageBox.StandardButton.Save:
                self._on_save_labels()
            elif reply == QMessageBox.StandardButton.Cancel:
                return
        self.qpoint_index = qpoint_index
        self.structure.switch_qpoint(qpoint_index)
        self.window.panel.set_modes(self.structure.modes)
        self.mode_index = 0
        self.switch_mode(self.mode_index)

    # ── Mode switching ──
    def switch_mode(self, mode_index) -> None:
        self.mode_index = mode_index
        self.animation.stop()
        self._reset_positions_to_equilibrium()
        self._apply_mode_state()

    # ── Apply callback ──
    def _on_apply(self) -> None:
        panel = self.window.panel
        new_qp = panel._qpoint_spin.value()
        new_sc = (
            panel._sc_nx.value(),
            panel._sc_ny.value(),
            panel._sc_nz.value(),
        )
        new_mt = panel.current_mode
        new_mi = panel._pending_mode_index
        new_amp = panel.amplitude_spin.value()
        new_per = panel.period_spin.value()

        self.animation.stop()
        self.mode_amplitudes[new_mt] = new_amp

        if new_qp != self.qpoint_index:
            self.switch_qpoint(new_qp)
        if new_sc != (self.supercell or (1, 1, 1)):
            self._apply_supercell(new_sc)
        self.mode_type = new_mt
        self.amplitude = new_amp
        self.period = new_per
        self.animation.period = new_per
        self.switch_mode(new_mi)

    def _on_save_labels(self) -> None:
        panel = self.window.panel
        path: str | None = panel._save_path
        if path is None or Path(path).suffix.lower() != ".h5":
            return

        p = Path(path)
        qp_idx = self.qpoint_index if self.structure.is_crystal else None
        try:
            update_labels(p, self.structure.modes, qpoint_index=qp_idx)
        except (OSError, KeyError) as e:
            QMessageBox.warning(panel, "Save Failed", f"Could not save labels:\n{e}")
            return

        panel._labels_dirty = False
        panel.btn_save_labels.setEnabled(False)

    def _apply_supercell(self, new_sc: tuple[int, int, int]) -> None:
        self.supercell = new_sc
        self.scene.supercell = new_sc
        self.animation.clear_frame_cache()
        self.scene.build_base()
        self._reset_positions_to_equilibrium()

    # ── Export ──
    def export_animation(
        self,
        format: str,
        name: str,
        cycles: int,
        progress_callback: Callable[[int, int], None] | None,
    ) -> None:

        fps = {"gif": self.gif_fps, "mp4": self.mp4_fps}.get(format, self.fps)
        n_frames = max(int(round(fps * self.period)), 2)

        export_frames = self.animation.generate_frame_positions(
            self.mode_index,
            self.amplitude,
            n_frames,
            cycles,
            supercell=self.supercell,
        )

        self.camera.sync_axis_camera()
        images = self.animation.render_export_frames(
            self.camera.canvas,
            export_frames,
            progress_callback,
        )

        if format == "png":
            paths = save_png_sequence(images, name)
            print(f"Exported {len(paths)} PNG frames to {name}_*.png", file=sys.stderr)
        elif format == "gif":
            out_path = f"{name}.gif"
            duration = 1000.0 / self.gif_fps
            path = save_gif(images, out_path, duration=duration, loop=0)
            print(f"Exported GIF to {path}", file=sys.stderr)
        elif format == "mp4":
            out_path = f"{name}.mp4"
            path = save_mp4(images, out_path, fps=self.mp4_fps)
            print(f"Exported MP4 to {path}", file=sys.stderr)

    def run(self) -> None:
        self.window.show()
        self.camera.prewarm_hud()
        app.run()
