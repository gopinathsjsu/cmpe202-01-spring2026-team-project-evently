import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({
  usePathname: vi.fn(),
}));

vi.mock("@/lib/auth", () => ({
  useAuth: vi.fn(),
}));

import { usePathname } from "next/navigation";

import Navbar from "./navbar";
import { useAuth } from "@/lib/auth";

const mockedUsePathname = vi.mocked(usePathname);
const mockedUseAuth = vi.mocked(useAuth);

describe("Navbar", () => {
  beforeEach(() => {
    mockedUsePathname.mockReturnValue("/");
  });

  it("hides personal navigation when the user is signed out", () => {
    mockedUseAuth.mockReturnValue({
      user: null,
      loading: false,
      error: null,
    });

    render(<Navbar />);

    expect(screen.queryByRole("link", { name: "My Tickets" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "My Calendar" })).not.toBeInTheDocument();
  });

  it("shows My Calendar instead of My Tickets when the user is signed in", () => {
    mockedUseAuth.mockReturnValue({
      user: {
        id: 4,
        email: "member@example.com",
        first_name: "Taylor",
        last_name: "Nguyen",
        name: "Taylor Nguyen",
        roles: ["user"],
        picture: null,
      },
      loading: false,
      error: null,
    });

    render(<Navbar />);

    expect(screen.getByRole("link", { name: "My Calendar" })).toHaveAttribute(
      "href",
      "/calendar",
    );
    expect(screen.queryByRole("link", { name: "My Tickets" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Taylor Nguyen" })).toHaveAttribute(
      "href",
      "/profile",
    );
  });
});
