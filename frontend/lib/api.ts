import { getApiBase } from "@/lib/api-base";
import { toBrowserSafeBackendUrl } from "@/lib/api-base";

// ==========================================================================
// API CLIENT — Single entry point for all backend requests.
//
// TODO [auth]: When authentication is added, attach the session token here
// so every request is automatically authenticated:
//
//   const token = getSessionToken();
//   if (token) headers["Authorization"] = `Bearer ${token}`;
// ==========================================================================

/**
 * Structured error thrown when the backend returns a non-2xx response.
 * `detail` preserves whatever the server sent (string, validation array, etc.)
 */
export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, detail: unknown) {
    const text =
      typeof detail === "string" ? detail : JSON.stringify(detail);
    super(`API error ${status}: ${text}`);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

const BACKEND_URL_KEYS = new Set([
  "image_url",
  "event_image_url",
  "profile_photo_url",
  "redirect_to",
]);

function normalizeBackendUrlsInPayload(value: unknown, key?: string): unknown {
  if (typeof value === "string") {
    if (key && BACKEND_URL_KEYS.has(key)) {
      return toBrowserSafeBackendUrl(value);
    }
    return value;
  }
  if (Array.isArray(value)) {
    return value.map((item) => normalizeBackendUrlsInPayload(item));
  }
  if (value && typeof value === "object") {
    const normalized: Record<string, unknown> = {};
    for (const [entryKey, entryValue] of Object.entries(
      value as Record<string, unknown>,
    )) {
      normalized[entryKey] = normalizeBackendUrlsInPayload(entryValue, entryKey);
    }
    return normalized;
  }
  return value;
}

function isLoopbackHostname(hostname: string): boolean {
  return hostname === "localhost" || hostname === "127.0.0.1" || hostname === "::1";
}

function resolveRequestBase(base: string): string {
  if (typeof window === "undefined" || window.location.protocol !== "https:") {
    return base;
  }
  try {
    const parsed = new URL(base);
    if (parsed.protocol === "http:" && !isLoopbackHostname(parsed.hostname)) {
      return `${window.location.origin}/api`;
    }
  } catch {
    return base;
  }
  return base;
}

/**
 * Thin wrapper around `fetch` that:
 *  - Prefixes the backend base URL
 *  - Sets JSON content-type (overridable)
 *  - Throws an `ApiError` with the server's detail on failure
 *
 * Works for GET, POST, PUT, DELETE — pass `method` and `body` via `init`.
 */
export async function apiFetch<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const requestBase = resolveRequestBase(getApiBase());
  const headers = new Headers(init?.headers);
  const isFormData =
    typeof FormData !== "undefined" && init?.body instanceof FormData;
  if (!headers.has("Content-Type") && init?.body && !isFormData) {
    headers.set("Content-Type", "application/json");
  }

  // TODO [auth]: Inject auth headers here when ready.
  const res = await fetch(`${requestBase}${path}`, {
    credentials: init?.credentials ?? "include",
    ...init,
    headers,
  });

  if (!res.ok) {
    let detail: unknown = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? body;
    } catch {
      // response wasn't JSON — keep statusText
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) {
    return undefined as T;
  }

  const contentType = res.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    return (await res.text()) as T;
  }

  const body = (await res.json()) as unknown;
  return normalizeBackendUrlsInPayload(body) as T;
}
