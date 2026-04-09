import Image from "next/image";
import { notFound } from "next/navigation";
import Navbar from "@/app/components/navbar";
import { apiFetch } from "@/lib/api";
import type { EventDetail, UserDetail } from "@/lib/types";
import { EventLocationMapDynamic } from "./event-location-map-dynamic";
import { RegistrationCard } from "./registration-card";
import { ShareButtons } from "./share-buttons";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function buildInPersonAddressLine(event: {
  location: {
    venue_name: string | null;
    address: string;
    city: string;
    state: string;
    zip_code: string;
  };
}): string {
  const { venue_name, address, city, state, zip_code } = event.location;
  const parts = [address, `${city}, ${state} ${zip_code}`.trim()].filter(Boolean);
  const line = parts.join(" · ");
  return venue_name ? `${venue_name} — ${line}` : line;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString("en-US", {
    hour: "numeric",
    minute: "2-digit",
  });
}

function buildGoogleCalendarUrl(event: EventDetail): string {
  const fmt = (iso: string) => new Date(iso).toISOString().replace(/[-:]|\.\d{3}/g, "");
  const location = event.is_online
    ? "Online"
    : `${event.location.venue_name ?? ""} ${event.location.address}, ${event.location.city}, ${event.location.state} ${event.location.zip_code}`.trim();

  const params = new URLSearchParams({
    action: "TEMPLATE",
    text: event.title,
    dates: `${fmt(event.start_time)}/${fmt(event.end_time)}`,
    details: event.about.slice(0, 500),
    location,
  });
  return `https://calendar.google.com/calendar/render?${params}`;
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default async function EventDetailPage({
  params,
}: {
  params: Promise<{ eventId: string }>;
}) {
  const { eventId } = await params;

  let event: EventDetail;
  try {
    event = await apiFetch<EventDetail>(`/events/${eventId}`);
  } catch {
    notFound();
  }

  let organizer: UserDetail | null = null;
  try {
    organizer = await apiFetch<UserDetail>(`/users/${event.organizer_user_id}`);
  } catch {
    // User endpoint may not have data yet — fall back to ID display
  }

  const spotsLeft = event.total_capacity - event.attending_count;

  return (
    <div className="min-h-screen bg-white text-black font-sans antialiased">
      <Navbar />

      {/* ── Main content ────────────────────────────────────────── */}
      <main className="mx-auto max-w-6xl px-4 py-8">
        <h1 className="mb-6 text-sm font-medium text-zinc-500 dark:text-zinc-400">
          Event Detail Page
        </h1>

        <div className="grid gap-8 lg:grid-cols-[1fr_320px]">
          {/* ── Left column ──────────────────────────────────────── */}
          <div className="space-y-8">
            {/* Banner image */}
            <div className="relative aspect-[16/7] w-full overflow-hidden rounded-xl bg-zinc-200 dark:bg-zinc-800">
              {event.image_url ? (
                <Image
                  src={event.image_url}
                  alt={event.title}
                  fill
                  sizes="(min-width: 1024px) 896px, 100vw"
                  className="h-full w-full object-cover"
                />
              ) : (
                <div className="flex h-full items-center justify-center text-sm text-zinc-400">
                  Event Banner Image
                </div>
              )}
            </div>

            {/* Category + Title */}
            <div>
              <span className="text-sm font-medium text-zinc-500 dark:text-zinc-400">
                {event.category}
              </span>
              <h2 className="mt-1 text-3xl font-bold tracking-tight">{event.title}</h2>
            </div>

            {/* Organizer */}
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-zinc-200 text-sm font-bold text-zinc-500 dark:bg-zinc-700 dark:text-zinc-300">
                {organizer
                  ? `${organizer.first_name[0]}${organizer.last_name[0]}`
                  : (
                    <svg viewBox="0 0 24 24" className="h-5 w-5 fill-current">
                      <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                      <circle cx="12" cy="7" r="4" />
                    </svg>
                  )}
              </div>
              <div className="text-sm">
                <p className="font-medium">Organized by</p>
                <p className="text-zinc-500 dark:text-zinc-400">
                  {organizer
                    ? `${organizer.first_name} ${organizer.last_name}`
                    : `Organizer #${event.organizer_user_id}`}
                </p>
              </div>
            </div>

            {/* About */}
            <section>
              <h3 className="text-xl font-semibold">About This Event</h3>
              <div className="mt-3 space-y-3 text-zinc-600 dark:text-zinc-400">
                {event.about.split("\n\n").map((paragraph, i) => (
                  <p key={i}>{paragraph}</p>
                ))}
              </div>
            </section>

            {/* Schedule */}
            {event.schedule.length > 0 && (
              <section>
                <h3 className="text-xl font-semibold">Event Schedule</h3>
                <div className="mt-4 divide-y divide-zinc-200 dark:divide-zinc-800">
                  {event.schedule.map((entry, i) => (
                    <div key={i} className="flex gap-8 py-3">
                      <span className="w-24 shrink-0 text-sm font-medium">
                        {formatTime(entry.start_time)}
                      </span>
                      <span className="text-sm font-medium">{entry.description}</span>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* Location */}
            {!event.is_online && (
              <section>
                <h3 className="text-xl font-semibold">Location</h3>
                <div className="mt-3 flex items-start gap-2">
                  <svg
                    viewBox="0 0 24 24"
                    className="mt-0.5 h-5 w-5 shrink-0 fill-current text-zinc-700 dark:text-zinc-300"
                  >
                    <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
                    <circle cx="12" cy="10" r="3" fill="white" />
                  </svg>
                  <div className="text-sm">
                    {event.location.venue_name && (
                      <p className="font-medium">{event.location.venue_name}</p>
                    )}
                    <p className="text-zinc-500 dark:text-zinc-400">
                      {event.location.address
                        ? `${event.location.address}, ${event.location.city}, ${event.location.state} ${event.location.zip_code}`
                        : `${event.location.city}, ${event.location.state} ${event.location.zip_code}`}
                    </p>
                  </div>
                </div>
                <div className="mt-4">
                  <EventLocationMapDynamic
                    latitude={event.location.latitude}
                    longitude={event.location.longitude}
                    popupTitle={event.location.venue_name ?? "Event venue"}
                    mapsQuery={buildInPersonAddressLine(event)}
                  />
                </div>
              </section>
            )}

            {event.is_online && (
              <section>
                <h3 className="text-xl font-semibold">Location</h3>
                <p className="mt-3 text-sm text-zinc-500 dark:text-zinc-400">
                  This is an online event.
                </p>
              </section>
            )}
          </div>

          {/* ── Right sidebar ────────────────────────────────────── */}
          <aside className="space-y-6 lg:sticky lg:top-8 lg:self-start">
            <div className="rounded-xl border border-zinc-200 bg-white p-6 text-zinc-900 shadow-sm dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-100">
              {/* Date */}
              <div className="flex items-start gap-3">
                <svg viewBox="0 0 24 24" className="mt-0.5 h-5 w-5 shrink-0 fill-none stroke-current text-zinc-700 dark:text-zinc-200" strokeWidth={2}>
                  <rect x="3" y="4" width="18" height="18" rx="2" />
                  <line x1="16" y1="2" x2="16" y2="6" />
                  <line x1="8" y1="2" x2="8" y2="6" />
                  <line x1="3" y1="10" x2="21" y2="10" />
                </svg>
                <div className="text-sm">
                  <p className="text-xs font-medium text-zinc-400">Date</p>
                  <p className="font-medium text-zinc-900 dark:text-zinc-100">{formatDate(event.start_time)}</p>
                </div>
              </div>

              {/* Time */}
              <div className="mt-4 flex items-start gap-3">
                <svg viewBox="0 0 24 24" className="mt-0.5 h-5 w-5 shrink-0 fill-none stroke-current text-zinc-700 dark:text-zinc-200" strokeWidth={2}>
                  <circle cx="12" cy="12" r="10" />
                  <polyline points="12 6 12 12 16 14" />
                </svg>
                <div className="text-sm">
                  <p className="text-xs font-medium text-zinc-400">Time</p>
                  <p className="font-medium text-zinc-900 dark:text-zinc-100">
                    {formatTime(event.start_time)} - {formatTime(event.end_time)}
                  </p>
                </div>
              </div>

              {/* Capacity */}
              <div className="mt-4 flex items-start gap-3">
                <svg viewBox="0 0 24 24" className="mt-0.5 h-5 w-5 shrink-0 fill-none stroke-current text-zinc-700 dark:text-zinc-200" strokeWidth={2}>
                  <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                  <circle cx="9" cy="7" r="4" />
                  <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
                  <path d="M16 3.13a4 4 0 0 1 0 7.75" />
                </svg>
                <div className="text-sm">
                  <p className="text-xs font-medium text-zinc-400">Capacity</p>
                  <p className="font-medium text-zinc-900 dark:text-zinc-100">
                    {spotsLeft > 0 ? `${spotsLeft} spots left` : "Sold out"}
                  </p>
                </div>
              </div>

              <RegistrationCard
                addToCalendarUrl={buildGoogleCalendarUrl(event)}
                eventId={event.id}
                organizerUserId={event.organizer_user_id}
                price={event.price}
                spotsLeft={spotsLeft}
              />
            </div>

            {/* Share */}
            <div className="rounded-xl border border-zinc-200 bg-white p-6 text-zinc-900 shadow-sm dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-100">
              <h4 className="mb-3 text-sm font-semibold text-zinc-900 dark:text-zinc-100">Share Event</h4>
              <ShareButtons />
            </div>
          </aside>
        </div>
      </main>
    </div>
  );
}
