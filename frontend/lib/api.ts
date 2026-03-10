// ==========================================================================
// API CLIENT — Single entry point for all backend requests.
//
// TODO [auth]: When authentication is added, attach the session token here
// so every request is automatically authenticated:
//
//   const token = getSessionToken();
//   if (token) headers["Authorization"] = `Bearer ${token}`;
// ==========================================================================

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

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
  // TODO [auth]: Inject auth headers here when ready.
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
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

  return res.json() as Promise<T>;
}
