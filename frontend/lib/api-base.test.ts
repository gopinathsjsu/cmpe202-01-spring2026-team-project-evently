// @vitest-environment node

import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

describe("api-base getPublicApiBase", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.resetModules();
    delete (globalThis as { window?: unknown }).window;
  });

  it("coerces https://localhost:8000 from env to http when handling signin redirect", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "https://localhost:8000");
    const { getPublicApiBase } = await import("./api-base");
    const req = new NextRequest(new URL("https://localhost:3000/signin"));
    expect(getPublicApiBase(req)).toBe("http://localhost:8000");
  });

  it("leaves remote https API URL unchanged for server routes", async () => {
    vi.stubEnv(
      "NEXT_PUBLIC_API_URL",
      "https://api.example.com",
    );
    const { getPublicApiBase } = await import("./api-base");
    const req = new NextRequest(new URL("https://localhost:3000/signin"));
    expect(getPublicApiBase(req)).toBe("https://api.example.com");
  });

  it("uses same-origin /api in browser when configured URL is remote http on https page", async () => {
    vi.stubEnv(
      "NEXT_PUBLIC_API_URL",
      "http://evently-dev-api-alb-511216335.us-east-2.elb.amazonaws.com",
    );
    Object.defineProperty(globalThis, "window", {
      value: {
        location: {
          protocol: "https:",
          origin: "https://feature-aws-deployment.d2p6a0rb9624ww.amplifyapp.com",
          hostname: "feature-aws-deployment.d2p6a0rb9624ww.amplifyapp.com",
        },
      },
      configurable: true,
    });
    const { getPublicApiBase } = await import("./api-base");
    expect(getPublicApiBase()).toBe(
      "https://feature-aws-deployment.d2p6a0rb9624ww.amplifyapp.com/api",
    );
  });
});

describe("api-base toBrowserSafeBackendUrl", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.resetModules();
    delete (globalThis as { window?: unknown }).window;
  });

  it("rewrites remote http backend URLs through /api", async () => {
    const { toBrowserSafeBackendUrl } = await import("./api-base");
    expect(
      toBrowserSafeBackendUrl("http://evently-dev-api-alb.example.com/uploads/a.png"),
    ).toBe("/api/uploads/a.png");
  });

  it("keeps external https URLs unchanged", async () => {
    const { toBrowserSafeBackendUrl } = await import("./api-base");
    expect(
      toBrowserSafeBackendUrl("https://cdn.example.com/images/a.png"),
    ).toBe("https://cdn.example.com/images/a.png");
  });

  it("routes relative backend paths through /api", async () => {
    const { toBrowserSafeBackendUrl } = await import("./api-base");
    expect(toBrowserSafeBackendUrl("/uploads/a.png")).toBe("/api/uploads/a.png");
  });
});
