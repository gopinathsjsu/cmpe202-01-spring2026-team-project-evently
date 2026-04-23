import type { NextRequest } from "next/server";

const DEFAULT_API_URL = "http://localhost:8000";

const API_PROXY_PREFIX = "/api";

function isLoopbackHost(hostname: string): boolean {
  return hostname === "localhost" || hostname === "127.0.0.1";
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
  const internal = process.env.API_INTERNAL_URL?.trim().replace(/\/$/, "");
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
    return configuredUrl.toString().replace(/\/$/, "");
  } catch {
    return configuredBase;
  }
}

/**
 * Local dev: backend on port 8000. Deployed (Amplify, etc.): never use :8000 on the
 * page host — nothing listens there and `fetch` hangs — use same-origin `/api` instead.
 */
function deriveBrowserApiBase(): string {
  if (typeof window === "undefined") {
    return DEFAULT_API_URL;
  }

  if (isLoopbackHost(window.location.hostname)) {
    return `${window.location.protocol}//${window.location.hostname}:8000`;
  }

  return sameOriginApiBase();
}

function deriveRequestApiBase(request: NextRequest): string {
  const hostname = request.nextUrl.hostname;
  if (isLoopbackHost(hostname)) {
    return `${request.nextUrl.protocol}//${hostname}:8000`;
  }
  return sameOriginApiBase(request);
}

export function getPublicApiBase(request?: NextRequest): string {
  if (process.env.NEXT_PUBLIC_API_URL) {
    return request
      ? process.env.NEXT_PUBLIC_API_URL
      : normalizeLocalApiBase(process.env.NEXT_PUBLIC_API_URL);
  }

  if (request) {
    return deriveRequestApiBase(request);
  }

  return deriveBrowserApiBase();
}

export function getApiBase(request?: NextRequest): string {
  if (typeof window === "undefined") {
    return process.env.API_INTERNAL_URL ?? getPublicApiBase(request);
  }

  return getPublicApiBase(request);
}
