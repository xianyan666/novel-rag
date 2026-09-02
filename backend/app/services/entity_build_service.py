"""实体索引构建服务。"""

import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "scripts"


def build_entities(project_id: str) -> dict:
    script = SCRIPTS_DIR / "build_entities.py"
    result = subprocess.run(
        [sys.executable, str(script), "--project", project_id],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=600,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Entity build failed:\n{result.stderr[:500]}")
    return {"stdout": result.stdout, "stderr": result.stderr}
