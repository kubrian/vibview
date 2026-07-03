"""Tests for element config dataclass and Config element access."""

import pytest

from vibview.config import Color, Config, ElementConfig, _deep_merge, _load_defaults


class TestElementConfig:
    def test_construction(self):
        el = ElementConfig(radius=0.5, color=Color.from_hex("#000000"), mass=1.0)
        assert el.radius == 0.5
        assert el.color == Color.from_hex("#000000")
        assert el.mass == 1.0

    def test_invalid_radius_raises(self):
        with pytest.raises(TypeError, match="ElementConfig.radius must be"):
            ElementConfig(radius="big", color=Color.from_hex("#000000"), mass=1.0)

    def test_invalid_color_raises(self):
        with pytest.raises(ValueError, match="Color"):
            Color.from_hex("#xyzxyz")

    def test_invalid_mass_raises(self):
        with pytest.raises(TypeError, match="ElementConfig.mass must be"):
            ElementConfig(radius=1.0, color=Color.from_hex("#000000"), mass="heavy")


class TestConfigElementAccess:
    def test_known_element(self):
        cfg = Config.defaults()
        assert cfg.elements["O"].radius == 0.66
        assert cfg.elements["O"].color == Color.from_hex("#ff0d0d")
        assert cfg.elements["O"].mass == 15.999

    def test_unknown_element_raises_key_error(self):
        cfg = Config.defaults()
        with pytest.raises(KeyError, match="Xx"):
            _ = cfg.elements["Xx"]

    def test_custom_element(self):
        defaults = _load_defaults()
        cfg = Config.from_dict(
            {
                **defaults,
                "elements": {
                    **defaults.get("elements", {}),
                    "Fe": {"radius": 1.5, "color": "#ff0000", "mass": 55.845},
                },
            }
        )
        assert cfg.elements["Fe"].radius == 1.5
        assert cfg.elements["Fe"].color == Color.from_hex("#ff0000")
        assert cfg.elements["Fe"].mass == 55.845

    def test_partial_override_merges_with_defaults(self):
        merged = _deep_merge(
            _load_defaults(),
            {"elements": {"Au": {"color": "#ffaa00"}}},
        )
        cfg = Config.from_dict(merged)
        assert cfg.elements["Au"].color == Color.from_hex("#ffaa00")
        assert cfg.elements["Au"].radius == 1.36
        assert cfg.elements["Au"].mass == 196.967

    def test_invalid_element_config_raises(self):
        with pytest.raises(TypeError, match="ElementConfig.radius must be"):
            Config.from_dict(
                {
                    **_load_defaults(),
                    "elements": {
                        "Fe": {"radius": "big", "color": "#ffffff", "mass": 1.0}
                    },
                }
            )
