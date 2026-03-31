"use client";

import { useCallback, useEffect, useState } from "react";
import { AuthNav } from "@/components/auth-nav";
import { getApiBase } from "@/lib/api-base";

type EventCategory =
  | "Music"
  | "Business"
  | "Arts"
  | "Food"
  | "Sports"
  | "Education"
  | "Theater"
  | "Comedy"
  | "Festival"
  | "Conference"
  | "Workshop"
  | "Other";

interface EventFromApi {
  id: number;
  title: string;
  price: number;
  start_time: string;
  category: EventCategory;
  is_online: boolean;
  image_url: string | null;
  location: { venue_name: string | null; city: string; state: string };
  attending_count: number;
}

function formatEventDate(iso: string): string {
  const d = new Date(iso);
  const day = d.toLocaleDateString("en-US", { weekday: "short" }).toUpperCase();
  const month = d.toLocaleDateString("en-US", { month: "short" }).toUpperCase();
  return `${day}, ${month} ${d.getDate()} • ${d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", hour12: true })}`;
}
function formatPrice(price: number): string {
  return price === 0 ? "Free" : `$${price.toFixed(2)}`;
}
function formatAttending(n: number): string {
  return n >= 1000 ? `${(n / 1000).toFixed(1)}K attending` : `${n} attending`;
}
function formatLocation(
  loc: EventFromApi["location"],
  isOnline: boolean,
): string {
  if (isOnline) return "Online Event";
  return loc.venue_name
    ? `${loc.venue_name}, ${loc.city}`
    : `${loc.city}, ${loc.state}`;
}

async function fetchEvents(params: {
  page?: number;
  page_size?: number;
  q?: string;
  city?: string;
  category?: EventCategory;
  sort_by?: string;
  sort_order?: string;
  is_online?: boolean;
  price_type?: string;
  date_preset?: string;
}) {
  const search = new URLSearchParams();
  search.set("page", String(params.page ?? 1));
  search.set("page_size", String(params.page_size ?? 12));
  search.set("sort_by", params.sort_by ?? "start_time");
  search.set("sort_order", params.sort_order ?? "asc");
  if (params.q?.trim()) search.set("q", params.q.trim());
  if (params.city?.trim()) search.set("city", params.city.trim());
  if (params.category) search.set("category", params.category);
  if (params.is_online !== undefined)
    search.set("is_online", String(params.is_online));
  if (params.price_type) search.set("price_type", params.price_type);
  if (params.date_preset) search.set("date_preset", params.date_preset);
  const res = await fetch(`${getApiBase()}/events/?${search.toString()}`);
  if (!res.ok) throw new Error("Failed to fetch events");
  return res.json() as Promise<{ items: EventFromApi[]; total: number }>;
}

// Icons
function SearchIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="m21 21-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
      />
    </svg>
  );
}
function MapPinIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"
      />
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"
      />
    </svg>
  );
}
function HeartIcon({
  filled,
  className,
}: {
  filled?: boolean;
  className?: string;
}) {
  return (
    <svg
      className={className}
      fill={filled ? "currentColor" : "none"}
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z"
      />
    </svg>
  );
}
function GlobeIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9"
      />
    </svg>
  );
}

const CATEGORIES: { name: EventCategory; icon: string }[] = [
  { name: "Music", icon: "♪" },
  { name: "Business", icon: "💼" },
  { name: "Arts", icon: "🎨" },
  { name: "Food", icon: "🍴" },
  { name: "Sports", icon: "🏋" },
  { name: "Education", icon: "🎓" },
];

const FOOTER_LINKS = {
  "Use Evently": ["Browse Events", "Create Event", "Pricing", "Mobile App"],
  "Plan Events": [
    "Event Planning",
    "Sell Tickets",
    "Event Marketing",
    "Resources",
  ],
  Connect: ["About Us", "Contact", "Help Center", "Blog"],
};

const PAGE_SIZE = 12;

export default function DiscoverPage() {
  const [events, setEvents] = useState<EventFromApi[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [searchQuery, setSearchQuery] = useState("");
  const [locationQuery, setLocationQuery] = useState("");
  const [categoryFilter, setCategoryFilter] = useState<EventCategory | null>(
    null,
  );
  const [sortBy, setSortBy] = useState<"start_time" | "price" | "title">(
    "start_time",
  );
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("asc");
  const [dateFilters, setDateFilters] = useState<string[]>([]);
  const [eventTypeFilters, setEventTypeFilters] = useState<string[]>([]);
  const [priceFilter, setPriceFilter] = useState<string | null>(null);

  const resolvedIsOnline =
    eventTypeFilters.includes("Online") &&
    !eventTypeFilters.includes("In-Person")
      ? true
      : eventTypeFilters.includes("In-Person") &&
          !eventTypeFilters.includes("Online")
        ? false
        : undefined;

  const resolvedDatePreset = dateFilters.includes("Today")
    ? "today"
    : dateFilters.includes("This Week")
      ? "this_week"
      : dateFilters.includes("This Month")
        ? "this_month"
        : undefined;

  const resolvedPriceType =
    priceFilter === "Free"
      ? "free"
      : priceFilter === "Paid"
        ? "paid"
        : undefined;

  const loadEvents = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchEvents({
        page,
        page_size: PAGE_SIZE,
        q: searchQuery || undefined,
        city: locationQuery || undefined,
        category: categoryFilter ?? undefined,
        sort_by: sortBy,
        sort_order: sortOrder,
        is_online: resolvedIsOnline,
        price_type: resolvedPriceType,
        date_preset: resolvedDatePreset,
      });
      setEvents(data.items);
      setTotal(data.total);
    } catch {
      setEvents([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [
    page,
    searchQuery,
    locationQuery,
    categoryFilter,
    sortBy,
    sortOrder,
    resolvedIsOnline,
    resolvedPriceType,
    resolvedDatePreset,
  ]);

  useEffect(() => {
    loadEvents();
  }, [loadEvents]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
  };

  const handleClearAll = () => {
    setSearchQuery("");
    setLocationQuery("");
    setCategoryFilter(null);
    setPage(1);
    setDateFilters([]);
    setEventTypeFilters([]);
    setPriceFilter(null);
    setSortBy("start_time");
    setSortOrder("asc");
  };

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="min-h-screen bg-white text-black font-sans antialiased">
      <header className="sticky top-0 z-50 border-b border-gray-200 bg-white">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-6 px-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-8">
            <a href="/" className="flex items-center gap-2">
              <span className="flex h-8 w-8 items-center justify-center rounded bg-black text-white text-sm font-bold">E</span>
              <span className="text-lg font-semibold">Evently</span>
            </a>
            <nav className="hidden items-center gap-6 md:flex">
              <a href="/discover" className="text-sm font-medium text-black">Browse Events</a>
              <a href="/create" className="text-sm font-medium text-gray-700 hover:text-black">Create Event</a>
              <a href="/tickets" className="text-sm font-medium text-gray-700 hover:text-black">My Tickets</a>
            </nav>
          </div>
          <div className="flex flex-1 items-center justify-center max-w-md px-4">
            <div className="relative w-full">
              <SearchIcon className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
              <input
                type="search"
                placeholder="Search events..."
                className="w-full rounded-md border border-gray-300 bg-gray-50 py-2 pl-9 pr-4 text-sm placeholder:text-gray-500 focus:border-black focus:outline-none focus:ring-1 focus:ring-black"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>
          </div>
          <AuthNav />
        </div>
      </header>

      <main>
        <section className="border-b border-gray-200 bg-white py-16 sm:py-20">
          <div className="mx-auto max-w-7xl px-4 text-left sm:px-6 lg:px-8">
            <h1 className="text-3xl font-bold tracking-tight text-black sm:text-4xl">
              Discover Events That Matter
            </h1>
            <p className="mt-3 text-lg text-gray-600">
              Find and attend events near you or create your own
            </p>
            <form
              onSubmit={handleSearch}
              className="mt-8 flex flex-col gap-3 sm:flex-row sm:items-stretch sm:justify-start"
            >
              <div className="relative min-w-0 sm:min-w-[200px] sm:max-w-[280px] rounded-md border border-gray-300 bg-gray-50">
                <SearchIcon className="absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-gray-400" />
                <input
                  type="search"
                  placeholder="Search for events"
                  className="w-full rounded-md bg-transparent py-3 pl-11 pr-4 text-base placeholder:text-gray-500 focus:border-black focus:outline-none focus:ring-0"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              </div>
              <div className="relative min-w-0 sm:min-w-[200px] sm:max-w-[280px] rounded-md border border-gray-300 bg-gray-50">
                <MapPinIcon className="absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-gray-400" />
                <input
                  type="text"
                  placeholder="Location"
                  className="w-full rounded-md bg-transparent py-3 pl-11 pr-4 text-base placeholder:text-gray-500 focus:border-black focus:outline-none focus:ring-0"
                  value={locationQuery}
                  onChange={(e) => setLocationQuery(e.target.value)}
                />
              </div>
              <button
                type="submit"
                className="rounded-md border border-black bg-black px-6 py-3 text-base font-medium text-white hover:bg-gray-800"
              >
                Search
              </button>
            </form>
          </div>
        </section>

        {/* Browse by Category */}
        <section className="border-b border-gray-200 bg-white py-10">
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
            <h2 className="text-xl font-bold text-black">Browse by Category</h2>
            <div className="mt-6 flex flex-wrap justify-between gap-4 pb-2">
              {CATEGORIES.map((cat) => (
                <button
                  key={cat.name}
                  type="button"
                  onClick={() => {
                    setCategoryFilter((c) =>
                      c === cat.name ? null : cat.name,
                    );
                    setPage(1);
                  }}
                  className={`flex min-w-[120px] flex-col items-center gap-2 rounded-lg border px-6 py-4 text-center transition-colors hover:border-gray-400 hover:bg-gray-50 ${
                    categoryFilter === cat.name
                      ? "border-black bg-gray-50"
                      : "border-gray-300 bg-white"
                  }`}
                >
                  <span className="text-2xl">{cat.icon}</span>
                  <span className="text-sm font-medium text-black">
                    {cat.name}
                  </span>
                </button>
              ))}
            </div>
          </div>
        </section>

        <section className="border-b border-gray-200 bg-white py-10">
          <div className="mx-auto flex max-w-7xl gap-8 px-4 sm:px-6 lg:px-8">
            <aside className="hidden w-56 shrink-0 lg:block">
              <div className="rounded-lg border border-gray-200 bg-white p-4">
                <div className="flex items-center justify-between">
                  <h3 className="font-bold text-black">Filters</h3>
                  <button
                    type="button"
                    onClick={handleClearAll}
                    className="text-sm text-blue-600 hover:text-blue-700"
                  >
                    Clear all
                  </button>
                </div>
                <div>
                  <h4 className="mt-4 font-semibold text-black">Date</h4>
                  <ul className="mt-3 space-y-2">
                    {["Today", "This Week", "This Month", "Custom Date"].map(
                      (opt) => (
                        <li key={opt} className="flex items-center gap-2">
                          <input
                            type="checkbox"
                            id={`date-${opt}`}
                            className="h-4 w-4 rounded border-gray-300 text-black focus:ring-black"
                            checked={dateFilters.includes(opt)}
                            onChange={(e) =>
                              setDateFilters((prev) =>
                                e.target.checked
                                  ? [...prev, opt]
                                  : prev.filter((x) => x !== opt),
                              )
                            }
                          />
                          <label
                            htmlFor={`date-${opt}`}
                            className="text-sm text-gray-700"
                          >
                            {opt}
                          </label>
                        </li>
                      ),
                    )}
                  </ul>
                </div>
                <div className="mt-6">
                  <h4 className="font-semibold text-black">Event Type</h4>
                  <ul className="mt-3 space-y-2">
                    {["In-Person", "Online"].map((opt) => (
                      <li key={opt} className="flex items-center gap-2">
                        <input
                          type="checkbox"
                          id={`type-${opt}`}
                          className="h-4 w-4 rounded border-gray-300 text-black focus:ring-black"
                          checked={eventTypeFilters.includes(opt)}
                          onChange={(e) =>
                            setEventTypeFilters((prev) =>
                              e.target.checked
                                ? [...prev, opt]
                                : prev.filter((x) => x !== opt),
                            )
                          }
                        />
                        <label
                          htmlFor={`type-${opt}`}
                          className="text-sm text-gray-700"
                        >
                          {opt}
                        </label>
                      </li>
                    ))}
                  </ul>
                </div>
                <div className="mt-6">
                  <h4 className="font-semibold text-black">Price</h4>
                  <ul className="mt-3 space-y-2">
                    {["Free", "Paid"].map((opt) => (
                      <li key={opt} className="flex items-center gap-2">
                        <input
                          type="radio"
                          name="price"
                          id={`price-${opt}`}
                          className="h-4 w-4 border-gray-300 text-black focus:ring-black"
                          checked={priceFilter === opt}
                          onChange={() => setPriceFilter(opt)}
                        />
                        <label
                          htmlFor={`price-${opt}`}
                          className="text-sm text-gray-700"
                        >
                          {opt}
                        </label>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </aside>

            <div className="min-w-0 flex-1">
              <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                <p className="text-sm text-gray-600">
                  {loading ? "Loading…" : `Showing ${total} events`}
                </p>
                <div className="flex items-center gap-2">
                  <span className="text-sm text-gray-600">Sort by:</span>
                  <select
                    className="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-black focus:border-black focus:outline-none focus:ring-1 focus:ring-black"
                    value={sortBy}
                    onChange={(e) =>
                      setSortBy(
                        e.target.value as "start_time" | "price" | "title",
                      )
                    }
                  >
                    <option value="start_time">Relevance</option>
                    <option value="price">Price</option>
                    <option value="title">Title</option>
                  </select>
                  <select
                    className="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-black focus:border-black focus:outline-none focus:ring-1 focus:ring-black"
                    value={sortOrder}
                    onChange={(e) =>
                      setSortOrder(e.target.value as "asc" | "desc")
                    }
                  >
                    <option value="asc">Asc</option>
                    <option value="desc">Desc</option>
                  </select>
                </div>
              </div>

              {loading ? (
                <div className="grid gap-6 sm:grid-cols-2 xl:grid-cols-3">
                  {[1, 2, 3, 4, 5, 6].map((i) => (
                    <div
                      key={i}
                      className="overflow-hidden rounded-lg border border-gray-200 bg-gray-100 animate-pulse"
                    >
                      <div className="aspect-[16/10] w-full bg-gray-200" />
                      <div className="space-y-2 p-4">
                        <div className="h-3 w-1/4 rounded bg-gray-200" />
                        <div className="h-5 w-3/4 rounded bg-gray-200" />
                        <div className="h-4 w-full rounded bg-gray-200" />
                      </div>
                    </div>
                  ))}
                </div>
              ) : events.length === 0 ? (
                <p className="py-12 text-center text-gray-500">
                  No events found. Try different filters or search.
                </p>
              ) : (
                <div className="grid gap-6 sm:grid-cols-2 xl:grid-cols-3">
                  {events.map((event) => (
                    <article
                      key={event.id}
                      className="overflow-hidden rounded-lg border border-gray-200 bg-white transition-shadow hover:shadow-md"
                    >
                      <div
                        className="aspect-[16/10] w-full bg-gray-200"
                        aria-label="Event image"
                      >
                        {event.image_url && (
                          <img
                            src={event.image_url}
                            alt=""
                            className="h-full w-full object-cover"
                          />
                        )}
                      </div>
                      <div className="relative p-4">
                        <button
                          type="button"
                          className="absolute right-4 top-4 text-gray-400 hover:text-red-500"
                          aria-label="Favorite"
                        >
                          <HeartIcon filled={false} className="h-5 w-5" />
                        </button>
                        <p className="text-xs font-medium uppercase tracking-wide text-gray-500">
                          {formatEventDate(event.start_time)}
                        </p>
                        <h3 className="mt-1 text-lg font-bold text-black">
                          {event.title}
                        </h3>
                        <p className="mt-1 flex items-center gap-1 text-sm text-gray-600">
                          {event.is_online ? (
                            <GlobeIcon className="h-4 w-4 shrink-0" />
                          ) : (
                            <MapPinIcon className="h-4 w-4 shrink-0" />
                          )}
                          <span>
                            {formatLocation(event.location, event.is_online)}
                          </span>
                        </p>
                        <p className="mt-2 text-sm font-medium text-black">
                          {formatPrice(event.price)}
                        </p>
                        <p className="mt-1 text-sm text-gray-500">
                          {formatAttending(event.attending_count)}
                        </p>
                      </div>
                    </article>
                  ))}
                </div>
              )}

              {!loading && total > 0 && (
                <nav
                  className="mt-8 flex items-center justify-center gap-2"
                  aria-label="Pagination"
                >
                  <button
                    type="button"
                    className="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
                    disabled={page <= 1}
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                  >
                    &larr;
                  </button>
                  {(() => {
                    const maxVisible = 5;
                    let start = Math.max(1, page - Math.floor(maxVisible / 2));
                    const end = Math.min(totalPages, start + maxVisible - 1);
                    start = Math.max(1, end - maxVisible + 1);
                    return Array.from({ length: end - start + 1 }, (_, i) => {
                      const p = start + i;
                      return (
                        <button
                          key={p}
                          type="button"
                          className={`rounded-md px-3 py-2 text-sm font-medium ${page === p ? "bg-black text-white" : "border border-gray-300 bg-white text-gray-700 hover:bg-gray-50"}`}
                          onClick={() => setPage(p)}
                        >
                          {p}
                        </button>
                      );
                    });
                  })()}
                  <button
                    type="button"
                    className="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
                    disabled={page >= totalPages}
                    onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  >
                    &rarr;
                  </button>
                </nav>
              )}
            </div>
          </div>
        </section>

        <section className="border-b border-gray-200 bg-white py-16 text-center">
          <div className="mx-auto max-w-2xl px-4">
            <h2 className="text-3xl font-bold text-black">
              Host Your Own Event
            </h2>
            <p className="mt-3 text-lg text-gray-600">
              Create and manage events with our easy-to-use platform.
            </p>
            <a
              href="/create"
              className="mt-6 inline-block rounded-md bg-black px-6 py-3 text-base font-medium text-white hover:bg-gray-800"
            >
              Create Event
            </a>
          </div>
        </section>

        <footer className="bg-white py-12 text-gray-600">
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
            <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
              {Object.entries(FOOTER_LINKS).map(([heading, links]) => (
                <div key={heading}>
                  <h4 className="font-semibold text-black">{heading}</h4>
                  <ul className="mt-4 space-y-2">
                    {links.map((link) => (
                      <li key={link}>
                        <a
                          href={link === "Help Center" ? "/help" : "#"}
                          className="text-sm hover:text-black"
                        >
                          {link}
                        </a>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
              <div>
                <h4 className="font-semibold text-black">Follow Us</h4>
                <div className="mt-4 flex gap-4">
                  {["Facebook", "Twitter", "Instagram", "LinkedIn"].map(
                    (name) => (
                      <a
                        key={name}
                        href="#"
                        className="text-sm hover:text-black"
                        aria-label={name}
                      >
                        {name}
                      </a>
                    ),
                  )}
                </div>
              </div>
            </div>
            <div className="mt-12 flex flex-col items-center justify-between gap-4 border-t border-gray-200 pt-8 sm:flex-row">
              <p className="text-sm text-gray-500">
                © 2026 Evently. All rights reserved.
              </p>
              <div className="flex gap-6 text-sm">
                <a href="#" className="hover:text-black">
                  Privacy Policy
                </a>
                <a href="#" className="hover:text-black">
                  Terms of Service
                </a>
                <a href="#" className="hover:text-black">
                  Cookie Policy
                </a>
              </div>
            </div>
          </div>
        </footer>
      </main>
    </div>
  );
}
