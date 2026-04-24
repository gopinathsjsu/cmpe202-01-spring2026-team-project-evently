import { NextRequest, NextResponse } from "next/server";

import { getSafeNextUrl } from "@/lib/safe-next-url";

export function GET(request: NextRequest) {
  // Always redirect through same-origin `/api` rewrite to avoid HTTPS->HTTP
  // mixed-content issues when backend is on an HTTP ALB.
  const backendUrl = new URL("/api/auth/signin", request.url);
  backendUrl.searchParams.set("next", getSafeNextUrl(request));
  return NextResponse.redirect(backendUrl);
}
