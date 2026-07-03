"""Manages mode-specific overlay visuals (arrows, wireframes)."""

import numpy as np
from vispy.color import Color
from vispy.scene import visuals

from vibview.core import generate_frames
from vibview.renderers._geometry import build_arrow_visuals


class ModeOverlayManager:
    """Creates and manages mode-specific overlay visuals (arrows, wireframes)."""

    def __init__(self, config, view_scene):
        self.config = config
        self.view_scene = view_scene
        self.camera = None
        self.visuals = []

    def set_camera(self, camera):
        self.camera = camera

    def clear(self):
        for a in self.visuals:
            a.parent = None
        self.visuals.clear()

    def _get_displacements(
        self, structure, mode_index, amplitude, supercell, eq_xyz
    ) -> np.ndarray:
        """Displacement vectors at t=0 for every atom in the (super)cell.

        Returns displacement vectors (not positions) of shape ``(N, 3)``
        where ``N`` is ``n_atoms`` for single-cell or ``n_cells * n_atoms``
        for supercell.
        """
        frames = generate_frames(
            structure,
            mode_index,
            frames=1,
            amplitude=amplitude,
            cycles=1,
            supercell=supercell,
        )
        return frames[0] - np.asarray(eq_xyz, dtype=np.float64)

    def build_arrows(
        self,
        structure,
        mode_index,
        amplitude,
        eq_xyz,
        supercell,
    ):
        disps = self._get_displacements(
            structure, mode_index, amplitude, supercell, eq_xyz
        )

        cfg = self.config.rendering
        scfg = self.config.static
        shaft_radius = cfg.bond_radius * scfg.arrow_shaft_radius_factor
        tip_radius = shaft_radius * scfg.arrow_tip_radius_factor

        for i in range(len(eq_xyz)):
            start = eq_xyz[i]
            vec = disps[i]
            length = np.linalg.norm(vec)
            if length < 1e-6:
                continue

            direction = vec / length
            tip_length = min(
                length * scfg.arrow_tip_length_factor,
                scfg.arrow_tip_length_max_factor * amplitude,
            )
            shaft_end = start + (length - tip_length) * direction

            tube, cone = build_arrow_visuals(
                start,
                shaft_end,
                direction,
                shaft_radius,
                tip_radius,
                tip_length,
                scfg.arrow_color,
                self.view_scene,
                shading=cfg.effective_shading,
                cone_offset=0.0,
            )
            if self.camera:
                self.camera.apply_shading_filter(tube)
                self.camera.apply_shading_filter(cone)
            self.visuals.append(tube)
            self.visuals.append(cone)

    def build_wireframe(
        self,
        structure,
        mode_index,
        amplitude,
        eq_xyz,
        bond_indices,
        supercell,
    ):
        disps = self._get_displacements(
            structure, mode_index, amplitude, supercell, eq_xyz
        )
        displaced_xyz = eq_xyz + disps

        cfg = self.config.overlay
        br = self.config.rendering.bond_radius

        eq_c = Color(cfg.eq_color)
        eq_rgba = (*eq_c.rgb, cfg.eq_alpha)
        for i, j in bond_indices:
            tube = visuals.Tube(
                points=np.array([eq_xyz[i], eq_xyz[j]]),
                radius=br * cfg.eq_radius_multiplier,
                color=eq_rgba,
                parent=self.view_scene,
                shading=None,
            )
            tube.set_gl_state(preset="translucent", depth_test=False)
            self.visuals.append(tube)

        dc = Color(cfg.disp_color)
        disp_rgba = (*dc.rgb, cfg.disp_alpha)
        for i, j in bond_indices:
            tube = visuals.Tube(
                points=np.array([displaced_xyz[i], displaced_xyz[j]]),
                radius=br * cfg.disp_radius_multiplier,
                color=disp_rgba,
                parent=self.view_scene,
                shading=None,
            )
            tube.set_gl_state(preset="translucent", depth_test=False)
            self.visuals.append(tube)
