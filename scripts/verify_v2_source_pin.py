#!/usr/bin/env python3
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PIN_PATH = REPO_ROOT / "config" / "v2-source-pin.json"


def git(root, *args):
    return subprocess.check_output(
        ["git", "-C", str(root), *args],
        text=True,
        stderr=subprocess.STDOUT,
    ).strip()


def main():
    source_root_raw = os.environ.get("GATEKEEPER_V2_SOURCE_ROOT")
    if not source_root_raw:
        print("FAIL: GATEKEEPER_V2_SOURCE_ROOT is required", file=sys.stderr)
        return 2

    source_root = Path(source_root_raw).expanduser().resolve()
    pin = json.loads(PIN_PATH.read_text(encoding="utf-8"))
    expected = pin["commit"].lower()

    try:
        actual = git(source_root, "rev-parse", "HEAD").lower()
        remote = git(source_root, "config", "--get", "remote.origin.url")
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        print(f"FAIL: unable to inspect Gatekeeper V2 source checkout: {exc}", file=sys.stderr)
        return 2

    if actual != expected:
        print(
            json.dumps(
                {
                    "status": "FAIL",
                    "reason": "v2_source_commit_mismatch",
                    "expected_commit": expected,
                    "actual_commit": actual,
                },
                separators=(",", ":"),
            )
        )
        return 1

    print(
        json.dumps(
            {
                "status": "PASS",
                "pin_scope": "source_checkout_only",
                "repository": pin["repository"],
                "expected_commit": expected,
                "actual_commit": actual,
                "remote": remote,
                "runtime_identity_proven": False,
            },
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
