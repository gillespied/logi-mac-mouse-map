"""Load and save user settings as TOML."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

CONFIG_PATH = Path.home() / ".config" / "logi-mac-mouse-map" / "config.toml"

DEFAULT_SHORTCUT = "ctrl+up"  # Mission Control


@dataclass
class Config:
    """User settings."""

    shortcut: str = DEFAULT_SHORTCUT
    enabled: bool = True


def load_config(path: Path = CONFIG_PATH) -> Config:
    """Read the config file, falling back to defaults when it is missing or invalid."""
    try:
        data = tomllib.loads(path.read_text())
    except (FileNotFoundError, tomllib.TOMLDecodeError):
        return Config()
    shortcut = data.get("shortcut")
    enabled = data.get("enabled")
    return Config(
        shortcut=shortcut if isinstance(shortcut, str) else DEFAULT_SHORTCUT,
        enabled=enabled if isinstance(enabled, bool) else True,
    )


def save_config(config: Config, path: Path = CONFIG_PATH) -> None:
    """Write the config file, creating parent directories as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    shortcut = config.shortcut.replace("\\", "\\\\").replace('"', '\\"')
    path.write_text(f'shortcut = "{shortcut}"\nenabled = {str(config.enabled).lower()}\n')
