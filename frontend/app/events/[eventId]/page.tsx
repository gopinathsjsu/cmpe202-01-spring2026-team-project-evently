import Image from "next/image";
import { headers } from "next/headers";
import Link from "next/link";
import { notFound } from "next/navigation";
import Navbar from "@/app/components/navbar";
import { toBrowserSafeBackendUrl } from "@/lib/api-base";
import { initials } from "@/lib/profile-utils";
import type { EventDetail, UserDetail } from "@/lib/types";
import { EventLocationMapLoader } from "./event-location-map-loader";
import { OrganizerActions } from "./organizer-actions";
import { RegistrationCard } from "./registration-card";
import { ShareButtons } from "./share-buttons";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

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

async function buildEventShareUrl(eventId: string): Promise<string> {
  const requestHeaders = await headers();
  const host =
    requestHeaders.get("x-forwarded-host") ??
    requestHeaders.get("host") ??
    "localhost:3000";
  const protocol =
    requestHeaders.get("x-forwarded-proto") ??
    (host.startsWith("localhost") || host.startsWith("127.0.0.1")
      ? "http"
      : "https");

  return `${protocol}://${host}/events/${eventId}`;
}

async function fetchFromSameOriginApi<T>(path: string): Promise<T> {
  const requestHeaders = await headers();
  const host =
    requestHeaders.get("x-forwarded-host") ??
    requestHeaders.get("host") ??
    "localhost:3000";
  const protocol =
    requestHeaders.get("x-forwarded-proto") ??
    (host.startsWith("localhost") || host.startsWith("127.0.0.1")
      ? "http"
      : "https");
  const res = await fetch(`${protocol}://${host}/api${path}`, {
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`API request failed: ${res.status}`);
  }
  return (await res.json()) as T;
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
  const shareUrl = await buildEventShareUrl(eventId);

  let event: EventDetail;
  try {
    event = await fetchFromSameOriginApi<EventDetail>(`/events/${eventId}`);
  } catch {
    notFound();
  }

  let organizer: UserDetail | null = null;
  try {
    organizer = await fetchFromSameOriginApi<UserDetail>(
      `/users/${event.organizer_user_id}`,
    );
  } catch {
    // User endpoint may not have data yet — fall back to ID display
  }

  const spotsLeft = event.total_capacity - event.attending_count;
  const organizerBadgeInitials = organizer
    ? initials(organizer.first_name, organizer.last_name, organizer.username)
    : null;

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
                  src={toBrowserSafeBackendUrl(event.image_url)}
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
            <Link
              href={`/profile/${event.organizer_user_id}`}
              className="group inline-flex items-center gap-3 rounded-lg border border-zinc-200 px-3 py-2 text-left transition-colors hover:border-zinc-800 hover:bg-zinc-800 hover:text-white focus:outline-none focus:ring-2 focus:ring-black focus:ring-offset-2 dark:border-zinc-800 dark:hover:border-zinc-200 dark:hover:bg-zinc-200 dark:hover:text-black"
            >
              <div className="flex h-10 w-10 items-center justify-center overflow-hidden rounded-full bg-zinc-200 text-sm font-bold text-zinc-500 dark:bg-zinc-700 dark:text-zinc-300">
                {organizer?.profile_photo_url ? (
                  <Image
                    src={toBrowserSafeBackendUrl(organizer.profile_photo_url)}
                    alt=""
                    width={40}
                    height={40}
                    className="h-full w-full object-cover"
                  />
                ) : organizerBadgeInitials ? (
                  organizerBadgeInitials
                ) : (
                    <svg viewBox="0 0 24 24" className="h-5 w-5 fill-current">
                      <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                      <circle cx="12" cy="7" r="4" />
                    </svg>
                )}
              </div>
              <div className="text-sm">
                <p className="font-medium">Organized by</p>
                <p className="text-zinc-500 transition-colors group-hover:text-zinc-200 dark:text-zinc-400 dark:group-hover:text-zinc-700">
                  {organizer
                    ? `${organizer.first_name} ${organizer.last_name}`
                    : `Organizer #${event.organizer_user_id}`}
                </p>
              </div>
            </Link>

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
                      {event.location.city}, {event.location.state} {event.location.zip_code}
                    </p>
                  </div>
                </div>
                <EventLocationMapLoader
                  latitude={event.location.latitude}
                  longitude={event.location.longitude}
                />
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
                eventId={event.id}
                price={event.price}
                spotsLeft={spotsLeft}
              />
            </div>

            {/* Organizer tools */}
            <OrganizerActions
              eventId={event.id}
              organizerUserId={event.organizer_user_id}
              attendingCount={event.attending_count}
              totalCapacity={event.total_capacity}
            />

            {/* Share */}
            <div className="rounded-xl border border-zinc-200 bg-white p-6 text-zinc-900 shadow-sm dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-100">
              <h4 className="mb-3 text-sm font-semibold text-zinc-900 dark:text-zinc-100">Share Event</h4>
              <ShareButtons shareUrl={shareUrl} />
            </div>
          </aside>
        </div>
      </main>
    </div>
  );
}
