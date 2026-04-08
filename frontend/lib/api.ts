import { getApiBase } from "@/lib/api-base";

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
  const headers = new Headers(init?.headers);
  const isFormData =
    typeof FormData !== "undefined" && init?.body instanceof FormData;
  if (!headers.has("Content-Type") && init?.body && !isFormData) {
    headers.set("Content-Type", "application/json");
  }

  // TODO [auth]: Inject auth headers here when ready.
  const res = await fetch(`${getApiBase()}${path}`, {
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

  return res.json() as Promise<T>;
}
