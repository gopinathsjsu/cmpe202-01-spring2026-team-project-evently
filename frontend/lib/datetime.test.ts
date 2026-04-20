// @vitest-environment node

import { describe, expect, it } from "vitest";

import { parseApiDate } from "./datetime";

describe("parseApiDate", () => {
  it("treats naive API datetimes as UTC", () => {
    expect(parseApiDate("2026-03-22T06:30:00").toISOString()).toBe(
      "2026-03-22T06:30:00.000Z",
    );
  });

  it("preserves explicit timezone offsets", () => {
    expect(parseApiDate("2026-03-22T06:30:00-07:00").toISOString()).toBe(
      "2026-03-22T13:30:00.000Z",
    );
  });
});
