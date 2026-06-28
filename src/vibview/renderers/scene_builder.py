"""Scene visual construction — thin orchestrator over focused managers.

Owns supercell logic and the high-level build/rebuild API.
Consumers access sub-managers directly for lower-level operations.
"""

import numpy as np

from vibview.core import _cell_offsets
from vibview.renderers._geometry import get_basis_properties
from vibview.renderers.atom_manager import AtomManager
from vibview.renderers.bond_manager import BondManager
from vibview.renderers.lattice_manager import LatticeManager
from vibview.renderers.mode_overlay_manager import ModeOverlayManager


class SceneBuilder:
    """Orchestrates scene construction across sub-managers (atoms, bonds, lattice, overlays)."""

    def __init__(self, structure, config, view_scene):
        self.structure = structure
        self.config = config
        self.camera = None

        self.atoms = AtomManager(config, view_scene)
        self.bonds = BondManager(config, view_scene)
        self.lattice = LatticeManager(config, view_scene)
        self.overlay = ModeOverlayManager(config, view_scene)

        self._supercell_xyz = None
        self._supercell_bond_indices = None
        self._supercell_cache = {}

        self.supercell = None

    @property
    def is_supercell(self):
        return self._supercell_xyz is not None

    def set_camera(self, camera):
        self.camera = camera
        self.atoms.set_camera(camera)
        self.bonds.set_camera(camera)
        self.overlay.set_camera(camera)

    def get_equilibrium_xyz(self):
        if self.is_supercell:
            return self._supercell_xyz
        return self.structure.xyz

    def _compute_basis_properties(self):
        return get_basis_properties(self.structure, self.config)

    def ensure_supercell(self):
        sc = self.supercell
        if sc is None or sc == (1, 1, 1):
            self._supercell_xyz = None
            self._supercell_bond_indices = None
            return

        lattice = self.structure.data.lattice
        if lattice is None:
            raise ValueError(
                "Supercell expansion requires lattice vectors; "
                "use supercell=None for molecules (non-periodic structures)"
            )

        cached = self._supercell_cache.get(sc)
        if cached is not None:
            self._supercell_xyz, self._supercell_bond_indices = cached
            return

        lattice = np.array(lattice, dtype=np.float64)
        cell_offsets = _cell_offsets(sc)
        cell_offsets_cart = cell_offsets @ lattice

        xyz = np.asarray(self.structure.xyz, dtype=np.float64)
        expanded = xyz[np.newaxis, :, :] + cell_offsets_cart[:, np.newaxis, :]
        expanded = expanded.reshape(-1, 3)
        self._supercell_xyz = expanded

        n_basis = len(self.structure.atoms)
        n_cells = expanded.shape[0] // n_basis

        basis_radii, _ = self._compute_basis_properties()

        basis_pos = np.asarray(self.structure.xyz, dtype=np.float64)
        d2 = np.sum(
            (basis_pos[:, np.newaxis, :] - basis_pos[np.newaxis, :, :]) ** 2,
            axis=2,
        )
        cutoff2 = (
            basis_radii[:, np.newaxis]
            + basis_radii[np.newaxis, :]
            + self.config.rendering.bond_tolerance
        ) ** 2

        upper = np.arange(n_basis)[:, np.newaxis] < np.arange(n_basis)[np.newaxis, :]
        i_idx, j_idx = np.where((d2 < cutoff2) & upper)

        cell_offsets_arr = np.arange(n_cells, dtype=np.int64) * n_basis
        all_i = (i_idx[np.newaxis, :] + cell_offsets_arr[:, np.newaxis]).ravel()
        all_j = (j_idx[np.newaxis, :] + cell_offsets_arr[:, np.newaxis]).ravel()

        self._supercell_bond_indices = list(zip(all_i.tolist(), all_j.tolist()))
        self._supercell_cache[sc] = (
            self._supercell_xyz,
            self._supercell_bond_indices,
        )

    def clear_all_visuals(self):
        self.atoms.clear()
        self.bonds.clear()
        self.overlay.clear()
        self.lattice.clear()

    def build_base(self):
        self.clear_all_visuals()
        self.ensure_supercell()

        basis_radii, basis_colors = self._compute_basis_properties()
        n_basis = len(basis_radii)

        if self.is_supercell:
            n_cells = self._supercell_xyz.shape[0] // n_basis
            for ci in range(n_cells):
                for ai in range(n_basis):
                    self.atoms.add(
                        self._supercell_xyz[ci * n_basis + ai],
                        basis_radii[ai],
                        basis_colors[ai],
                    )
            self.bonds.indices = list(self._supercell_bond_indices or [])
        else:
            for ai, a in enumerate(self.structure.atoms):
                self.atoms.add(a.xyz, basis_radii[ai], basis_colors[ai])
            cfg = self.config.rendering
            bond_pairs = self.structure.detect_bonds(
                tolerance=cfg.bond_tolerance,
                config=self.config,
            )
            self.bonds.indices = [(i, j) for i, j, _ in bond_pairs]

        for _ in self.bonds.indices:
            self.bonds.add_placeholder()

        self.lattice.build(self.structure.data.lattice, self.supercell)

    def rebuild_overlays(self, mode_type, mode_index, amplitude):
        self.overlay.clear()

        if mode_type == "static":
            self.atoms.set_visibility(True)
            self.bonds.set_visibility(True)
            self.overlay.build_arrows(
                self.structure,
                mode_index,
                amplitude,
                self.get_equilibrium_xyz(),
                supercell=self.supercell,
            )
        elif mode_type == "overlay":
            self.atoms.set_visibility(False)
            self.bonds.set_visibility(True)
            self.overlay.build_wireframe(
                self.structure,
                mode_index,
                amplitude,
                self.get_equilibrium_xyz(),
                self.bonds.indices,
                supercell=self.supercell,
            )
        else:
            self.atoms.set_visibility(True)
            self.bonds.set_visibility(True)

    def apply_positions(self, positions):
        self.atoms.apply_positions(positions)
        self.bonds.update_transforms(positions)
