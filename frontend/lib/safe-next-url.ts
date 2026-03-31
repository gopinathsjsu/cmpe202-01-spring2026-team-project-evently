import type { NextRequest } from "next/server";

export function getSafeNextUrl(request: NextRequest): string {
  const nextParam = request.nextUrl.searchParams.get("next");
  if (!nextParam) {
    return new URL("/", request.url).toString();
  }

  const nextUrl = new URL(nextParam, request.url);
  if (nextUrl.origin !== request.nextUrl.origin) {
    return new URL("/", request.url).toString();
  }

  return nextUrl.toString();
}
