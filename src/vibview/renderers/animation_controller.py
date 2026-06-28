"""Animation frame generation, caching, and playback."""

from vispy import app

from vibview.core import generate_frames
from vibview.renderers.export import render_frames


class AnimationController:
    """Manages frame generation, pre-built merged meshes, and timer playback."""

    def __init__(self, structure, config, scene_builder, view_scene):
        self.structure = structure
        self.scene_builder = scene_builder
        self.view_scene = view_scene
        self.fps = config.animation.fps
        self.period = config.animation.period

        self.frames = None
        self.frame_idx = 0
        self.timer = None
        self._merged_atom_meshes = []
        self._merged_bond_meshes = []
        self._frames_cache = {}

    @property
    def frames_per_cycle(self):
        return max(int(round(self.fps * self.period)), 2)

    def start(self, mode_index, amplitude, qpoint_index, supercell):
        self.stop()

        key = (
            mode_index,
            amplitude,
            supercell,
            self.frames_per_cycle,
            qpoint_index,
        )
        cached = self._frames_cache.get(key)
        if cached is not None:
            self.frames = cached
        else:
            self.frames = self.generate_frame_positions(
                mode_index,
                amplitude,
                self.frames_per_cycle,
                supercell=supercell,
            )
            self._frames_cache[key] = self.frames
        self.frame_idx = 0
        self._build_merged_frames()
        self.scene_builder.apply_positions(self.frames[0])
        self.timer = app.Timer(
            interval=1 / self.fps,
            connect=self._tick,
            start=True,
        )

    def stop(self):
        if self.timer is not None and self.timer.running:
            self.timer.stop()

    def _tick(self, event):
        if self.frames is None:
            return
        prev = self.frame_idx
        self.frame_idx = (self.frame_idx + 1) % len(self.frames)
        if self._merged_atom_meshes:
            self._merged_atom_meshes[prev].visible = False
            self._merged_bond_meshes[prev].visible = False
            self._merged_atom_meshes[self.frame_idx].visible = True
            self._merged_bond_meshes[self.frame_idx].visible = True
        else:
            self.scene_builder.apply_positions(self.frames[self.frame_idx])

    def _build_merged_frames(self):
        self._destroy_merged_meshes()
        if not len(self.frames):
            return

        sb = self.scene_builder
        radii, colors_rgba = sb.atoms.get_radii_and_colors(
            self.structure, sb.is_supercell, sb.get_equilibrium_xyz()
        )
        parent = self.view_scene
        n_frames = len(self.frames)
        bond_indices = sb.bonds.indices

        for fi in range(n_frames):
            positions = self.frames[fi]
            atom_mesh = sb.atoms.build_merged_mesh(
                positions,
                radii,
                colors_rgba,
                sb.config.rendering.subdivisions,
                parent,
            )
            bond_mesh = sb.bonds.build_merged_mesh(
                bond_indices,
                positions,
                sb.config.rendering.bond_radius,
                parent,
            )
            atom_mesh.visible = fi == 0
            bond_mesh.visible = fi == 0
            self._merged_atom_meshes.append(atom_mesh)
            self._merged_bond_meshes.append(bond_mesh)

        for s in sb.atoms.visuals:
            s.visible = False
        for b in sb.bonds.visuals:
            b.visible = False

    def _destroy_merged_meshes(self):
        for m in self._merged_atom_meshes + self._merged_bond_meshes:
            m.parent = None
        self._merged_atom_meshes.clear()
        self._merged_bond_meshes.clear()

    def clear_frame_cache(self):
        self._frames_cache.clear()

    def generate_frame_positions(
        self, mode_index, amplitude, n_frames, cycles=1, supercell=None
    ):
        return generate_frames(
            self.structure,
            mode_index,
            amplitude=amplitude,
            frames=n_frames,
            cycles=cycles,
            supercell=supercell,
        )

    def show_base_visuals(self):
        """Restore visibility of base atom/bond visuals (hides merged meshes)."""
        self._destroy_merged_meshes()
        for s in self.scene_builder.atoms.visuals:
            s.visible = True
        for b in self.scene_builder.bonds.visuals:
            b.visible = True

    def render_export_frames(
        self, canvas, export_frame_positions, progress_callback=None
    ):
        timer_was_running = self.timer is not None and self.timer.running
        saved_frames = self.frames
        saved_frame_idx = self.frame_idx
        self.stop()

        had_merged = bool(self._merged_atom_meshes)
        if had_merged:
            self._destroy_merged_meshes()
            self.show_base_visuals()

        try:
            self.scene_builder.apply_positions(export_frame_positions[0])
            canvas.render()
            images = render_frames(
                canvas,
                export_frame_positions,
                apply_frame_fn=lambda i: self.scene_builder.apply_positions(
                    export_frame_positions[i]
                ),
                progress_callback=progress_callback,
            )
        finally:
            if had_merged:
                self._build_merged_frames()
                for m in self._merged_atom_meshes:
                    m.visible = False
                for m in self._merged_bond_meshes:
                    m.visible = False
                self._merged_atom_meshes[self.frame_idx].visible = True
                self._merged_bond_meshes[self.frame_idx].visible = True
            if saved_frames is not None:
                self.frames = saved_frames
                self.frame_idx = saved_frame_idx
                self.scene_builder.apply_positions(self.frames[self.frame_idx])
            if timer_was_running:
                self.timer.start()

        return images
