"""导入服务：调用 ingest.py 脚本。"""

import os
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "scripts"


def run_ingest(project_id: str) -> dict:
    script = SCRIPTS_DIR / "ingest.py"
    env = {
        "NO_PROXY": "localhost,127.0.0.1",
        "no_proxy": "localhost,127.0.0.1",
    }
    full_env = {**os.environ, **env}

    result = subprocess.run(
        [sys.executable, str(script), "--project", project_id],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=600,
        env=full_env,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Ingest failed:\n{result.stderr[:500]}")
    return {"stdout": result.stdout, "stderr": result.stderr}
