const DEFAULT_API_URL = "http://localhost:8000";

export function getApiBase(): string {
  if (typeof window === "undefined") {
    return process.env.API_INTERNAL_URL ??
      process.env.NEXT_PUBLIC_API_URL ??
      DEFAULT_API_URL;
  }

  return process.env.NEXT_PUBLIC_API_URL ?? DEFAULT_API_URL;
}
