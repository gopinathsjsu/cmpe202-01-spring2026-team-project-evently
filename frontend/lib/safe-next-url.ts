import type { NextRequest } from "next/server";

function firstHeaderValue(value: string | null): string | null {
  return value?.split(",")[0]?.trim() || null;
}

export function getPublicRequestOrigin(request: NextRequest): string {
  const forwardedHost = firstHeaderValue(request.headers.get("x-forwarded-host"));
  const host = forwardedHost ?? firstHeaderValue(request.headers.get("host"));
  const forwardedProto = firstHeaderValue(request.headers.get("x-forwarded-proto"));

  if (!host) {
    return request.nextUrl.origin;
  }

  const protocol = forwardedProto ?? request.nextUrl.protocol.replace(/:$/, "");
  return `${protocol}://${host}`;
}

export function getSafeNextUrl(request: NextRequest): string {
  const publicOrigin = getPublicRequestOrigin(request);
  const nextParam = request.nextUrl.searchParams.get("next");
  if (!nextParam) {
    return new URL("/", publicOrigin).toString();
  }

  const nextUrl = new URL(nextParam, publicOrigin);
  if (nextUrl.origin !== publicOrigin) {
    return new URL("/", publicOrigin).toString();
  }

  return nextUrl.toString();
}
