import { render, screen, waitFor } from "@testing-library/react";
import { act } from "react";
import { hydrateRoot } from "react-dom/client";
import { renderToString } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({
  useRouter: vi.fn(() => ({ push: vi.fn() })),
}));

vi.mock("@/lib/auth", () => ({
  useAuth: vi.fn(),
}));

import { useAuth } from "@/lib/auth";

import { AuthRequiredAction } from "./auth-required-action";

const mockedUseAuth = vi.mocked(useAuth);

describe("AuthRequiredAction", () => {
  beforeEach(() => {
    mockedUseAuth.mockReturnValue({
      user: null,
      loading: false,
      error: null,
    });
  });

  it("renders a disabled button in server markup before hydration", () => {
    const html = renderToString(
      <AuthRequiredAction
        actionLabel="create an event"
        authenticatedHref="/create"
        className="text-sm font-medium text-gray-700 hover:text-black"
        nextPath="/create"
      >
        Create Event
      </AuthRequiredAction>,
    );

    expect(html).toContain("disabled");
  });

  it("becomes interactive after mount when not otherwise disabled", async () => {
    render(
      <AuthRequiredAction
        actionLabel="create an event"
        authenticatedHref="/create"
        className="text-sm font-medium text-gray-700 hover:text-black"
        nextPath="/create"
      >
        Create Event
      </AuthRequiredAction>,
    );

    await waitFor(() => {
      expect(
        screen.getByRole("button", { name: "Create Event" }),
      ).not.toBeDisabled();
    });
  });

  it("hydrates without a disabled attribute mismatch", async () => {
    let authState = {
      user: null,
      loading: true,
      error: null,
    };

    mockedUseAuth.mockImplementation(() => authState);

    const html = renderToString(
      <AuthRequiredAction
        actionLabel="create an event"
        authenticatedHref="/create"
        className="text-sm font-medium text-gray-700 hover:text-black"
        nextPath="/create"
      >
        Create Event
      </AuthRequiredAction>,
    );

    const container = document.createElement("div");
    container.innerHTML = html;
    document.body.appendChild(container);

    expect(container.querySelector("button")).toHaveAttribute("disabled");

    authState = {
      user: null,
      loading: false,
      error: null,
    };

    const errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    await act(async () => {
      hydrateRoot(
        container,
        <AuthRequiredAction
          actionLabel="create an event"
          authenticatedHref="/create"
          className="text-sm font-medium text-gray-700 hover:text-black"
          nextPath="/create"
        >
          Create Event
        </AuthRequiredAction>,
      );
    });

    const errorOutput = errorSpy.mock.calls.flat().join("\n");
    expect(errorOutput).not.toContain("Hydration failed");
    expect(errorOutput).not.toContain("didn't match");

    errorSpy.mockRestore();
    container.remove();
  });
});
