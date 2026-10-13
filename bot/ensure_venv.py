from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def ensure_venv() -> None:
    """Перезапускает скрипт через .venv, если пакеты ставили туда, а запуск идёт другим Python."""
    root = Path(__file__).resolve().parent.parent
    if os.name == "nt":
        venv_python = root / ".venv" / "Scripts" / "python.exe"
    else:
        venv_python = root / ".venv" / "bin" / "python"
    if not venv_python.exists():
        return
    try:
        if Path(sys.executable).resolve() == venv_python.resolve():
            return
    except OSError:
        pass
    raise SystemExit(subprocess.call([str(venv_python), *sys.argv]))
