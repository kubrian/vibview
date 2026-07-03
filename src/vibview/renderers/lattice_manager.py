"""Manages the unit-cell lattice box visual."""

import numpy as np

from vibview.renderers._geometry import build_cylinder_mesh


class LatticeManager:
    """Creates the unit-cell lattice box from cylinder segments."""

    def __init__(self, config, view_scene):
        self.config = config
        self.view_scene = view_scene
        self.visuals = []

    def clear(self):
        for v in self.visuals:
            v.parent = None
        self.visuals.clear()

    def build(self, lattice, supercell):
        if lattice is None:
            return
        if len(lattice) != 3:
            raise ValueError(
                f"Invalid lattice: expected 0 or 3 vectors, got {len(lattice)}"
            )

        a = np.array(lattice[0])
        b = np.array(lattice[1])
        c = np.array(lattice[2])
        nx, ny, nz = supercell if supercell is not None else (1, 1, 1)

        cfg = self.config.lattice
        lattice_color = (*cfg.color.rgb, cfg.alpha)

        segments = []
        for i in range(nx + 1):
            for j in range(ny + 1):
                for k in range(nz + 1):
                    p = i * a + j * b + k * c
                    if i < nx:
                        segments.append((p, p + a))
                    if j < ny:
                        segments.append((p, p + b))
                    if k < nz:
                        segments.append((p, p + c))

        if not segments:
            return

        mesh = build_cylinder_mesh(
            segments,
            cfg.width,
            lattice_color,
            self.view_scene,
            shading=None,
            cols=8,
        )
        self.visuals.append(mesh)
