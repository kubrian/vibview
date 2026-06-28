"""Camera and canvas management for the vispy viewer."""

import numpy as np
from vispy import scene
from vispy.scene import visuals
from vispy.scene.widgets import ViewBox

from vibview.renderers._geometry import build_arrow_visuals


class CameraController:
    """Owns the SceneCanvas, main camera, and axis sub-view.

    Handles camera setup, pan/zoom/reset, axis indicator visuals, and the
    mini axis-rotation indicator in the lower-left corner.
    """

    def __init__(self, structure, config):
        self.structure = structure
        self._lighting = config.lighting
        self._camera_cfg = config.camera
        self._axis_cfg = config.axis
        self.axis_visuals = []
        self.axis_labels = []

        center = np.mean(self.structure.xyz, axis=0)
        radii = np.linalg.norm(self.structure.xyz - center, axis=1)
        max_radius = radii.max()
        fov = config.camera.fov
        fill = config.camera.fill_factor
        cam_distance = max(
            max_radius / (fill * np.tan(np.radians(fov / 2))),
            config.camera.min_distance,
        )

        self.canvas = scene.SceneCanvas(
            show=False,
            title="VibView",
            bgcolor=config.rendering.background_color,
            size=tuple(config.camera.default_window_size),
        )
        self.view = self.canvas.central_widget.add_view()
        self.view.camera = scene.cameras.ArcballCamera(
            center=center,
            distance=cam_distance,
            fov=fov,
        )

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

    def _add_small_arrow(self, origin, direction, length, color, radius, parent=None):
        if parent is None:
            parent = self.view.scene
        direction = np.array(direction, dtype=float)
        norm = np.linalg.norm(direction)
        if norm < 1e-12:
            return
        direction = direction / norm

        tip_length = min(
            length * self._axis_cfg.tip_length_factor,
            self._axis_cfg.tip_length_max,
        )
        shaft_end = origin + (length - tip_length) * direction
        tip_radius = radius * self._axis_cfg.tip_radius_factor

        tube, cone = build_arrow_visuals(
            origin,
            shaft_end,
            direction,
            radius,
            tip_radius,
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
                (abc[i] / n, color, label, self._axis_cfg.lattice_shaft_radius, n)
                for i, (color, label) in enumerate(
                    zip(self._axis_cfg.colors_lattice, ["a", "b", "c"])
                )
                if (n := np.linalg.norm(abc[i])) > 1e-12
            ]
            if raw:
                max_norm = max(n for _, _, _, _, n in raw)
                scale = arrow_length / max_norm
                axes = [(d, c, lbl, r, n * scale) for d, c, lbl, r, n in raw]

        if axes is None:
            dirs = [
                np.array([1.0, 0.0, 0.0]),
                np.array([0.0, 1.0, 0.0]),
                np.array([0.0, 0.0, 1.0]),
            ]
            axes = [
                (d, c, lbl, self._axis_cfg.shaft_radius, arrow_length)
                for d, c, lbl in zip(
                    dirs, self._axis_cfg.colors_cartesian, ["x", "y", "z"]
                )
            ]

        for d, c, label_text, _radius, length in axes:
            tip = origin + (length + label_offset) * d
            label = visuals.Text(
                label_text,
                pos=tip,
                color=c,
                font_size=self._axis_cfg.label_font_size,
                parent=parent,
                anchor_x="center",
                anchor_y="center",
            )
            self.axis_labels.append(label)

        for d, c, _label_text, radius, length in axes:
            self._add_small_arrow(
                origin,
                d,
                length=length,
                color=c,
                radius=radius,
                parent=parent,
            )

        self.axis_view.camera.distance = self._camera_cfg.axis_camera_distance
        self.axis_view.camera.view_changed()
