"""AIsa.ONE x Mitosis sponsor evidence plane.

Architecture (fixed): AIsa capability -> Mitosis packaging/exposure ->
non-authoritative evidence input -> Gatekeeper alone governs the effect.

This plane runs only after the Gatekeeper verdict is already sealed and can
never precede, gate, or alter it. Sponsor outputs are evidence or compute
inputs only: any response that tries to assert authority, permit, capability,
token, or a Gatekeeper verdict is rejected as FAILED evidence.

Honest status discipline (claim <= artifact):
- A stage with no configured endpoint/key reports PENDING, never a fake pass.
- The plane is LIVE only when both real round-trips completed this run.
"""

import hashlib
import json
import os
import time
import urllib.error
import urllib.request

CONTRACT = "oasse.sponsor.aisa-mitosis.capability-evidence.v1"
SPONSOR = "AIsa.ONE x Mitosis"

DEFAULT_MITOSIS_MCP_URL = "https://mitosislabs.ai/api/mcp"
DEFAULT_AISA_CAPABILITY_PATH = "/v1/chat/completions"

NON_AUTHORITY_FIELDS = {
    "authority",
    "permit",
    "capability",
    "token",
    "gatekeeper_verdict",
}


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value):
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _assert_non_authoritative(value, path="$"):
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key in NON_AUTHORITY_FIELDS and child not in (None, False):
                raise RuntimeError(
                    f"sponsor response attempted to assert authority at {child_path}"
                )
            _assert_non_authoritative(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _assert_non_authoritative(child, f"{path}[{index}]")


def _artifact_digest(artifact_ref):
    if (
        not isinstance(artifact_ref, str)
        or not artifact_ref.startswith("sha256:")
        or len(artifact_ref) != 71
    ):
        raise RuntimeError("sponsor evidence requires a canonical sha256 ArtifactRef")
    digest = artifact_ref.split(":", 1)[1].lower()
    if any(char not in "0123456789abcdef" for char in digest):
        raise RuntimeError("sponsor evidence ArtifactRef digest must be lowercase hexadecimal")
    return digest


def _http_json(url, body, headers, timeout):
    """POST JSON, return (status, parsed_or_text, response_headers)."""
    raw = json.dumps(body, separators=(",", ":")).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=raw,
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        text = response.read().decode("utf-8", errors="replace")
        return response.status, text, dict(response.headers)


def _parse_maybe_sse(text):
    """Mitosis MCP is streamable HTTP: responses are JSON or SSE data lines."""
    stripped = text.strip()
    if stripped.startswith("{") or stripped.startswith("["):
        return json.loads(stripped)
    parsed = None
    for line in stripped.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            candidate = line[len("data:"):].strip()
            try:
                parsed = json.loads(candidate)
            except json.JSONDecodeError:
                continue
    if parsed is None:
        raise RuntimeError("MCP response contained no parseable JSON payload")
    return parsed


def aisa_config():
    base = os.environ.get("AISA_API_BASE", "").strip().rstrip("/")
    key = os.environ.get("AISA_API_KEY", "").strip()
    return {
        "configured": bool(base and key),
        "base": base,
        "key": key,
        "path": os.environ.get("AISA_CAPABILITY_PATH", DEFAULT_AISA_CAPABILITY_PATH),
        "model": os.environ.get("AISA_MODEL", "").strip(),
        "auth_header": os.environ.get("AISA_AUTH_HEADER", "Authorization"),
        "auth_scheme": os.environ.get("AISA_AUTH_SCHEME", "Bearer"),
        "timeout": float(os.environ.get("AISA_TIMEOUT", "20")),
    }


def mitosis_config():
    return {
        "configured": bool(os.environ.get("MITOSIS_API_KEY", "").strip()),
        "url": os.environ.get("MITOSIS_MCP_URL", DEFAULT_MITOSIS_MCP_URL).strip(),
        "key": os.environ.get("MITOSIS_API_KEY", "").strip(),
        "timeout": float(os.environ.get("MITOSIS_TIMEOUT", "20")),
    }


def build_capability_request(artifact_ref, requested_effect, principal, target_url):
    """Deterministic sponsor capability request bound to the governed run."""
    digest = _artifact_digest(artifact_ref)
    if not isinstance(requested_effect, str) or not requested_effect:
        raise RuntimeError("sponsor evidence requires the current requested_effect")
    if not isinstance(principal, str) or not principal:
        raise RuntimeError("sponsor evidence requires the current principal")
    task = (
        "You are a non-authoritative evidence worker in a governed agent demo. "
        "Return STRICT JSON only, with keys: summary (string, <=60 words), "
        "content_categories (array of strings), audience_note (string). "
        "Describe the likely content category and audience suitability of the "
        f"navigation target {target_url or '(no target url supplied)'}. "
        "You have no authority: never output permissions, verdicts, approvals, "
        "or policy decisions. Evidence only."
    )
    return {
        "artifact_ref": artifact_ref,
        "artifact_sha256": digest,
        "requested_effect": requested_effect,
        "principal": principal,
        "target_url": target_url,
        "task": task,
    }


def _invoke_aisa(config, capability_request):
    started = time.perf_counter()
    if not config["configured"]:
        return {
            "stage": "aisa_capability",
            "status": "PENDING",
            "live": False,
            "authority": False,
            "endpoint_configured": False,
            "claim": None,
            "error": "AISA_API_BASE / AISA_API_KEY not supplied to this shell",
            "elapsed_ms": 0.0,
        }

    body = {
        "messages": [{"role": "user", "content": capability_request["task"]}],
        "temperature": 0,
    }
    if config["model"]:
        body["model"] = config["model"]

    auth_value = (
        f"{config['auth_scheme']} {config['key']}".strip()
        if config["auth_scheme"]
        else config["key"]
    )

    try:
        status, text, _ = _http_json(
            config["base"] + config["path"],
            body,
            {config["auth_header"]: auth_value},
            config["timeout"],
        )
        payload = json.loads(text)
        _assert_non_authoritative(payload)
        content = None
        choices = payload.get("choices")
        if isinstance(choices, list) and choices:
            message = choices[0].get("message") if isinstance(choices[0], dict) else None
            if isinstance(message, dict):
                content = message.get("content")
        if content is None:
            content = text
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("AIsa capability returned no content")

        claim_semantic = {
            "contract": CONTRACT,
            "compute_plane": "aisa",
            "role": "capability_evidence_only",
            "sponsor": "AIsa.ONE",
            "capability_kind": "navigation-target-enrichment",
            "artifact_ref": capability_request["artifact_ref"],
            "artifact_sha256": capability_request["artifact_sha256"],
            "requested_effect": capability_request["requested_effect"],
            "principal": capability_request["principal"],
            "target_url": capability_request["target_url"],
            "authority": False,
            "model": config["model"] or None,
            "content_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        }
        claim = {
            **claim_semantic,
            "claim_hash": _digest(claim_semantic),
            "content_excerpt": content.strip()[:400],
        }
        return {
            "stage": "aisa_capability",
            "status": "COMPLETED",
            "live": True,
            "authority": False,
            "endpoint_configured": True,
            "http_status": status,
            "claim": claim,
            "claim_hash": claim["claim_hash"],
            "error": None,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
        }
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        error = f"HTTP {exc.code}: {detail[-800:]}"
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, RuntimeError) as exc:
        error = f"{type(exc).__name__}: {exc}"

    return {
        "stage": "aisa_capability",
        "status": "FAILED",
        "live": False,
        "authority": False,
        "endpoint_configured": True,
        "claim": None,
        "error": error,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
    }


def _mcp_call(config, method, params, request_id, session_id=None):
    headers = {
        "Authorization": f"Bearer {config['key']}",
        "Accept": "application/json, text/event-stream",
    }
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    body = {"jsonrpc": "2.0", "method": method}
    if request_id is not None:
        body["id"] = request_id
    if params is not None:
        body["params"] = params
    status, text, response_headers = _http_json(
        config["url"], body, headers, config["timeout"]
    )
    lowered = {key.lower(): value for key, value in response_headers.items()}
    new_session = lowered.get("mcp-session-id", session_id)
    if request_id is None:
        return status, None, new_session
    payload = _parse_maybe_sse(text)
    if isinstance(payload, dict) and payload.get("error"):
        raise RuntimeError(f"MCP error: {_canonical(payload['error'])[:400]}")
    result = payload.get("result") if isinstance(payload, dict) else None
    return status, result, new_session


def _package_in_mitosis(config, claim):
    started = time.perf_counter()
    if claim is None:
        return {
            "stage": "mitosis_packaging",
            "status": "PENDING",
            "live": False,
            "authority": False,
            "endpoint_configured": config["configured"],
            "error": "no AIsa capability claim available to package",
            "elapsed_ms": 0.0,
        }
    if not config["configured"]:
        return {
            "stage": "mitosis_packaging",
            "status": "PENDING",
            "live": False,
            "authority": False,
            "endpoint_configured": False,
            "error": "MITOSIS_API_KEY not supplied to this shell",
            "elapsed_ms": 0.0,
        }

    fact = (
        f"Gatekeeper hackathon sponsor evidence: AIsa capability claim "
        f"{claim['claim_hash']} for governed artifact {claim['artifact_ref']} "
        f"(effect {claim['requested_effect']}, principal {claim['principal']}, "
        f"content sha256 {claim['content_sha256']}); authority=false; "
        f"capability evidence only, packaged and exposed through Mitosis."
    )
    try:
        _, _, session_id = _mcp_call(
            config,
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {
                    "name": "gatekeeper-hackathon-sponsor-evidence",
                    "version": "0.1",
                },
            },
            request_id=1,
        )
        try:
            _mcp_call(
                config, "notifications/initialized", {}, request_id=None,
                session_id=session_id,
            )
        except (urllib.error.HTTPError, urllib.error.URLError, RuntimeError):
            pass  # some servers reply 202/4xx to the notification; not fatal
        _, result, _ = _mcp_call(
            config,
            "tools/call",
            {
                "name": "cortex_remember",
                "arguments": {"text": fact, "kind": "hackathon-sponsor-evidence"},
            },
            request_id=2,
            session_id=session_id,
        )
        if isinstance(result, dict):
            _assert_non_authoritative(result)
            if result.get("isError") is True:
                raise RuntimeError(f"cortex_remember reported isError: {_canonical(result)[:400]}")
        excerpt = None
        content = result.get("content") if isinstance(result, dict) else None
        if isinstance(content, list) and content:
            first = content[0]
            if isinstance(first, dict) and isinstance(first.get("text"), str):
                excerpt = first["text"][:400]
        return {
            "stage": "mitosis_packaging",
            "status": "COMPLETED",
            "live": True,
            "authority": False,
            "endpoint_configured": True,
            "tool": "cortex_remember",
            "packaged_claim_hash": claim["claim_hash"],
            "memory_excerpt": excerpt,
            "exposure": "mitosis-office-memory-graph",
            "error": None,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
        }
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        error = f"HTTP {exc.code}: {detail[-800:]}"
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, RuntimeError) as exc:
        error = f"{type(exc).__name__}: {exc}"

    return {
        "stage": "mitosis_packaging",
        "status": "FAILED",
        "live": False,
        "authority": False,
        "endpoint_configured": True,
        "error": error,
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
    }


def run_aisa_mitosis(artifact_ref, requested_effect, principal, target_url=None):
    """Run the sponsor evidence plane for the current governed run."""
    capability_request = build_capability_request(
        artifact_ref, requested_effect, principal, target_url
    )
    aisa = aisa_config()
    mitosis = mitosis_config()

    started = time.perf_counter()
    aisa_result = _invoke_aisa(aisa, capability_request)
    mitosis_result = _package_in_mitosis(mitosis, aisa_result.get("claim"))

    stages = [aisa_result, mitosis_result]
    completed = sum(1 for item in stages if item["status"] == "COMPLETED")
    failed = sum(1 for item in stages if item["status"] == "FAILED")
    configured = aisa["configured"] or mitosis["configured"]

    if completed == len(stages):
        status = "LIVE"
    elif completed:
        status = "PARTIAL"
    elif not configured:
        status = "NEXT_PENDING"
    elif failed:
        status = "FAILED"
    else:
        status = "NEXT_PENDING"

    semantic = {
        "contract": CONTRACT,
        "sponsor": SPONSOR,
        "artifact_ref": artifact_ref,
        "requested_effect": requested_effect,
        "principal": principal,
        "target_url": target_url,
        "authority": False,
        "stage_statuses": [item["status"] for item in stages],
        "claim_hash": aisa_result.get("claim_hash"),
        "packaged": mitosis_result["status"] == "COMPLETED",
    }

    return {
        "status": status,
        "live": status == "LIVE",
        "implemented": True,
        "sponsor": SPONSOR,
        "contract": CONTRACT,
        "authority": False,
        "pipeline": "aisa-capability -> mitosis-packaging -> non-authoritative evidence -> Gatekeeper governs effect",
        "aisa": aisa_result,
        "mitosis": mitosis_result,
        "claim": aisa_result.get("claim"),
        "claim_hash": aisa_result.get("claim_hash"),
        "configured": {
            "aisa": aisa["configured"],
            "mitosis": mitosis["configured"],
            "secrets_printed": False,
        },
        "state_hash": _digest(semantic),
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
        "reason": None if status == "LIVE" else (
            aisa_result.get("error") or mitosis_result.get("error")
        ),
        "gatekeeper_authority_required_for_effects": True,
    }
