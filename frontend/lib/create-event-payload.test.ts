// @vitest-environment node

import { describe, expect, it } from "vitest";

import { buildCreateEventPayload } from "./create-event-payload";

describe("buildCreateEventPayload", () => {
  it("uses the provided location fields instead of hardcoded values", () => {
    const payload = buildCreateEventPayload({
      title: " Launch Party ",
      category: "Business",
      startISO: "2026-06-01T17:00:00.000Z",
      endISO: "2026-06-01T19:00:00.000Z",
      venueName: " Innovation Hub ",
      address: " 123 Main St ",
      city: " San Jose ",
      state: " CA ",
      zipCode: " 95112 ",
      latitude: "37.3382",
      longitude: "-121.8863",
    });

    expect(payload.title).toBe("Launch Party");
    expect(payload.location).toEqual({
      venue_name: "Innovation Hub",
      address: "123 Main St",
      city: "San Jose",
      state: "CA",
      zip_code: "95112",
      latitude: 37.3382,
      longitude: -121.8863,
    });
  });
});
