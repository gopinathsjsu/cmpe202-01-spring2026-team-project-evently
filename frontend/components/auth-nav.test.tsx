import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AuthNav } from "./auth-nav";

vi.mock("@/lib/auth", () => ({
  useAuth: vi.fn(),
}));

import { useAuth } from "@/lib/auth";

const mockedUseAuth = vi.mocked(useAuth);

describe("AuthNav", () => {
  it("shows the admin queue link for signed-in admins", () => {
    mockedUseAuth.mockReturnValue({
      user: {
        id: 1,
        email: "admin@example.com",
        first_name: "Admin",
        last_name: "User",
        name: "Admin User",
        roles: ["user", "admin"],
        picture: null,
      },
      loading: false,
      error: null,
    });

    render(<AuthNav />);

    expect(screen.getByRole("link", { name: "Admin Queue" })).toHaveAttribute(
      "href",
      "/admin/events",
    );
    expect(screen.getByText("Admin")).toBeInTheDocument();
  });

  it("does not show the admin queue link for non-admin users", () => {
    mockedUseAuth.mockReturnValue({
      user: {
        id: 2,
        email: "user@example.com",
        first_name: "Regular",
        last_name: "User",
        name: "Regular User",
        roles: ["user"],
        picture: null,
      },
      loading: false,
      error: null,
    });

    render(<AuthNav />);

    expect(
      screen.queryByRole("link", { name: "Admin Queue" }),
    ).not.toBeInTheDocument();
  });
});
