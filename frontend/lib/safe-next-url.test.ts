// @vitest-environment node

import { describe, expect, it } from "vitest";
import { NextRequest } from "next/server";

import { getPublicRequestOrigin, getSafeNextUrl } from "./safe-next-url";

describe("getPublicRequestOrigin", () => {
  it("uses forwarded host and protocol ahead of the internal request URL", () => {
    const request = new NextRequest("https://localhost:3000/signin", {
      headers: {
        "x-forwarded-host": "feature-aws-deployment.d2p6a0rb9624ww.amplifyapp.com",
        "x-forwarded-proto": "https",
      },
    });

    expect(getPublicRequestOrigin(request)).toBe(
      "https://feature-aws-deployment.d2p6a0rb9624ww.amplifyapp.com",
    );
  });

  it("falls back to the request origin when forwarded headers are absent", () => {
    const request = new NextRequest("http://localhost:3000/signin");

    expect(getPublicRequestOrigin(request)).toBe("http://localhost:3000");
  });
});

describe("getSafeNextUrl", () => {
  it("builds the default next URL from the public forwarded origin", () => {
    const request = new NextRequest("https://localhost:3000/signin", {
      headers: {
        "x-forwarded-host": "feature-aws-deployment.d2p6a0rb9624ww.amplifyapp.com",
        "x-forwarded-proto": "https",
      },
    });

    expect(getSafeNextUrl(request)).toBe(
      "https://feature-aws-deployment.d2p6a0rb9624ww.amplifyapp.com/",
    );
  });

  it("keeps relative next paths on the public forwarded origin", () => {
    const request = new NextRequest("https://localhost:3000/signin?next=%2Fevents%2F21", {
      headers: {
        "x-forwarded-host": "feature-aws-deployment.d2p6a0rb9624ww.amplifyapp.com",
        "x-forwarded-proto": "https",
      },
    });

    expect(getSafeNextUrl(request)).toBe(
      "https://feature-aws-deployment.d2p6a0rb9624ww.amplifyapp.com/events/21",
    );
  });

  it("rejects absolute next URLs for other origins", () => {
    const request = new NextRequest(
      "https://localhost:3000/signin?next=https%3A%2F%2Fevil.example%2F",
      {
        headers: {
          "x-forwarded-host": "feature-aws-deployment.d2p6a0rb9624ww.amplifyapp.com",
          "x-forwarded-proto": "https",
        },
      },
    );

    expect(getSafeNextUrl(request)).toBe(
      "https://feature-aws-deployment.d2p6a0rb9624ww.amplifyapp.com/",
    );
  });
});
