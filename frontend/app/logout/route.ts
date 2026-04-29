import { NextRequest, NextResponse } from "next/server";

import { getPublicRequestOrigin, getSafeNextUrl } from "@/lib/safe-next-url";

export function GET(request: NextRequest) {
  // Always redirect through same-origin `/api` rewrite to avoid HTTPS->HTTP
  // mixed-content issues when backend is on an HTTP ALB.
  const backendUrl = new URL("/api/auth/logout", getPublicRequestOrigin(request));
  backendUrl.searchParams.set("next", getSafeNextUrl(request));
  return NextResponse.redirect(backendUrl);
}
