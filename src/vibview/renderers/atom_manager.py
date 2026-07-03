"""Manages atom sphere visuals."""

import numpy as np
from vispy import scene
from vispy.geometry import MeshData, create_sphere
from vispy.scene import visuals

from vibview.renderers._geometry import get_basis_properties


class AtomManager:
    """Creates, positions, and toggles atom sphere meshes."""

    def __init__(self, config, view_scene):
        self.config = config
        self.view_scene = view_scene
        self.camera = None
        self.visuals = []

    def set_camera(self, camera):
        self.camera = camera

    def clear(self):
        for s in self.visuals:
            s.parent = None
        self.visuals.clear()

    def add(self, pos, radius, color):
        cfg = self.config.rendering
        sphere = visuals.Sphere(
            radius=radius,
            parent=self.view_scene,
            method="ico",
            subdivisions=cfg.subdivisions,
            color=color.rgba,
            shading=cfg.effective_shading,
        )
        if self.camera:
            self.camera.apply_shading_filter(sphere)
        sphere.transform = scene.transforms.STTransform(translate=pos)
        self.visuals.append(sphere)

    def set_visibility(self, visible):
        for s in self.visuals:
            s.visible = visible

    def apply_positions(self, positions):
        for i in range(len(self.visuals)):
            self.visuals[i].transform.translate = positions[i]

    def get_radii_and_colors(self, structure, is_supercell, eq_xyz):
        basis_radii, basis_colors = get_basis_properties(structure, self.config)
        n_basis = len(basis_radii)

        basis_radii_f32 = basis_radii.astype(np.float32)
        basis_colors_rgba = np.empty((n_basis, 4), dtype=np.float32)
        for ai, c in enumerate(basis_colors):
            basis_colors_rgba[ai] = c.rgba

        n_total = len(eq_xyz)
        if is_supercell:
            n_cells = n_total // n_basis
            radii = np.tile(basis_radii_f32, n_cells)
            colors_rgba = np.tile(basis_colors_rgba, (n_cells, 1))
        else:
            radii = basis_radii_f32.copy()
            colors_rgba = basis_colors_rgba.copy()
        return radii, colors_rgba

    def build_merged_mesh(self, positions, radii, colors_rgba, subdivisions, parent):
        base = create_sphere(radius=1.0, method="ico", subdivisions=subdivisions)
        base_verts = base.get_vertices().astype(np.float32)
        base_faces = base.get_faces().astype(np.uint32)
        n_base = len(base_verts)
        n_atoms = len(positions)
        n_faces = len(base_faces)

        all_verts = np.empty((n_atoms * n_base, 3), dtype=np.float32)
        all_faces = np.empty((n_atoms * n_faces, 3), dtype=np.uint32)
        all_colors = np.empty((n_atoms * n_base, 4), dtype=np.float32)

        for i in range(n_atoms):
            si = i * n_base
            fi = i * n_faces
            all_verts[si : si + n_base] = base_verts * radii[i] + positions[i]
            all_faces[fi : fi + n_faces] = base_faces + si
            all_colors[si : si + n_base] = colors_rgba[i]

        mesh_data = MeshData(
            vertices=all_verts, faces=all_faces, vertex_colors=all_colors
        )
        mesh = visuals.Mesh(
            meshdata=mesh_data,
            parent=parent,
            shading=self.config.rendering.effective_shading,
        )
        if self.camera:
            self.camera.apply_shading_filter(mesh)
        return mesh
