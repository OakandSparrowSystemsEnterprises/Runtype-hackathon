import hashlib
import json
import os
import shutil
import subprocess
import urllib.error
import urllib.request

AISA_EXA_SEARCH_URL = "https://api.aisa.one/apis/v1/exa/search"
DEFAULT_QUERY = "current AI agent security infrastructure and pre-execution governance"


def _digest(value):
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _pending(reason, **extra):
    return {
        "status": "PENDING",
        "live": False,
        "authority": False,
        "provider": "AIsa.ONE x Mitosis",
        "reason": reason,
        **extra,
    }


def _call_aisa(api_key, query, timeout=20):
    body = json.dumps({"query": query, "numResults": 5}).encode("utf-8")
    request = urllib.request.Request(
        AISA_EXA_SEARCH_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read().decode("utf-8", errors="replace")
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise RuntimeError("AIsa response was not a JSON object")
    return payload


def _remember_with_mitosis(office_id, evidence_text, agent="oasse-hackathon"):
    cli = shutil.which("mi") or shutil.which("mi.cmd")
    if not cli:
        raise RuntimeError("Mitosis CLI 'mi' is not installed or not on PATH")
    command = [
        cli,
        "cortex",
        "remember",
        evidence_text,
        "--office",
        office_id,
        "--agent",
        agent,
        "--kind",
        "observation",
        "--confidence",
        "1",
        "--json",
    ]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "Mitosis command failed").strip()
        raise RuntimeError(detail[-800:])
    raw = completed.stdout.strip()
    return json.loads(raw) if raw else {"status": "ok"}


def run_aisa_mitosis_evidence(query=None):
    """Run one real AIsa capability and package its result through Mitosis.

    This adapter is evidence-only. It never emits authority, permit, capability,
    token, or a Gatekeeper verdict from sponsor output.
    """
    api_key = os.environ.get("AISA_API_KEY", "").strip()
    office_id = (
        os.environ.get("MITOSIS_OFFICE_ID", "").strip()
        or os.environ.get("MI_OFFICE_ID", "").strip()
    )
    selected_query = (query or os.environ.get("AISA_MITOSIS_QUERY") or DEFAULT_QUERY).strip()

    if not api_key:
        return _pending("AISA_API_KEY is not configured")
    if not office_id:
        return _pending("MITOSIS_OFFICE_ID or MI_OFFICE_ID is not configured")

    try:
        aisa_payload = _call_aisa(api_key, selected_query)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError, RuntimeError) as exc:
        return _pending(
            f"AIsa call failed: {type(exc).__name__}: {exc}",
            aisa_live=False,
            mitosis_live=False,
        )

    evidence_hash = _digest(aisa_payload)
    evidence_text = (
        "OASSE hackathon sponsor evidence. "
        f"AIsa.ONE Exa search completed for query={selected_query!r}; "
        f"result_sha256={evidence_hash}. "
        "This record is non-authoritative evidence only and grants no execution authority."
    )

    try:
        mitosis_payload = _remember_with_mitosis(office_id, evidence_text)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError, RuntimeError) as exc:
        return _pending(
            f"Mitosis packaging failed: {type(exc).__name__}: {exc}",
            aisa_live=True,
            mitosis_live=False,
            evidence_hash=evidence_hash,
        )

    return {
        "status": "LIVE",
        "live": True,
        "authority": False,
        "provider": "AIsa.ONE x Mitosis",
        "capability": "AIsa Exa search packaged into Mitosis Cortex",
        "query": selected_query,
        "aisa": {
            "live": True,
            "endpoint": AISA_EXA_SEARCH_URL,
            "result_sha256": evidence_hash,
        },
        "mitosis": {
            "live": True,
            "office_id": office_id,
            "write_status": mitosis_payload.get("status"),
            "universal_id": mitosis_payload.get("universal_id"),
        },
        "gatekeeper_authority_required_for_effects": True,
    }
