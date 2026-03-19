import { NextRequest, NextResponse } from "next/server";

import { getPublicApiBase } from "@/lib/api-base";

function getSafeNextUrl(request: NextRequest): string {
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

export function GET(request: NextRequest) {
  const backendUrl = new URL("/auth/signin", getPublicApiBase());
  backendUrl.searchParams.set("next", getSafeNextUrl(request));
  return NextResponse.redirect(backendUrl);
}
