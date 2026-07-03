from pathlib import Path
from unittest.mock import patch

import pytest

from vibview.config import (
    _AUTO,
    CameraConfig,
    Color,
    Config,
    RenderingConfig,
    _deep_merge,
)


class TestDeepMerge:
    def test_simple_override(self):
        base = {"a": 1, "b": 2}
        override = {"b": 3}
        result = _deep_merge(base, override)
        assert result == {"a": 1, "b": 3}

    def test_nested_merge(self):
        base = {"rendering": {"color": "red", "size": 5}, "animation": {"fps": 60}}
        override = {"rendering": {"color": "blue"}}
        result = _deep_merge(base, override)
        assert result["rendering"] == {"color": "blue", "size": 5}
        assert result["animation"]["fps"] == 60

    def test_new_key_added(self):
        base = {"a": 1}
        override = {"b": 2}
        result = _deep_merge(base, override)
        assert result == {"a": 1, "b": 2}

    def test_base_unchanged(self):
        base = {"a": {"b": 1}}
        override = {"a": {"c": 2}}
        result = _deep_merge(base, override)
        assert result["a"] == {"b": 1, "c": 2}
        assert base["a"] == {"b": 1}


class TestLoadConfig:
    def test_defaults_only(self):
        with patch("vibview.config.USER_CONFIG_PATH") as mock_path:
            mock_path.exists.return_value = False
            cfg = Config.load(None)
        assert cfg.rendering.background_color == Color.from_hex("#1e1e24")
        assert cfg.animation.fps == 30

    def test_session_overrides(self, tmp_path):
        session_file = tmp_path / "session.yaml"
        session_file.write_text(
            "animation:\n"
            "  default_amplitude: 0.8\n"
            "rendering:\n"
            "  background_color: '#000000'\n"
        )
        with patch("vibview.config.USER_CONFIG_PATH") as mock_path:
            mock_path.exists.return_value = False
            cfg = Config.load(session_file)
        assert cfg.animation.default_amplitude == 0.8
        assert cfg.rendering.background_color == Color.from_hex("#000000")
        assert cfg.animation.fps == 30

    def test_session_quality_override(self, tmp_path):
        session_file = tmp_path / "session.yaml"
        session_file.write_text("rendering:\n  quality: low\n")
        with patch("vibview.config.USER_CONFIG_PATH") as mock_path:
            mock_path.exists.return_value = False
            cfg = Config.load(session_file)
        assert cfg.rendering.quality == "low"
        assert cfg.rendering.subdivisions == 1
        assert cfg.rendering.effective_shading == "flat"

    def test_high_quality_defaults_to_smooth(self, tmp_path):
        session_file = tmp_path / "session.yaml"
        session_file.write_text("rendering:\n  quality: high\n")
        with patch("vibview.config.USER_CONFIG_PATH") as mock_path:
            mock_path.exists.return_value = False
            cfg = Config.load(session_file)
        assert cfg.rendering.effective_shading == "smooth"

    def test_explicit_shading_overrides_quality_default(self, tmp_path):
        session_file = tmp_path / "session.yaml"
        session_file.write_text("rendering:\n  quality: low\n  shading: smooth\n")
        with patch("vibview.config.USER_CONFIG_PATH") as mock_path:
            mock_path.exists.return_value = False
            cfg = Config.load(session_file)
        assert cfg.rendering.effective_shading == "smooth"

    def test_invalid_shading_raises(self):
        cfg = Config.defaults()
        with pytest.raises(ValueError, match="shading"):
            RenderingConfig(**{**cfg.rendering.__dict__, "shading": "shiny"})

    def test_session_config_overrides_defaults(self, tmp_path):
        session_file = tmp_path / "session.yaml"
        session_file.write_text("rendering:\n  atom_color: '#00ff00'\n")
        with patch("vibview.config.USER_CONFIG_PATH") as mock_path:
            mock_path.exists.return_value = False
            cfg = Config.load(session_file)
        assert cfg.rendering.atom_color == Color.from_hex("#00ff00")
        assert cfg.rendering.background_color == Color.from_hex("#1e1e24")

    def test_session_config_nonexistent(self):
        with patch("vibview.config.USER_CONFIG_PATH") as mock_path:
            mock_path.exists.return_value = False
            cfg = Config.load(Path("/nonexistent/session.yaml"))
        assert cfg.animation.fps == 30

    def test_user_config_overrides_defaults(self, tmp_path):
        user_file = tmp_path / "user_config.yaml"
        user_file.write_text("animation:\n  fps: 15\n")
        with patch("vibview.config.USER_CONFIG_PATH", user_file):
            cfg = Config.load(None)
        assert cfg.animation.fps == 15

    def test_full_cascade(self, tmp_path):
        user_file = tmp_path / "user.yaml"
        user_file.write_text("rendering:\n  background_color: '#111111'\n")
        session_file = tmp_path / "session.yaml"
        session_file.write_text("rendering:\n  atom_color: '#222222'\n")
        with patch("vibview.config.USER_CONFIG_PATH", user_file):
            cfg = Config.load(session_file)

        assert cfg.rendering.background_color == Color.from_hex("#111111")
        assert cfg.rendering.atom_color == Color.from_hex("#222222")


_AUTO_CENTER = (_AUTO, _AUTO, _AUTO)
_HUD_DEFAULTS: dict[str, object] = dict(
    show_hud=False,
    hud_font_size=9,
    hud_linespace=2,
    hud_margin=12,
    hud_color=Color.from_hex("#ffffff"),
    hud_alpha=0.8,
)


def _camera_config(**overrides):
    base = dict(
        fov=0,
        fill_factor=0.75,
        min_distance=5.0,
        default_window_size=(608, 608),
        axis_view_size=100,
        axis_view_padding=0,
        axis_camera_distance=5.0,
        axis_camera_fov=0,
        center=_AUTO_CENTER,
        distance=_AUTO,
        azimuth=_AUTO,
        elevation=_AUTO,
        **_HUD_DEFAULTS,
    )
    base.update(overrides)
    return CameraConfig(**base)


class TestCameraConfig:
    def test_defaults_are_auto_sentinels(self):
        cfg = _camera_config()
        for attr in ("distance", "azimuth", "elevation"):
            assert getattr(cfg, attr) == _AUTO, f"{attr} should be _AUTO"
        assert all(c == _AUTO for c in cfg.center), "center should be all _AUTO"

    def test_explicit_pose_values(self):
        cfg = _camera_config(
            center=(1.0, 2.0, 3.0),
            distance=15.0,
            azimuth=45.0,
            elevation=30.0,
        )
        assert cfg.center == (1.0, 2.0, 3.0)
        assert cfg.distance == 15.0
        assert cfg.azimuth == 45.0
        assert cfg.elevation == 30.0

    def test_list_center_coerced_to_tuple(self):
        cfg = _camera_config(center=[1.0, 2.0, 3.0])
        assert isinstance(cfg.center, tuple)
        assert cfg.center == (1.0, 2.0, 3.0)

    def test_invalid_center_length_raises(self):
        with pytest.raises(ValueError, match="center"):
            _camera_config(center=(1.0, 2.0))

    def test_negative_distance_raises(self):
        with pytest.raises(ValueError, match="distance"):
            _camera_config(distance=-1.0)

    def test_elevation_out_of_range_raises(self):
        with pytest.raises(ValueError, match="elevation"):
            _camera_config(elevation=91.0)

    def test_hud_fields_defaults(self):
        cfg = _camera_config()
        assert cfg.show_hud is False
        assert cfg.hud_font_size == 9
        assert cfg.hud_linespace == 2
        assert cfg.hud_margin == 12
        assert cfg.hud_color == Color.from_hex("#ffffff")
        assert cfg.hud_alpha == 0.8

    def test_invalid_hud_alpha_raises(self):
        with pytest.raises(ValueError, match="hud_alpha"):
            _camera_config(hud_alpha=1.5)


class TestCameraAutoStrings:
    def test_auto_strings_convert_to_inf(self):
        cfg = _camera_config(
            center="auto", distance="auto", azimuth="auto", elevation="auto"
        )
        assert all(c == _AUTO for c in cfg.center)
        assert cfg.distance == _AUTO
        assert cfg.azimuth == _AUTO
        assert cfg.elevation == _AUTO

    def test_invalid_center_string_raises(self):
        with pytest.raises(ValueError, match="center: expected"):
            _camera_config(center="garbage")

    def test_invalid_distance_string_raises(self):
        with pytest.raises(ValueError, match="distance: expected"):
            _camera_config(distance="banana")


class TestConfigLoadWithCamera:
    def test_defaults_have_auto_pose(self):
        with patch("vibview.config.USER_CONFIG_PATH") as mock_path:
            mock_path.exists.return_value = False
            cfg = Config.load(None)
        assert cfg.camera.center == (_AUTO, _AUTO, _AUTO)
        assert cfg.camera.distance == _AUTO
        assert cfg.camera.azimuth == _AUTO
        assert cfg.camera.elevation == _AUTO

    def test_session_pose_overrides(self, tmp_path):
        session_file = tmp_path / "session.yaml"
        session_file.write_text("camera:\n  azimuth: 90.0\n  elevation: 45.0\n")
        with patch("vibview.config.USER_CONFIG_PATH") as mock_path:
            mock_path.exists.return_value = False
            cfg = Config.load(session_config=session_file)
        assert cfg.camera.azimuth == 90.0
        assert cfg.camera.elevation == 45.0
        assert cfg.camera.distance == _AUTO

    def test_explicit_center_override(self, tmp_path):
        session_file = tmp_path / "session.yaml"
        session_file.write_text("camera:\n  center: [2.0, 3.0, 4.0]\n")
        with patch("vibview.config.USER_CONFIG_PATH") as mock_path:
            mock_path.exists.return_value = False
            cfg = Config.load(session_config=session_file)
        assert cfg.camera.center == (2.0, 3.0, 4.0)
