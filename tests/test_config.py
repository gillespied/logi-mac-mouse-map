from logi_mouse_map.config import DEFAULT_SHORTCUT, Config, load_config, save_config


def test_missing_file_gives_defaults(tmp_path):
    assert load_config(tmp_path / "nope.toml") == Config()


def test_round_trip(tmp_path):
    path = tmp_path / "sub" / "config.toml"
    save_config(Config(shortcut="cmd+shift+4", enabled=False), path)
    assert load_config(path) == Config(shortcut="cmd+shift+4", enabled=False)


def test_invalid_toml_gives_defaults(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text("not = [valid")
    assert load_config(path).shortcut == DEFAULT_SHORTCUT


def test_wrong_types_fall_back(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text("shortcut = 5\nenabled = 'yes'\n")
    assert load_config(path) == Config()
