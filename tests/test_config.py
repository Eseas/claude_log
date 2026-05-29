"""Tests for the Config class."""

import yaml

from claude_log_organizer.config import Config


class TestConfigDefaults:
    def test_defaults_loaded_without_file(self):
        config = Config(None)
        assert config.get("watch.patterns") == ["*.log"]
        assert config.get("output.directory") == "./tasks"

    def test_nonexistent_file_uses_defaults(self, tmp_path):
        config = Config(tmp_path / "missing.yaml")
        assert config.get("output.directory") == "./tasks"


class TestConfigGet:
    def test_dot_notation_nested(self):
        config = Config(None)
        assert config.get("logging.level") == "INFO"

    def test_missing_key_returns_default(self):
        config = Config(None)
        assert config.get("nonexistent.key", "fallback") == "fallback"

    def test_missing_key_returns_none_by_default(self):
        config = Config(None)
        assert config.get("does.not.exist") is None

    def test_partial_path_into_nondict(self):
        config = Config(None)
        # output.directory is a string; descending further must return default
        assert config.get("output.directory.deeper", "x") == "x"


class TestConfigMerge:
    def test_user_config_overrides_defaults(self, tmp_path):
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml.dump({
            "output": {"directory": "/custom/path"},
        }), encoding="utf-8")
        config = Config(cfg_file)
        assert config.get("output.directory") == "/custom/path"
        # untouched defaults remain
        assert config.get("output.overwrite") is False

    def test_deep_merge_preserves_sibling_keys(self, tmp_path):
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(yaml.dump({
            "watch": {"poll_interval": 5.0},
        }), encoding="utf-8")
        config = Config(cfg_file)
        assert config.get("watch.poll_interval") == 5.0
        assert config.get("watch.patterns") == ["*.log"]

    def test_malformed_yaml_falls_back_to_defaults(self, tmp_path, capsys):
        cfg_file = tmp_path / "bad.yaml"
        cfg_file.write_text("{ this is not: valid: yaml :::", encoding="utf-8")
        config = Config(cfg_file)
        assert config.get("output.directory") == "./tasks"


class TestConfigCreateDefault:
    def test_creates_file(self, tmp_path):
        out = tmp_path / "new_config.yaml"
        Config.create_default(out)
        assert out.exists()

    def test_created_file_is_loadable(self, tmp_path):
        out = tmp_path / "sub" / "new_config.yaml"
        Config.create_default(out)
        config = Config(out)
        assert config.get("watch.patterns") == ["*.log"]
