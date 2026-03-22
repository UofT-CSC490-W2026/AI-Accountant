from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from auth.mock_cognito import MockCognito


def _shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def main() -> int:
    parser = argparse.ArgumentParser(description="Print mock Cognito env vars and sample JWTs.")
    parser.add_argument("--format", choices=("shell", "json"), default="shell")
    args = parser.parse_args()

    mock = MockCognito()
    payload = {"env": mock.env_vars, "tokens": mock.sample_tokens()}

    if args.format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    for key, value in payload["env"].items():
        print(f"export {key}={_shell_quote(value)}")
    for key, value in payload["tokens"].items():
        print(f"export {key.upper()}={_shell_quote(value)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
