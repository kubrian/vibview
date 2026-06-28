from pathlib import Path
from unittest.mock import patch

import pytest

from vibview.config import Config, RenderingConfig, _deep_merge, _load_defaults


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
            cfg = Config.load()
        assert cfg.rendering.background_color == "#1e1e24"
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
            cfg = Config.load(session_config=session_file)
        assert cfg.animation.default_amplitude == 0.8
        assert cfg.rendering.background_color == "#000000"
        assert cfg.animation.fps == 30

    def test_session_quality_override(self, tmp_path):
        session_file = tmp_path / "session.yaml"
        session_file.write_text("rendering:\n  quality: low\n")
        with patch("vibview.config.USER_CONFIG_PATH") as mock_path:
            mock_path.exists.return_value = False
            cfg = Config.load(session_config=session_file)
        assert cfg.rendering.quality == "low"
        assert cfg.rendering.subdivisions == 1
        assert cfg.rendering.effective_shading == "flat"

    def test_high_quality_defaults_to_smooth(self, tmp_path):
        session_file = tmp_path / "session.yaml"
        session_file.write_text("rendering:\n  quality: high\n")
        with patch("vibview.config.USER_CONFIG_PATH") as mock_path:
            mock_path.exists.return_value = False
            cfg = Config.load(session_config=session_file)
        assert cfg.rendering.effective_shading == "smooth"

    def test_explicit_shading_overrides_quality_default(self, tmp_path):
        session_file = tmp_path / "session.yaml"
        session_file.write_text("rendering:\n  quality: low\n  shading: smooth\n")
        with patch("vibview.config.USER_CONFIG_PATH") as mock_path:
            mock_path.exists.return_value = False
            cfg = Config.load(session_config=session_file)
        assert cfg.rendering.effective_shading == "smooth"

    def test_invalid_shading_raises(self):
        defaults = _load_defaults()
        with pytest.raises(ValueError, match="shading"):
            RenderingConfig(**{**defaults["rendering"], "shading": "shiny"})

    def test_session_config_overrides_defaults(self, tmp_path):
        session_file = tmp_path / "session.yaml"
        session_file.write_text("rendering:\n  atom_color: '#00ff00'\n")
        with patch("vibview.config.USER_CONFIG_PATH") as mock_path:
            mock_path.exists.return_value = False
            cfg = Config.load(session_config=session_file)
        assert cfg.rendering.atom_color == "#00ff00"
        assert cfg.rendering.background_color == "#1e1e24"

    def test_session_config_nonexistent(self):
        with patch("vibview.config.USER_CONFIG_PATH") as mock_path:
            mock_path.exists.return_value = False
            cfg = Config.load(session_config=Path("/nonexistent/session.yaml"))
        assert cfg.animation.fps == 30

    def test_user_config_overrides_defaults(self, tmp_path):
        user_file = tmp_path / "user_config.yaml"
        user_file.write_text("animation:\n  fps: 15\n")
        with patch("vibview.config.USER_CONFIG_PATH", user_file):
            cfg = Config.load()
        assert cfg.animation.fps == 15

    def test_full_cascade(self, tmp_path):
        user_file = tmp_path / "user.yaml"
        user_file.write_text("rendering:\n  background_color: '#111111'\n")
        session_file = tmp_path / "session.yaml"
        session_file.write_text("rendering:\n  atom_color: '#222222'\n")
        with patch("vibview.config.USER_CONFIG_PATH", user_file):
            cfg = Config.load(session_config=session_file)

        assert cfg.rendering.background_color == "#111111"
        assert cfg.rendering.atom_color == "#222222"
