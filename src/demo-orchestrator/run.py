import os
import shutil
import subprocess

import arena
import server
from security_probes import run_chain_verification_probe, run_idempotency_probe
from tenki_swarm import run_tenki_swarm

PORT = server.PORT
DemoHandler = server.DemoHandler
ThreadingHTTPServer = server.ThreadingHTTPServer


def _credential(agent_id):
    return arena._credential(agent_id)


def _cotal_binary():
    candidate = shutil.which("npx.cmd") or shutil.which("npx")
    if not candidate:
        raise RuntimeError("npx not found on PATH")
    return candidate


def _cotal_send_without_pipes(agent_id, mode, target, text):
    command = [
        _cotal_binary(),
        "cotal-ai",
        "send",
        mode,
        target,
        text,
        "--creds",
        str(_credential(agent_id)),
    ]
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    completed = subprocess.run(
        command,
        cwd=str(arena.COTAL_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=45,
        check=False,
        creationflags=creationflags,
    )
    return {
        "agent": agent_id,
        "mode": mode,
        "target": target,
        "allowed": completed.returncode == 0,
        "returncode": completed.returncode,
        "detail": "",
    }


# On Windows, Cotal can leave inherited stdout/stderr pipe handles open after
# the CLI itself exits. The live runtime does not need CLI prose; the broker
# return code is the enforcement signal, so use null-backed handles.
arena._cotal_send = _cotal_send_without_pipes

_base_run_arena = arena.run_arena


def _run_arena_with_security(base_demo):
    result = _base_run_arena(base_demo)
    chain_verification = run_chain_verification_probe()
    idempotency = run_idempotency_probe()

    # Tenki is supporting compute/evidence only. A Tenki failure or missing
    # endpoint must never erase a Gatekeeper authority result or make Tenki an
    # authority source.
    try:
        tenki = run_tenki_swarm(
            base_demo.get("artifact_ref"),
            base_demo.get("requested_effect") or "parent-shield.navigation",
            base_demo.get("effect_principal") or "agent-b",
        )
    except Exception as exc:
        tenki = {
            "status": "PENDING",
            "live": False,
            "platform": "Tenki",
            "authority": False,
            "reason": str(exc),
        }

    result["security"] = {
        "chain_verification": chain_verification,
        "idempotency": idempotency,
    }
    result["tenki"] = tenki
    result["deterministic_steward"] = {
        "status": "IMPLEMENTATION_PENDING",
        "live": False,
        "authority": False,
    }
    result["ok"] = (
        bool(result.get("ok"))
        and chain_verification["ok"]
        and idempotency["ok"]
    )
    return result


# server imported run_arena by value, so patch both references used by the
# runtime after adding the live security and supporting-evidence probes.
arena.run_arena = _run_arena_with_security
server.run_arena = _run_arena_with_security


if __name__ == "__main__":
    runtime = ThreadingHTTPServer(("0.0.0.0", PORT), DemoHandler)
    print(f"Gatekeeper Demo Orchestrator listening on :{PORT} (arena runtime)", flush=True)
    runtime.serve_forever()
