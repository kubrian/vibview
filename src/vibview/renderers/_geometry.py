"""Shared geometry utilities for scene construction."""

import numpy as np
from vispy.geometry import MeshData, create_cone, create_cylinder
from vispy.scene import transforms, visuals


def get_basis_properties(structure, config):
    """Compute radius and color for each atom in the basis.

    Args:
        structure: The structure to compute properties for.
        config: Application configuration with element data.

    Returns:
        basis_radii: (n_basis,) array of radii (scaled by ``radii_scale``).
        basis_colors: (n_basis,) array of color strings.
    """
    cfg = config.rendering
    n_basis = len(structure.atoms)
    basis_radii = np.empty(n_basis, dtype=np.float64)
    basis_colors = np.empty(n_basis, dtype=object)
    for ai, a in enumerate(structure.atoms):
        basis_radii[ai] = config.elements[a.symbol].radius * cfg.radii_scale
        basis_colors[ai] = config.elements[a.symbol].color
    return basis_radii, basis_colors


def build_cylinder_mesh(segments, radius, color, parent, shading, cols):
    """Build a merged visuals.Mesh from cylinder segments.

    Args:
        segments: (start, end) point pairs for each cylinder segment.
        radius: Cylinder radius.
        color: Mesh color.
        parent: Parent scene node.
        shading: Shading mode (default None).
        cols: Cylinder circumference segments (default 8).

    Returns:
        The merged cylinder mesh.
    """
    base = create_cylinder(rows=2, cols=cols, radius=[1.0, 1.0], length=1.0)
    base_verts = base.get_vertices().astype(np.float32)
    base_faces = base.get_faces().astype(np.uint32)
    n_base = len(base_verts)
    n_faces = len(base_faces)

    n_segments = len(segments)
    all_verts = np.empty((n_segments * n_base, 3), dtype=np.float32)
    all_faces = np.empty((n_segments * n_faces, 3), dtype=np.uint32)

    valid = 0
    for p1, p2 in segments:
        mid = (p1 + p2) * 0.5
        d = p2 - p1
        length = np.linalg.norm(d)
        if length < 1e-12:
            continue

        verts = base_verts.copy()
        verts[:, 0] *= radius
        verts[:, 1] *= radius
        verts[:, 2] = (verts[:, 2] - 0.5) * length
        verts = rotate_from_z(verts, d / length)
        verts += mid

        vi = valid * n_base
        fi = valid * n_faces
        all_verts[vi : vi + n_base] = verts
        all_faces[fi : fi + n_faces] = base_faces + vi
        valid += 1

    if valid < n_segments:
        all_verts = all_verts[: valid * n_base]
        all_faces = all_faces[: valid * n_faces]

    mesh_data = MeshData(vertices=all_verts, faces=all_faces)
    return visuals.Mesh(
        meshdata=mesh_data,
        color=color,
        parent=parent,
        shading=shading,
    )


def _rotation_matrix_from_z(direction):
    """Return a 3x3 rotation matrix that maps +z to *direction*.

    Args:
        direction: Target direction vector (will be normalised).

    Returns:
        3x3 rotation matrix.
    """
    z = np.array([0.0, 0.0, 1.0])
    cos_a = np.dot(z, direction)
    if abs(cos_a) < 0.99999:
        axis = np.cross(z, direction)
        axis_norm = np.linalg.norm(axis)
        if axis_norm > 1e-12:
            axis /= axis_norm
        angle = np.arccos(np.clip(cos_a, -1.0, 1.0))
        c = np.cos(angle)
        s = np.sin(angle)
        t = 1 - c
        x, y, z_ = axis
        return np.array(
            [
                [t * x * x + c, t * x * y - s * z_, t * x * z_ + s * y],
                [t * x * y + s * z_, t * y * y + c, t * y * z_ - s * x],
                [t * x * z_ - s * y, t * y * z_ + s * x, t * z_ * z_ + c],
            ]
        )
    elif cos_a < -0.99999:
        # 180° rotation about x-axis (proper rotation, det=+1)
        return np.array([[1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [0.0, 0.0, -1.0]])
    return np.eye(3)


def rotate_transform_from_z(direction):
    """Return a vispy MatrixTransform that rotates from +z to *direction*.

    Args:
        direction: Target direction vector (will be normalised).

    Returns:
        vispy MatrixTransform.
    """
    R = _rotation_matrix_from_z(direction)
    tr = transforms.MatrixTransform()
    m = np.eye(4)
    m[:3, :3] = R.T
    tr.matrix = m
    return tr


def rotate_from_z(verts: np.ndarray, direction: np.ndarray) -> np.ndarray:
    """Rotate vertices from the +z axis to *direction*.

    Args:
        verts: (N, 3) array of vertices.
        direction: Target direction vector (will be normalised).

    Returns:
        Rotated (N, 3) array.
    """
    R = _rotation_matrix_from_z(direction)
    return verts @ R.T


def build_arrow_visuals(
    origin,
    shaft_end,
    direction,
    shaft_radius,
    tip_radius,
    tip_length,
    color,
    parent,
    shading,
    cone_offset,
):
    """Create Tube shaft + cone tip visuals for an arrow.

    Args:
        origin: Start point of the shaft (3,).
        shaft_end: End point of the shaft — cone base sits here (3,).
        direction: Unit vector pointing along the arrow (3,).
        shaft_radius: Shaft tube radius.
        tip_radius: Cone tip radius.
        tip_length: Cone tip length.
        color: Mesh colour.
        parent: Parent scene node.
        shading: Shading mode (default None).
        cone_offset: Backward shift of the cone along *direction* to overlap shaft.

    Returns:
        tuple of (tube, cone) visuals.
    """
    tube = visuals.Tube(
        points=np.array([origin, shaft_end]),
        radius=shaft_radius,
        color=color,
        parent=parent,
        shading=shading,
    )
    mesh_data = create_cone(cols=20, radius=tip_radius, length=tip_length)
    cone = visuals.Mesh(
        meshdata=mesh_data,
        color=color,
        parent=parent,
        shading=shading,
    )
    tr = rotate_transform_from_z(direction)
    tr.translate(shaft_end - cone_offset * direction)
    cone.transform = tr
    return tube, cone
