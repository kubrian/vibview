"""Configuration loading, merging, and typed access."""

from collections.abc import Sequence
from dataclasses import dataclass, field, fields
from functools import cache
from importlib.resources import files as resource_files
from pathlib import Path
from typing import Any

import yaml

USER_CONFIG_PATH = Path.home() / ".config" / "vibview" / "config.yaml"

_SUBDIVISION_PRESETS: dict[str, int] = {
    "low": 1,
    "medium": 2,
    "high": 4,
}


@cache
def _load_defaults() -> dict[str, Any]:
    """Lazy-load default configuration from the bundled defaults.yaml."""
    path = resource_files("vibview.data").joinpath("defaults.yaml")
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


@dataclass
class RenderingConfig:
    """Configuration for 3D rendering appearance.

    ``quality`` drives the performance-related presets (subdivision
    level).  ``subdivisions`` is a read-only property derived from the
    selected quality level.

    ``shading`` controls the lighting model applied to scene visuals:
    ``"flat"`` for per-face Phong (facetted), ``"smooth"`` for per-vertex
    Phong (smooth).  When ``None`` (the default) the effective value is
    derived from quality: ``"smooth"`` on ``high``, ``"flat"`` on
    ``low``/``medium``.
    """

    quality: str
    shading: str | None
    background_color: str
    atom_color: str
    atom_radius: float
    radii_scale: float
    bond_color: str
    bond_radius: float
    bond_tolerance: float

    def __post_init__(self):
        self.quality = self.quality.lower()
        if self.quality not in _SUBDIVISION_PRESETS:
            raise ValueError(
                f"quality must be 'low', 'medium', or 'high', got {self.quality!r}"
            )
        if self.shading is not None and self.shading not in ("flat", "smooth"):
            raise ValueError(
                f"shading must be None, 'flat', or 'smooth', got {self.shading!r}"
            )
        if self.atom_radius <= 0:
            raise ValueError(f"atom_radius must be positive, got {self.atom_radius}")
        if self.radii_scale <= 0:
            raise ValueError(f"radii_scale must be positive, got {self.radii_scale}")
        if self.bond_radius <= 0:
            raise ValueError(f"bond_radius must be positive, got {self.bond_radius}")
        if self.bond_tolerance < 0:
            raise ValueError(
                f"bond_tolerance must be non-negative, got {self.bond_tolerance}"
            )

    @property
    def subdivisions(self) -> int:
        return _SUBDIVISION_PRESETS[self.quality]

    @property
    def effective_shading(self) -> str:
        if self.shading is not None:
            return self.shading
        return "smooth" if self.quality == "high" else "flat"


@dataclass
class AnimationConfig:
    """Configuration for animation behaviour."""

    fps: int
    period: float
    default_amplitude: float
    default_mode: str

    def __post_init__(self):
        if self.fps <= 0:
            raise ValueError(f"fps must be positive, got {self.fps}")
        if self.period <= 0:
            raise ValueError(f"period must be positive, got {self.period}")
        if self.default_amplitude <= 0:
            raise ValueError(
                f"default_amplitude must be positive, got {self.default_amplitude}"
            )


@dataclass
class LatticeConfig:
    """Configuration for unit-cell lattice box appearance."""

    color: str
    width: float
    alpha: float

    def __post_init__(self):
        if self.width <= 0:
            raise ValueError(f"width must be positive, got {self.width}")
        if not 0 <= self.alpha <= 1:
            raise ValueError(f"alpha must be between 0 and 1, got {self.alpha}")


@dataclass
class StaticOverlayConfig:
    """Configuration for static-mode arrow overlays."""

    amplitude: float
    arrow_color: str
    arrow_shaft_radius_factor: float
    arrow_tip_radius_factor: float
    arrow_tip_length_factor: float
    arrow_tip_length_max_factor: float


@dataclass
class OverlayConfig:
    """Configuration for overlay-mode wireframe appearance."""

    amplitude: float
    eq_color: str
    eq_alpha: float
    eq_radius_multiplier: float
    disp_color: str
    disp_alpha: float
    disp_radius_multiplier: float

    def __post_init__(self):
        if not 0 <= self.eq_alpha <= 1:
            raise ValueError(f"eq_alpha must be between 0 and 1, got {self.eq_alpha}")
        if not 0 <= self.disp_alpha <= 1:
            raise ValueError(
                f"disp_alpha must be between 0 and 1, got {self.disp_alpha}"
            )
        if self.eq_radius_multiplier < 0:
            raise ValueError(
                f"eq_radius_multiplier must be non-negative, got {self.eq_radius_multiplier}"
            )
        if self.disp_radius_multiplier < 0:
            raise ValueError(
                f"disp_radius_multiplier must be non-negative, got {self.disp_radius_multiplier}"
            )


@dataclass
class LightingConfig:
    """Configuration for scene lighting parameters."""

    ambient: tuple[float, float, float, float]
    diffuse: tuple[float, float, float, float]
    specular: tuple[float, float, float, float]
    shininess: float

    def __post_init__(self):
        for attr in ("ambient", "diffuse", "specular"):
            val = getattr(self, attr)
            if isinstance(val, Sequence) and not isinstance(val, tuple):
                setattr(self, attr, tuple(val))
            val = getattr(self, attr)
            if len(val) != 4:
                raise ValueError(f"{attr} must have 4 elements, got {len(val)}")
        if self.shininess <= 0:
            raise ValueError(f"shininess must be positive, got {self.shininess}")


@dataclass
class CameraConfig:
    """Configuration for camera and viewport defaults."""

    fov: float
    fill_factor: float
    min_distance: float
    default_window_size: tuple[int, int]
    axis_view_size: int
    axis_view_padding: int
    axis_camera_distance: float
    axis_camera_fov: float

    def __post_init__(self):
        if isinstance(self.default_window_size, list):
            self.default_window_size = tuple(self.default_window_size)
        if len(self.default_window_size) != 2:
            raise ValueError(
                f"default_window_size must have 2 elements, got {len(self.default_window_size)}"
            )
        if self.fill_factor <= 0 or self.fill_factor > 1:
            raise ValueError(f"fill_factor must be in (0, 1], got {self.fill_factor}")
        if self.fov <= 0 or self.fov >= 180:
            raise ValueError(f"fov must be between 0 and 180, got {self.fov}")


@dataclass
class AxisConfig:
    """Configuration for coordinate axis indicator appearance."""

    shaft_radius: float
    lattice_shaft_radius: float
    tip_length_factor: float
    tip_length_max: float
    tip_radius_factor: float
    colors_lattice: tuple[str, str, str]
    colors_cartesian: tuple[str, str, str]
    arrow_length: float
    label_offset: float
    label_font_size: int

    def __post_init__(self):
        for attr in ("colors_lattice", "colors_cartesian"):
            val = getattr(self, attr)
            if isinstance(val, list):
                setattr(self, attr, tuple(val))
            if len(getattr(self, attr)) != 3:
                raise ValueError(
                    f"{attr} must have 3 elements, got {len(getattr(self, attr))}"
                )


@dataclass
class DisplayConfig:
    """Configuration for display metadata (units, colours, overlays)."""

    frequency_units: str
    imaginary_color: str
    show_axis: bool
    supercell: tuple[int, int, int]

    def __post_init__(self):
        if isinstance(self.supercell, list):
            self.supercell = tuple(self.supercell)
        if len(self.supercell) != 3 or any(n < 1 for n in self.supercell):
            raise ValueError(
                f"supercell must be a tuple of 3 positive ints, got {self.supercell}"
            )


@dataclass
class ExportConfig:
    """Configuration for animation export."""

    gif_fps: int
    mp4_fps: int
    cycles: int


@dataclass
class ElementConfig:
    """Properties of a chemical element — radius, colour, mass."""

    radius: float
    color: str
    mass: float

    def __post_init__(self):
        if not isinstance(self.radius, (int, float)):
            raise TypeError(
                f"ElementConfig.radius must be int or float, got {type(self.radius).__name__}"
            )
        if not isinstance(self.color, str):
            raise TypeError(
                f"ElementConfig.color must be str, got {type(self.color).__name__}"
            )
        if not isinstance(self.mass, (int, float)):
            raise TypeError(
                f"ElementConfig.mass must be int or float, got {type(self.mass).__name__}"
            )


@dataclass
class Config:
    """Top-level configuration — one field per YAML section."""

    rendering: RenderingConfig
    animation: AnimationConfig
    lattice: LatticeConfig
    static: StaticOverlayConfig
    overlay: OverlayConfig
    lighting: LightingConfig
    camera: CameraConfig
    axis: AxisConfig
    display: DisplayConfig
    export: ExportConfig
    elements: dict[str, ElementConfig] = field(default_factory=dict, repr=False)

    @classmethod
    def defaults(cls) -> "Config":
        """Create a Config populated from the bundled defaults.yaml."""
        return cls.from_dict(_load_defaults())

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Config":
        section_types = {f.name: f.type for f in fields(cls) if f.name != "elements"}
        kwargs: dict[str, Any] = {}
        for key, field_cls in section_types.items():
            val = d.get(key, {})
            if not isinstance(val, dict):
                raise ValueError(
                    f"Config section {key!r} must be a mapping, got {type(val).__name__}: {val!r}"
                )
            known = set(field_cls.__dataclass_fields__)
            filtered = {k: v for k, v in val.items() if k in known}
            kwargs[key] = field_cls(**filtered)
        elements_raw = d.get("elements", {})
        kwargs["elements"] = {
            symbol: ElementConfig(**props) for symbol, props in elements_raw.items()
        }
        return cls(**kwargs)

    @classmethod
    def load(cls, session_config: Path | None = None) -> "Config":
        """Config cascade: session config > user config > defaults."""
        cfg = dict(_load_defaults())

        if USER_CONFIG_PATH.exists():
            with open(USER_CONFIG_PATH, encoding="utf-8") as f:
                try:
                    user_cfg = yaml.safe_load(f) or {}
                except yaml.YAMLError as e:
                    raise ValueError(f"Failed to parse {USER_CONFIG_PATH}: {e}") from e
                cfg = _deep_merge(cfg, user_cfg)

        if session_config and session_config.exists():
            with open(session_config, encoding="utf-8") as f:
                try:
                    session_cfg = yaml.safe_load(f) or {}
                except yaml.YAMLError as e:
                    raise ValueError(f"Failed to parse {session_config}: {e}") from e
                cfg = _deep_merge(cfg, session_cfg)

        return cls.from_dict(cfg)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = base.copy()
    for key, val in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(val, dict):
            merged[key] = _deep_merge(merged[key], val)
        else:
            merged[key] = val
    return merged
