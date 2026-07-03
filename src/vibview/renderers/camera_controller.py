"""Camera and canvas management for the vispy viewer."""

import numpy as np
from vispy import scene
from vispy.scene import visuals
from vispy.scene.widgets import ViewBox
from vispy.util.quaternion import Quaternion

from vibview.renderers._geometry import build_arrow_visuals


class CameraController:
    """Owns the SceneCanvas, main camera, axis sub-view, and HUD overlay.

    Handles camera setup, pan/zoom/reset, axis indicator visuals, the
    mini axis-rotation indicator in the lower-left corner, and an
    optional heads-up display (HUD) showing current camera parameters.
    """

    def __init__(self, structure, config):
        self.structure = structure
        self._lighting = config.lighting
        self._camera_cfg = config.camera
        self._axis_cfg = config.axis
        self.axis_visuals = []
        self.axis_labels = []

        # ── Camera pose ──────────────────────────────────────────
        if config.camera.center[0] == float("inf"):
            center = np.mean(self.structure.xyz, axis=0)
        else:
            center = np.array(config.camera.center)

        if config.camera.distance == float("inf"):
            fov = config.camera.fov
            radii = np.linalg.norm(self.structure.xyz - center, axis=1)
            if fov == 0:
                cam_distance = max(
                    radii.max() / config.camera.fill_factor,
                    config.camera.min_distance,
                )
            else:
                cam_distance = max(
                    radii.max()
                    / (config.camera.fill_factor * np.tan(np.radians(fov / 2))),
                    config.camera.min_distance,
                )
        else:
            cam_distance = config.camera.distance

        self.canvas = scene.SceneCanvas(
            show=False,
            title="VibView",
            bgcolor=config.rendering.background_color.rgba,
            size=tuple(config.camera.default_window_size),
        )
        self.view = self.canvas.central_widget.add_view()
        self.view.camera = scene.cameras.ArcballCamera(
            center=center,
            distance=cam_distance,
            fov=config.camera.fov,
        )

        if config.camera.azimuth != float("inf") and config.camera.elevation != float(
            "inf"
        ):
            q = self._build_quaternion(config.camera.azimuth, config.camera.elevation)
            self.view.camera._quaternion = q
            self.view.camera.view_changed()

        # ── Axis sub-view ────────────────────────────────────────
        self.axis_view = ViewBox(
            parent=self.canvas.scene,
        )
        self.axis_view.interactive = False
        self.axis_view.camera = scene.cameras.ArcballCamera(
            center=(0, 0, 0),
            distance=config.camera.axis_camera_distance,
            fov=config.camera.axis_camera_fov,
        )
        self._update_axis_view_layout()
        self.canvas.events.resize.connect(self._update_axis_view_layout)

        # ── HUD overlay ──────────────────────────────────────────
        self._hud_visible = config.camera.show_hud
        self._hud_view = self._create_hud_view()
        self._hud_view.visible = config.camera.show_hud
        self._layout_hud()
        visible = self._hud_visible
        self._hud_visible = True
        self._update_hud()
        self._hud_visible = visible

    def prewarm_hud(self) -> None:
        if self._hud_visible:
            return
        self._hud_view.visible = True
        self.canvas.render()
        self._hud_view.visible = False

    def _update_axis_view_layout(self, event=None):
        w, h = self.canvas.size
        ov_size = self._camera_cfg.axis_view_size
        pad = self._camera_cfg.axis_view_padding
        self.axis_view.pos = (pad, h - ov_size - pad)
        self.axis_view.size = (ov_size, ov_size)

    def setup_interaction(self):
        self._initial_camera_center = np.array(self.view.camera.center)
        self._initial_camera_distance = self.view.camera.distance
        self._initial_camera_quaternion = self.view.camera._quaternion.copy()
        self.view.camera.events.mouse_move.connect(self.sync_axis_camera)
        self.view.camera.events.mouse_wheel.connect(self.sync_axis_camera)
        self.canvas.events.draw.connect(self.sync_axis_camera)
        self.canvas.events.draw.connect(self._update_hud)
        self.sync_axis_camera()

    def sync_axis_camera(self, event=None):
        self.axis_view.camera._quaternion = self.view.camera._quaternion.copy()
        self.axis_view.camera.view_changed()

    def set_initial_state(self, center, distance, quaternion):
        """Override stored initial camera state (used in tests)."""
        self._initial_camera_center = center
        self._initial_camera_distance = distance
        self._initial_camera_quaternion = quaternion

    def reset_camera(self):
        self.view.camera.center = self._initial_camera_center
        self.view.camera.distance = self._initial_camera_distance
        self.view.camera._quaternion = self._initial_camera_quaternion.copy()
        self.view.camera.view_changed()
        self.sync_axis_camera()
        self.canvas.update()

    def apply_shading_filter(self, visual):
        sf = getattr(visual, "shading_filter", None)
        if sf is None and hasattr(visual, "mesh"):
            sf = visual.mesh.shading_filter
        if sf is not None:
            sf.ambient_light = self._lighting.ambient
            sf.diffuse_light = self._lighting.diffuse
            sf.specular_light = self._lighting.specular
            sf.shininess = self._lighting.shininess

    def _add_small_arrow(self, origin, direction, length, color, parent):
        direction = np.array(direction, dtype=float)
        norm = np.linalg.norm(direction)
        if norm < 1e-12:
            return
        direction = direction / norm

        tip_length = self._axis_cfg.tip_length
        shaft_end = origin + (length - tip_length) * direction

        tube, cone = build_arrow_visuals(
            origin,
            shaft_end,
            direction,
            self._axis_cfg.shaft_radius,
            self._axis_cfg.tip_radius,
            tip_length,
            color,
            parent,
            shading=None,
            cone_offset=0.001,
        )
        self.axis_visuals.append(tube)
        self.axis_visuals.append(cone)

    def add_axis_indicators(self):
        self.axis_visuals.clear()
        self.axis_labels.clear()
        parent = self.axis_view.scene
        origin = np.zeros(3)
        arrow_length = self._axis_cfg.arrow_length
        label_offset = self._axis_cfg.label_offset
        lattice = self.structure.data.lattice
        if lattice is not None and len(lattice) != 3:
            raise ValueError(
                f"Invalid lattice: expected 0 or 3 vectors, got {len(lattice)}"
            )

        axes = None
        if lattice is not None:
            abc = np.array(lattice)
            raw = [
                (abc[i] / n, color, label, n)
                for i, (color, label) in enumerate(
                    zip(self._axis_cfg.colors, ["a", "b", "c"])
                )
                if (n := np.linalg.norm(abc[i])) > 1e-12
            ]
            if raw:
                max_norm = max(n for _, _, _, n in raw)
                scale = arrow_length / max_norm
                axes = [(d, c, lbl, n * scale) for d, c, lbl, n in raw]

        if axes is None:
            dirs = [
                np.array([1.0, 0.0, 0.0]),
                np.array([0.0, 1.0, 0.0]),
                np.array([0.0, 0.0, 1.0]),
            ]
            axes = [
                (d, c, lbl, arrow_length)
                for d, c, lbl in zip(dirs, self._axis_cfg.colors, ["x", "y", "z"])
            ]

        for d, c, label_text, length in axes:
            tip = origin + (length + label_offset) * d
            label = visuals.Text(
                label_text,
                pos=tip,
                color=c.rgba,
                font_size=self._axis_cfg.label_font_size,
                parent=parent,
                anchor_x="center",
                anchor_y="center",
            )
            self.axis_labels.append(label)

        for d, c, _label_text, length in axes:
            self._add_small_arrow(
                origin,
                d,
                length=length,
                color=c.rgba,
                parent=parent,
            )

        self.axis_view.camera.distance = self._camera_cfg.axis_camera_distance
        self.axis_view.camera.view_changed()

    # ── HUD ──────────────────────────────────────────────────────

    def _create_hud_view(self) -> ViewBox:
        hud_view = ViewBox(parent=self.canvas.scene)
        hud_view.interactive = False
        hud_view.camera = scene.cameras.PanZoomCamera()
        cfg = self._camera_cfg
        self._hud_texts = [
            visuals.Text(
                "",
                font_size=cfg.hud_font_size,
                color=(*cfg.hud_color.rgb, cfg.hud_alpha),
                parent=hud_view.scene,
                anchor_x="left",
                anchor_y="bottom",
            )
            for _ in range(4)
        ]
        self.canvas.events.resize.connect(self._layout_hud)
        return hud_view

    def _layout_hud(self, event=None):
        if self._hud_view is None:
            return
        w, h = self.canvas.size
        cfg = self._camera_cfg
        margin = cfg.hud_margin
        font_size = cfg.hud_font_size
        linespace = cfg.hud_linespace
        self._hud_view.pos = (0, 0)
        self._hud_view.size = (w, h)
        self._hud_view.camera.rect = (0, 0, w, h)
        for i, t in enumerate(self._hud_texts):
            t.pos = (margin, h - margin - i * (font_size + linespace))

    def _update_hud(self, event=None):
        if not self._hud_visible or self._hud_view is None:
            return
        cam = self.view.camera
        azi, ele = self._quaternion_to_ae(cam._quaternion)
        lines = [
            f"rot: az {azi:.1f}°, el {ele:.1f}°",
            f"fov: {cam.fov:.0f}°",
            f"dist: {cam.distance:.2f} Å",
            f"ctr: [{cam.center[0]:.2f}, {cam.center[1]:.2f}, {cam.center[2]:.2f}] Å",
        ]
        for t, text in zip(self._hud_texts, lines):
            t.text = text

    def toggle_hud(self):
        self._hud_visible = not self._hud_visible
        self._hud_view.visible = self._hud_visible
        if self._hud_visible:
            self._layout_hud()
            self._update_hud()
        self.canvas.update()

    # ── Quaternion helpers ───────────────────────────────────────

    @staticmethod
    def _quaternion_to_ae(q):
        R = np.array(q.get_matrix())[:3, :3]
        forward = -R[:, 2]
        norm = np.linalg.norm(forward)
        if norm < 1e-12:
            return 0.0, 0.0
        azimuth = np.degrees(np.arctan2(forward[0], forward[1]))
        elevation = np.degrees(np.arcsin(forward[2] / norm))
        return azimuth, elevation

    @staticmethod
    def _build_quaternion(azimuth, elevation):
        az = np.radians(azimuth)
        el = np.radians(elevation)
        f = np.array(
            [
                np.sin(az) * np.cos(el),
                np.cos(az) * np.cos(el),
                np.sin(el),
            ]
        )
        default = np.array([0.0, 0.0, -1.0])
        cos_angle = np.dot(default, f)
        if cos_angle > 0.9999:
            return Quaternion()
        if cos_angle < -0.9999:
            return Quaternion(0.0, 1.0, 0.0, 0.0)
        axis = np.cross(default, f)
        axis = axis / np.linalg.norm(axis)
        angle = np.arccos(cos_angle)
        return Quaternion.create_from_axis_angle(angle, axis[0], axis[1], axis[2])
