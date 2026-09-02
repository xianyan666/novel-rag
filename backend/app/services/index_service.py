"""索引构建服务。"""

import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "scripts"


def build_index(project_id: str) -> dict:
    script = SCRIPTS_DIR / "build_index.py"
    env = {
        "NO_PROXY": "localhost,127.0.0.1",
        "no_proxy": "localhost,127.0.0.1",
    }
    import os
    full_env = {**os.environ, **env}

    result = subprocess.run(
        [sys.executable, str(script), "--project", project_id],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=1800,
        env=full_env,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Index build failed:\n{result.stderr[:500]}")
    return {"stdout": result.stdout, "stderr": result.stderr}
