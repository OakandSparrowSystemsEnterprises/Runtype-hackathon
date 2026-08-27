import os
import shutil
import subprocess

import arena
from server import DemoHandler, PORT, ThreadingHTTPServer


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
# the CLI itself exits. The normal arena capture path then waits for EOF and
# times out even though the message was delivered. The live runtime does not
# need CLI prose; the broker return code is the enforcement signal, so use
# null-backed handles instead of pipes.
arena._cotal_send = _cotal_send_without_pipes


if __name__ == "__main__":
    server = ThreadingHTTPServer(("0.0.0.0", PORT), DemoHandler)
    print(f"Gatekeeper Demo Orchestrator listening on :{PORT} (arena runtime)", flush=True)
    server.serve_forever()
