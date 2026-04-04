import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent


def main() -> int:
    env = os.environ.copy()
    required = ["API_BASE_URL", "MODEL_NAME", "HF_TOKEN"]
    missing = [key for key in required if not env.get(key)]
    if missing:
        print(
            "Missing required environment variables: "
            + ", ".join(missing),
            file=sys.stderr,
        )
        return 1

    env.setdefault("ENV_URL", "http://localhost:7860")

    default_python = PROJECT_ROOT / "backend" / ".venv" / "bin" / "python3"
    python_bin = os.environ.get("PYTHON_BIN", str(default_python))

    result = subprocess.run(
        [python_bin, "-u", "inference.py"],
        env=env,
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
    )

    print("=== STDOUT ===")
    print(result.stdout)
    if result.stderr:
        print("=== STDERR ===")
        print(result.stderr)
    print("Return code:", result.returncode)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
