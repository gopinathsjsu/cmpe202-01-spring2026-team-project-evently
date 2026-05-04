import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiFetch } from "@/lib/api";

import DiscoverPageClient from "./discover-page-client";

vi.mock("next/navigation", () => ({
  usePathname: vi.fn(() => "/"),
  useRouter: vi.fn(() => ({ push: vi.fn() })),
}));

vi.mock("@/lib/auth", () => ({
  useAuth: vi.fn(() => ({
    user: null,
    loading: false,
    error: null,
  })),
}));

vi.mock("@/lib/api", () => ({
  apiFetch: vi.fn(),
}));

const mockedApiFetch = vi.mocked(apiFetch);

describe("DiscoverPageClient", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it.each([
    { items: [], total: 0 },
    { items: [], total: 1 },
  ])(
    "fetches default events when server initial data has no items: %o",
    async (initialData) => {
      mockedApiFetch.mockResolvedValueOnce({
        items: [
          {
            id: 10,
            title: "Marathon Training Run",
            price: 0,
            start_time: "2026-03-22T06:30:00",
            category: "Sports",
            is_online: false,
            image_url: null,
            location: {
              venue_name: "Embarcadero",
              city: "San Francisco",
              state: "CA",
            },
            attending_count: 75,
          },
        ],
        total: 1,
      });

      render(<DiscoverPageClient initialData={initialData} />);

      await waitFor(() => {
        expect(mockedApiFetch).toHaveBeenCalledWith(
          "/events/?page=1&page_size=12&sort_by=start_time&sort_order=asc",
        );
      });

      expect(
        await screen.findByText("Marathon Training Run"),
      ).toBeInTheDocument();
      expect(screen.getByText("Showing 1 events")).toBeInTheDocument();
    },
  );
});
