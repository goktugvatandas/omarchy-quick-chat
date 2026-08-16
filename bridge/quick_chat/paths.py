"""XDG filesystem layout for Quick Chat."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True)
class PathSet:
    home: Path
    config_dir: Path
    state_dir: Path
    capture_dir: Path

    @property
    def config_file(self) -> Path:
        return self.config_dir / "config.json"

    @property
    def history_file(self) -> Path:
        return self.state_dir / "history.json"

    @property
    def menu_extension_file(self) -> Path:
        return self.home / ".config" / "omarchy" / "extensions" / "omarchy-menu.jsonc"

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> PathSet:
        values = os.environ if env is None else env
        home = Path(values.get("HOME", str(Path.home()))).expanduser()
        config_home = Path(values.get("XDG_CONFIG_HOME", home / ".config")).expanduser()
        state_home = Path(
            values.get("XDG_STATE_HOME", home / ".local" / "state")
        ).expanduser()
        runtime_value = values.get("XDG_RUNTIME_DIR")
        runtime_home = (
            Path(runtime_value).expanduser()
            if runtime_value
            else Path(tempfile.gettempdir()) / f"omarchy-{os.getuid()}"
        )
        return cls(
            home=home,
            config_dir=config_home / "omarchy" / "quick-chat",
            state_dir=state_home / "omarchy" / "quick-chat",
            capture_dir=runtime_home / "omarchy-quick-chat",
        )
