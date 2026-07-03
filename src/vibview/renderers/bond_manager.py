"""Manages bond tube visuals and transforms."""

import numpy as np
from vispy import scene
from vispy.scene import visuals

from vibview.renderers._geometry import build_cylinder_mesh, rotate_transform_from_z


class BondManager:
    """Creates, transforms, and toggles bond tube meshes."""

    def __init__(self, config, view_scene):
        self.config = config
        self.view_scene = view_scene
        self.camera = None
        self.visuals = []
        self.transforms = []
        self.indices = []

    def set_camera(self, camera):
        self.camera = camera

    def clear(self):
        for b in self.visuals:
            b.parent = None
        self.visuals.clear()
        self.transforms.clear()
        self.indices.clear()

    def add_bond(self):
        """Add a default-aligned tube (shaft along +z); call update_transforms to position it."""
        cfg = self.config.rendering
        tube = visuals.Tube(
            points=np.array([[0.0, 0.0, -0.5], [0.0, 0.0, 0.5]]),
            radius=cfg.bond_radius,
            color=cfg.bond_color,
            parent=self.view_scene,
            shading=cfg.effective_shading,
        )
        if self.camera:
            self.camera.apply_shading_filter(tube)
        self.visuals.append(tube)
        tr = scene.transforms.MatrixTransform()
        tube.transform = tr
        self.transforms.append(tr)

    def set_visibility(self, visible):
        for b in self.visuals:
            b.visible = visible

    def update_transforms(self, positions):
        for idx, (i, j) in enumerate(self.indices):
            p1 = positions[i]
            p2 = positions[j]
            mid = (p1 + p2) * 0.5
            d = p2 - p1
            length = np.linalg.norm(d)
            if length < 1e-12:
                length = 1.0

            tr = self.transforms[idx]
            direction = d / length
            rot = rotate_transform_from_z(direction)
            S = np.eye(4, dtype=np.float32)
            S[2, 2] = length
            tr.matrix = S @ rot.matrix
            tr.translate(mid)

    def build_merged_mesh(self, bond_indices, positions, bond_radius, parent, cols):
        segments = [(positions[i], positions[j]) for i, j in bond_indices]
        cfg = self.config.rendering
        mesh = build_cylinder_mesh(
            segments,
            bond_radius,
            cfg.bond_color,
            parent,
            shading=cfg.effective_shading,
            cols=cols,
        )
        if self.camera:
            self.camera.apply_shading_filter(mesh)
        return mesh
