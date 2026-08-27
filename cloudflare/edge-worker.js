const EDGE_ROLE = "public-edge-gateway";
const AUTHORITY_SOURCE = "Gatekeeper-V2-NPU";

function jsonResponse(payload, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
      "x-oasse-edge": "cloudflare-worker",
      "x-oasse-authority-source": AUTHORITY_SOURCE,
    },
  });
}

function upstreamUrl(request, origin) {
  const incoming = new URL(request.url);
  const target = new URL(origin);
  target.pathname = incoming.pathname;
  target.search = incoming.search;
  return target;
}

export default {
  async fetch(request, env) {
    if (request.method === "GET" && new URL(request.url).pathname === "/__oasse/edge-health") {
      return jsonResponse({
        ok: true,
        provider: "Cloudflare Workers",
        role: EDGE_ROLE,
        authority: false,
        authority_source: AUTHORITY_SOURCE,
        forwards_signed_agent_headers: true,
        gatekeeper_authority_required_for_effects: true,
      });
    }

    const origin = (env.OASSE_ORIGIN_URL || "").trim();
    if (!origin) {
      return jsonResponse({
        ok: false,
        status: "PENDING",
        provider: "Cloudflare Workers",
        role: EDGE_ROLE,
        authority: false,
        reason: "OASSE_ORIGIN_URL is not configured",
      }, 503);
    }

    const target = upstreamUrl(request, origin);
    const headers = new Headers(request.headers);
    headers.set("x-oasse-cloudflare-edge", "1");
    headers.set("x-oasse-authority-source", AUTHORITY_SOURCE);
    headers.delete("host");

    const upstreamRequest = new Request(target.toString(), {
      method: request.method,
      headers,
      body: request.method === "GET" || request.method === "HEAD" ? undefined : request.body,
      redirect: "manual",
    });

    let upstream;
    try {
      upstream = await fetch(upstreamRequest);
    } catch (error) {
      return jsonResponse({
        ok: false,
        status: "FAILED",
        provider: "Cloudflare Workers",
        role: EDGE_ROLE,
        authority: false,
        reason: `origin fetch failed: ${error instanceof Error ? error.message : String(error)}`,
      }, 502);
    }

    const responseHeaders = new Headers(upstream.headers);
    responseHeaders.set("x-oasse-edge", "cloudflare-worker");
    responseHeaders.set("x-oasse-edge-role", EDGE_ROLE);
    responseHeaders.set("x-oasse-authority-source", AUTHORITY_SOURCE);
    responseHeaders.set("cache-control", "no-store");

    return new Response(upstream.body, {
      status: upstream.status,
      statusText: upstream.statusText,
      headers: responseHeaders,
    });
  },
};
