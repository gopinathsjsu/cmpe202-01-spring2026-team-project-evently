// @vitest-environment node

import { afterEach, describe, expect, it, vi } from "vitest";

import { apiFetch } from "./api";

vi.mock("./api-base", () => ({
  getApiBase: () => "http://localhost:8000",
}));

describe("apiFetch", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("does not force JSON headers onto FormData requests", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const body = new FormData();
    body.append("field", "value");
    await apiFetch("/contact/", { method: "POST", body });

    const [, options] = fetchMock.mock.calls[0];
    expect(new Headers(options.headers).has("Content-Type")).toBe(false);
  });

  it("returns undefined for 204 responses", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(null, { status: 204 })),
    );

    await expect(apiFetch("/users/1/photo", { method: "DELETE" })).resolves.toBe(
      undefined,
    );
  });
});
