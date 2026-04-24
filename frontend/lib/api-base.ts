import type { NextRequest } from "next/server";

const DEFAULT_API_URL = "http://localhost:8000";

const API_PROXY_PREFIX = "/api";

function isIpv6Loopback(hostname: string): boolean {
  return hostname === "::1" || hostname === "[::1]";
}

function isLoopbackHost(hostname: string): boolean {
  return (
    hostname === "localhost" ||
    hostname === "127.0.0.1" ||
    isIpv6Loopback(hostname)
  );
}

/**
 * Uvicorn/FastAPI dev on loopback is HTTP. Env files often wrongly use https://…:8000
 * (or Next is served over HTTPS while copying the page scheme). Never use TLS for
 * loopback port 8000 unless you explicitly terminate TLS there (you almost certainly do not).
 */
function sanitizeConfiguredApiUrl(url: string): string {
  const trimmed = url.trim().replace(/\/$/, "");
  try {
    const u = new URL(trimmed);
    const port = u.port || (u.protocol === "https:" ? "443" : "80");
    if (u.protocol === "https:" && isLoopbackHost(u.hostname) && port === "8000") {
      u.protocol = "http:";
      return u.toString().replace(/\/$/, "");
    }
  } catch {
    return trimmed;
  }
  return trimmed;
}

function readEnvApiUrl(name: "NEXT_PUBLIC_API_URL" | "API_INTERNAL_URL"): string | undefined {
  const raw = process.env[name]?.trim();
  if (!raw) {
    return undefined;
  }
  return sanitizeConfiguredApiUrl(raw);
}

function isHttpsToHttpDowngrade(url: string): boolean {
  if (typeof window === "undefined" || window.location.protocol !== "https:") {
    return false;
  }
  try {
    const parsed = new URL(url);
    return parsed.protocol === "http:" && !isLoopbackHost(parsed.hostname);
  } catch {
    return false;
  }
}

/** Same-origin `/api` path; Next rewrites to BACKEND_PROXY_TARGET when deployed. */
function sameOriginApiBase(request?: NextRequest): string {
  if (request) {
    const u = request.nextUrl;
    return `${u.protocol}//${u.host}${API_PROXY_PREFIX}`;
  }
  if (typeof window !== "undefined") {
    return `${window.location.origin}${API_PROXY_PREFIX}`;
  }
  const internal = readEnvApiUrl("API_INTERNAL_URL");
  if (internal) {
    return internal;
  }
  return DEFAULT_API_URL;
}

function normalizeLocalApiBase(configuredBase: string): string {
  if (typeof window === "undefined") {
    return configuredBase;
  }

  const currentHostname = window.location.hostname;
  if (!isLoopbackHost(currentHostname)) {
    return configuredBase;
  }

  try {
    const configuredUrl = new URL(configuredBase);
    if (!isLoopbackHost(configuredUrl.hostname)) {
      return configuredBase;
    }
    configuredUrl.hostname = currentHostname;
    if (configuredUrl.protocol === "https:" && configuredUrl.port === "8000") {
      configuredUrl.protocol = "http:";
    }
    return configuredUrl.toString().replace(/\/$/, "");
  } catch {
    return configuredBase;
  }
}

/**
 * Local dev: backend on port 8000. Deployed (Amplify, etc.): never use :8000 on the
 * page host — nothing listens there and `fetch` hangs — use same-origin `/api` instead.
 */
function loopbackHttpApiOrigin(hostname: string): string {
  if (hostname === "::1" || hostname === "[::1]") {
    return "http://[::1]:8000";
  }
  return `http://${hostname}:8000`;
}

function deriveBrowserApiBase(): string {
  if (typeof window === "undefined") {
    return DEFAULT_API_URL;
  }

  if (isLoopbackHost(window.location.hostname)) {
    return loopbackHttpApiOrigin(window.location.hostname);
  }

  return sameOriginApiBase();
}

function deriveRequestApiBase(request: NextRequest): string {
  const hostname = request.nextUrl.hostname;
  if (isLoopbackHost(hostname)) {
    return loopbackHttpApiOrigin(hostname);
  }
  return sameOriginApiBase(request);
}

export function getPublicApiBase(request?: NextRequest): string {
  const configured = readEnvApiUrl("NEXT_PUBLIC_API_URL");
  if (configured) {
    // In HTTPS deployments (e.g., Amplify), browser requests to a plain HTTP API URL
    // are blocked as mixed content. Route through same-origin `/api` rewrite instead.
    if (!request && isHttpsToHttpDowngrade(configured)) {
      return sameOriginApiBase();
    }
    return request ? configured : normalizeLocalApiBase(configured);
  }

  if (request) {
    return deriveRequestApiBase(request);
  }

  return deriveBrowserApiBase();
}

export function getApiBase(request?: NextRequest): string {
  if (typeof window === "undefined") {
    const internal = readEnvApiUrl("API_INTERNAL_URL");
    if (internal) {
      return internal;
    }
    return getPublicApiBase(request);
  }

  return getPublicApiBase(request);
}
