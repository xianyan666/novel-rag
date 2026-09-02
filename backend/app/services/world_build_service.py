"""World index build service."""

import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "scripts"


def build_world_index(project_id: str) -> dict:
    script = SCRIPTS_DIR / "build_world_index.py"
    result = subprocess.run(
        [sys.executable, str(script), "--project", project_id],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=600,
    )
    if result.returncode != 0:
        raise RuntimeError(f"World index build failed:\n{result.stderr[:500]}")
    return {"stdout": result.stdout, "stderr": result.stderr}
