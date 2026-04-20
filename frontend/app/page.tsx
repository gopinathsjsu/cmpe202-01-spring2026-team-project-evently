import { getApiBase } from "@/lib/api-base";
import DiscoverPageClient, {
  type DiscoverPageInitialData,
} from "./discover-page-client";

export const dynamic = "force-dynamic";

async function fetchInitialEvents(): Promise<DiscoverPageInitialData> {
  const search = new URLSearchParams({
    page: "1",
    page_size: "12",
    sort_by: "start_time",
    sort_order: "asc",
  });

  try {
    const res = await fetch(`${getApiBase()}/events/?${search.toString()}`, {
      cache: "no-store",
    });
    if (!res.ok) {
      throw new Error(`Failed to fetch events: ${res.status}`);
    }
    return (await res.json()) as DiscoverPageInitialData;
  } catch (error) {
    console.error("Failed to fetch initial events for Discover page", error);
    return { items: [], total: 0 };
  }
}

export default async function DiscoverPage() {
  const initialData = await fetchInitialEvents();
  return <DiscoverPageClient initialData={initialData} />;
}
