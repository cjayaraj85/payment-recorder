from __future__ import annotations

import subprocess
from pathlib import Path


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    hooks_dir = project_root / ".githooks"
    subprocess.run(
        ["git", "config", "core.hooksPath", str(hooks_dir.relative_to(project_root))],
        cwd=project_root,
        check=True,
    )
    print(f"Configured git hooks path: {hooks_dir.relative_to(project_root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

