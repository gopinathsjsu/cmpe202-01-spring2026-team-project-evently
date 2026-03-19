import { NextRequest, NextResponse } from "next/server";

import { getPublicApiBase } from "@/lib/api-base";
import { getSafeNextUrl } from "@/lib/safe-next-url";

export function GET(request: NextRequest) {
  const backendUrl = new URL("/auth/logout", getPublicApiBase());
  backendUrl.searchParams.set("next", getSafeNextUrl(request));
  return NextResponse.redirect(backendUrl);
}
