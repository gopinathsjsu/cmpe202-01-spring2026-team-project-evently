// @vitest-environment node

import { describe, expect, it } from "vitest";

import { withNext } from "./path-with-next";

describe("withNext", () => {
  it("appends next when the path has no existing query string", () => {
    expect(withNext("/signin", "/calendar")).toBe("/signin?next=%2Fcalendar");
  });

  it("preserves existing query params", () => {
    expect(withNext("/signin?source=nav", "/calendar")).toBe(
      "/signin?source=nav&next=%2Fcalendar",
    );
  });

  it("keeps hash fragments at the end of the URL", () => {
    expect(withNext("/signin?source=nav#hero", "/calendar")).toBe(
      "/signin?source=nav&next=%2Fcalendar#hero",
    );
  });
});
