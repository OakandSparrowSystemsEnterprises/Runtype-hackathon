#!/usr/bin/env python3
"""Port the AIsa x Mitosis sponsor plane into the LOCAL steward-wired
evidence pipeline without altering Deterministic Steward semantics.

Anchored, idempotent, fail-loud: it edits src/demo-orchestrator/
evidence_pipeline.py in place only if every anchor is found, otherwise it
prints exactly which anchor is missing and changes nothing. Safe to re-run.
"""
import json
import pathlib
import py_compile
import sys

TARGET = pathlib.Path(__file__).resolve().parent.parent / "src" / "demo-orchestrator" / "evidence_pipeline.py"


def emit(stage, status, **detail):
    print(json.dumps({"stage": stage, "status": status, **detail}, separators=(",", ":")))


IMPORT_ANCHOR = "from deterministic_steward import run_deterministic_steward"
IMPORT_INSERT = "from aisa_mitosis import run_aisa_mitosis"

POOL_ANCHOR = "with ThreadPoolExecutor(max_workers=2) as pool:"
POOL_REPLACE = "with ThreadPoolExecutor(max_workers=3) as pool:"

SUBMIT_ANCHOR = """        steward_future = pool.submit(
            run_deterministic_steward,
            artifact_ref,
            requested_effect,
            principal,
        )"""
SUBMIT_INSERT = """
        sponsor_future = pool.submit(
            run_aisa_mitosis,
            artifact_ref,
            requested_effect,
            principal,
            base_demo.get("target_url"),
        )"""

EXCEPT_ANCHOR = """            steward.update({
                "implemented": True,
                "swarm_native": True,
                "authority": False,
                "workers": [],
            })"""
EXCEPT_INSERT = """

        try:
            aisa_mitosis = sponsor_future.result()
        except Exception as exc:
            aisa_mitosis = _failed_plane("aisa_mitosis", exc)
            aisa_mitosis.update({
                "implemented": True,
                "sponsor": "AIsa.ONE x Mitosis",
                "live": False,
            })"""

RETURN_ANCHOR = '        "deterministic_steward": steward,'
RETURN_INSERT = """
        "sponsor": {"aisa_mitosis": aisa_mitosis},
        "sponsor_evidence_live": aisa_mitosis.get("status") == "LIVE","""


def main():
    if not TARGET.exists():
        emit("sponsor_plane_patch", "FAIL", reason=f"{TARGET} not found")
        return 1

    text = TARGET.read_text(encoding="utf-8")

    if "run_deterministic_steward" not in text:
        emit(
            "sponsor_plane_patch", "FAIL",
            reason="this evidence_pipeline.py is not the steward-wired variant; "
                   "restore it first (git checkout 39954df -- "
                   "src/demo-orchestrator/evidence_pipeline.py), then re-run",
        )
        return 1

    if "run_aisa_mitosis" in text:
        emit("sponsor_plane_patch", "ALREADY_PATCHED", target=str(TARGET))
        return 0

    anchors = [
        ("import", IMPORT_ANCHOR, IMPORT_ANCHOR + "\n" + IMPORT_INSERT),
        ("pool_width", POOL_ANCHOR, POOL_REPLACE),
        ("submit_block", SUBMIT_ANCHOR, SUBMIT_ANCHOR + SUBMIT_INSERT),
        ("steward_isolation_block", EXCEPT_ANCHOR, EXCEPT_ANCHOR + EXCEPT_INSERT),
        ("return_block", RETURN_ANCHOR, RETURN_ANCHOR + RETURN_INSERT),
    ]

    for name, anchor, _ in anchors:
        count = text.count(anchor)
        if count != 1:
            emit(
                "sponsor_plane_patch", "FAIL", anchor=name, occurrences=count,
                reason="anchor must appear exactly once; patch manually per "
                       "SUBMISSION integration notes, nothing was changed",
            )
            return 1

    for _, anchor, replacement in anchors:
        text = text.replace(anchor, replacement, 1)

    TARGET.write_text(text, encoding="utf-8")

    try:
        py_compile.compile(str(TARGET), doraise=True)
    except py_compile.PyCompileError as exc:
        emit("sponsor_plane_patch", "FAIL", reason=f"patched file failed to compile: {exc}")
        return 1

    emit(
        "sponsor_plane_patch", "PATCHED",
        target=str(TARGET),
        steward_semantics_changed=False,
        sponsor_gates_core_evidence=False,
        added=["run_aisa_mitosis import", "sponsor_future", "sponsor isolation", "sponsor result keys"],
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
