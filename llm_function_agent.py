from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from function_agent.llm_cli import main


if __name__ == "__main__":
    raise SystemExit(main())

