import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("next/navigation", () => ({
  usePathname: vi.fn(),
}));

vi.mock("@/lib/auth", () => ({
  useAuth: vi.fn(),
}));

import { usePathname } from "next/navigation";

import { useAuth } from "@/lib/auth";
import HelpPage from "./page";

const mockedUsePathname = vi.mocked(usePathname);
const mockedUseAuth = vi.mocked(useAuth);

describe("HelpPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    mockedUsePathname.mockReturnValue("/help");
    mockedUseAuth.mockReturnValue({
      user: null,
      loading: false,
      error: null,
    });
  });

  // -----------------------------------------------------------------------
  // Rendering
  // -----------------------------------------------------------------------

  it("renders the header with Evently branding", () => {
    render(<HelpPage />);
    const eventlyTexts = screen.getAllByText("Evently");
    expect(eventlyTexts.length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Browse Events").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Create Event")).toBeInTheDocument();
  });

  it("renders the FAQ heading", () => {
    render(<HelpPage />);
    expect(
      screen.getByText("Frequently Asked Questions"),
    ).toBeInTheDocument();
  });

  it("renders the sidebar with all navigation items", () => {
    render(<HelpPage />);
    const sidebar = [
      "Getting Started",
      "FAQ",
      "Event Creation",
      "Ticket Management",
      "Payment Issues",
      "Contact Support",
    ];
    for (const item of sidebar) {
      expect(screen.getByRole("button", { name: item })).toBeInTheDocument();
    }
  });

  it("renders all three category tabs", () => {
    render(<HelpPage />);
    expect(screen.getByText("Ticketing")).toBeInTheDocument();
    expect(screen.getByText("Events")).toBeInTheDocument();
    expect(screen.getByText("Payments")).toBeInTheDocument();
  });

  it("renders FAQ items", () => {
    render(<HelpPage />);
    expect(
      screen.getByText("How do I create an event?"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("How do I register for an event?"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("What payment methods are accepted?"),
    ).toBeInTheDocument();
  });

  it("renders the Contact Support section", () => {
    render(<HelpPage />);
    const contactTexts = screen.getAllByText("Contact Support");
    expect(contactTexts.length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Email Support")).toBeInTheDocument();
    expect(screen.getByText("Phone Support")).toBeInTheDocument();
    expect(screen.getByText("Live Chat")).toBeInTheDocument();
  });

  it("renders the contact form fields", () => {
    render(<HelpPage />);
    expect(screen.getByLabelText("Subject")).toBeInTheDocument();
    expect(screen.getByLabelText("Email")).toBeInTheDocument();
    expect(screen.getByLabelText("Message")).toBeInTheDocument();
    expect(screen.getByText("Send Message")).toBeInTheDocument();
  });

  it("renders the footer", () => {
    render(<HelpPage />);
    expect(
      screen.getByText("© 2025 Evently. All rights reserved."),
    ).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // FAQ accordion
  // -----------------------------------------------------------------------

  it("expands and collapses FAQ items on click", () => {
    render(<HelpPage />);
    const question = screen.getByText("What payment methods are accepted?");

    expect(
      screen.queryByText(/We accept all major credit cards/),
    ).not.toBeInTheDocument();

    fireEvent.click(question);
    expect(
      screen.getByText(/We accept all major credit cards/),
    ).toBeInTheDocument();

    fireEvent.click(question);
    expect(
      screen.queryByText(/We accept all major credit cards/),
    ).not.toBeInTheDocument();
  });

  it("only one FAQ is expanded at a time", () => {
    render(<HelpPage />);

    fireEvent.click(screen.getByText("How do I create an event?"));
    expect(screen.getByText(/click "Create Event"/)).toBeInTheDocument();

    fireEvent.click(screen.getByText("What payment methods are accepted?"));
    expect(
      screen.getByText(/We accept all major credit cards/),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(/click "Create Event"/),
    ).not.toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Category filtering
  // -----------------------------------------------------------------------

  it("filters FAQs by category when a tab is clicked", () => {
    render(<HelpPage />);

    fireEvent.click(screen.getByText("Payments"));

    expect(
      screen.getByText("What payment methods are accepted?"),
    ).toBeInTheDocument();
    expect(
      screen.queryByText("How do I create an event?"),
    ).not.toBeInTheDocument();
  });

  it("clears category filter when same tab is clicked again", () => {
    render(<HelpPage />);

    fireEvent.click(screen.getByText("Payments"));
    expect(
      screen.queryByText("How do I create an event?"),
    ).not.toBeInTheDocument();

    fireEvent.click(screen.getByText("Payments"));
    expect(
      screen.getByText("How do I create an event?"),
    ).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // FAQ search
  // -----------------------------------------------------------------------

  it("filters FAQs based on search query", () => {
    render(<HelpPage />);
    const searchInput = screen.getByPlaceholderText("Search FAQ...");

    fireEvent.change(searchInput, { target: { value: "refund" } });

    expect(
      screen.getByText("How do I cancel my registration?"),
    ).toBeInTheDocument();
    expect(
      screen.queryByText("How do I create an event?"),
    ).not.toBeInTheDocument();
  });

  it("shows empty state when no FAQ matches search", () => {
    render(<HelpPage />);
    const searchInput = screen.getByPlaceholderText("Search FAQ...");

    fireEvent.change(searchInput, {
      target: { value: "xyznonexistent" },
    });

    expect(
      screen.getByText("No matching questions found."),
    ).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Contact form validation
  // -----------------------------------------------------------------------

  it("shows error when submitting without selecting a subject", async () => {
    render(<HelpPage />);
    fireEvent.click(screen.getByText("Send Message"));

    await waitFor(() => {
      expect(
        screen.getByText("Please select a topic."),
      ).toBeInTheDocument();
    });
  });

  it("shows error when submitting without email", async () => {
    render(<HelpPage />);
    const subjectSelect = screen.getByLabelText("Subject");
    fireEvent.change(subjectSelect, { target: { value: "Bug Report" } });
    fireEvent.click(screen.getByText("Send Message"));

    await waitFor(() => {
      expect(
        screen.getByText("Please enter your email."),
      ).toBeInTheDocument();
    });
  });

  it("shows error when submitting without message", async () => {
    render(<HelpPage />);
    const subjectSelect = screen.getByLabelText("Subject");
    const emailInput = screen.getByLabelText("Email");

    fireEvent.change(subjectSelect, { target: { value: "Bug Report" } });
    fireEvent.change(emailInput, { target: { value: "test@example.com" } });
    fireEvent.click(screen.getByText("Send Message"));

    await waitFor(() => {
      expect(
        screen.getByText("Please enter a message."),
      ).toBeInTheDocument();
    });
  });

  // -----------------------------------------------------------------------
  // Contact form submission
  // -----------------------------------------------------------------------

  it("submits the contact form successfully", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({ id: "abc123", message: "Message received." }),
    });
    vi.stubGlobal("fetch", mockFetch);

    render(<HelpPage />);

    fireEvent.change(screen.getByLabelText("Subject"), {
      target: { value: "Bug Report" },
    });
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "test@example.com" },
    });
    fireEvent.change(screen.getByLabelText("Message"), {
      target: { value: "Something is broken" },
    });
    fireEvent.click(screen.getByText("Send Message"));

    await waitFor(() => {
      expect(
        screen.getByText(/Message sent successfully/),
      ).toBeInTheDocument();
    });

    expect(mockFetch).toHaveBeenCalledOnce();
    const [url, options] = mockFetch.mock.calls[0];
    expect(url).toContain("/contact/");
    expect(options.method).toBe("POST");
    expect(options.body).toBeInstanceOf(FormData);
  });

  it("handles server error on contact form submission", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      json: () => Promise.resolve({ detail: "Server error occurred" }),
    });
    vi.stubGlobal("fetch", mockFetch);

    render(<HelpPage />);

    fireEvent.change(screen.getByLabelText("Subject"), {
      target: { value: "General Inquiry" },
    });
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "user@test.com" },
    });
    fireEvent.change(screen.getByLabelText("Message"), {
      target: { value: "Need help" },
    });
    fireEvent.click(screen.getByText("Send Message"));

    await waitFor(() => {
      expect(
        screen.getByText("Server error occurred"),
      ).toBeInTheDocument();
    });
  });

  // -----------------------------------------------------------------------
  // Navigation links
  // -----------------------------------------------------------------------

  it("has correct navigation links in the header", () => {
    render(<HelpPage />);
    const browseLinks = screen.getAllByRole("link", { name: "Browse Events" });
    expect(browseLinks.some((el) => el.getAttribute("href") === "/")).toBe(true);
    const createLink = screen.getByRole("link", { name: "Create Event" });
    expect(createLink).toHaveAttribute("href", "/create");
  });

  it("has a help center link in the footer", () => {
    render(<HelpPage />);
    const helpLinks = screen.getAllByRole("link", { name: "Help Center" });
    const footerHelp = helpLinks.find(
      (el) => el.getAttribute("href") === "/help",
    );
    expect(footerHelp).toBeDefined();
  });
});
