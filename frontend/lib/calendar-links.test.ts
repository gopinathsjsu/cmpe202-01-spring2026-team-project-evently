// @vitest-environment node

import { describe, expect, it } from "vitest";

import { buildEventUrl } from "./calendar-links";

describe("calendar-links", () => {
  it("builds event URLs from the current origin", () => {
    expect(buildEventUrl("https://evently.example", 42)).toBe(
      "https://evently.example/events/42",
    );
  });
});
