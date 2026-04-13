import type { NextRequest } from "next/server";

const DEFAULT_API_URL = "http://localhost:8000";

function isLoopbackHost(hostname: string): boolean {
  return hostname === "localhost" || hostname === "127.0.0.1";
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

function deriveBrowserApiBase(): string {
  if (typeof window === "undefined") {
    return DEFAULT_API_URL;
  }

  return `${window.location.protocol}//${window.location.hostname}:8000`;
}

function deriveRequestApiBase(request: NextRequest): string {
  return `${request.nextUrl.protocol}//${request.nextUrl.hostname}:8000`;
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

  return getPublicApiBase();
}
