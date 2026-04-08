// @vitest-environment node

import { describe, expect, it } from "vitest";

import { buildNextPath } from "./auth-redirect";

describe("buildNextPath", () => {
  it("preserves search params and hashes", () => {
    expect(buildNextPath("/events/12", "?ref=share", "#details")).toBe(
      "/events/12?ref=share#details",
    );
  });

  it("falls back to root when pathname is missing", () => {
    expect(buildNextPath(null, "", "")).toBe("/");
  });
});
