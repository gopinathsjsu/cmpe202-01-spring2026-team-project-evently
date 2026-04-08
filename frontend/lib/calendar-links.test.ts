// @vitest-environment node

import { describe, expect, it } from "vitest";

import { buildEventUrl, shouldShowAddToCalendar } from "./calendar-links";

describe("calendar-links", () => {
  it("builds event URLs from the current origin", () => {
    expect(buildEventUrl("https://evently.example", 42)).toBe(
      "https://evently.example/events/42",
    );
  });

  it("shows add-to-calendar for organizers and registered attendees", () => {
    expect(shouldShowAddToCalendar(true, null)).toBe(true);
    expect(shouldShowAddToCalendar(false, "going")).toBe(true);
    expect(shouldShowAddToCalendar(false, "checked_in")).toBe(true);
    expect(shouldShowAddToCalendar(false, null)).toBe(false);
  });
});
