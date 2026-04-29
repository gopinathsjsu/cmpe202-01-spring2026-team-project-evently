"use client";

import { useCallback, useEffect, useState } from "react";
import { usePathname } from "next/navigation";

import { EventImageUploadButton } from "@/app/components/event-image-upload-button";
import Navbar from "@/app/components/navbar";
import { ApiError, apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { EventCategory, PendingEventListItem } from "@/lib/types";

// ---------------------------------------------------------------------------
// Icons
// ---------------------------------------------------------------------------

function ShieldCheckIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
    </svg>
  );
}

function CheckIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
    </svg>
  );
}

function XMarkIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
    </svg>
  );
}

function CalendarIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
    </svg>
  );
}

function MapPinIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
    </svg>
  );
}

function UserIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
    </svg>
  );
}

function ExclamationIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const CATEGORY_COLORS: Record<EventCategory, string> = {
  Music: "bg-purple-100 text-purple-800",
  Business: "bg-blue-100 text-blue-800",
  Arts: "bg-pink-100 text-pink-800",
  Food: "bg-orange-100 text-orange-800",
  Sports: "bg-green-100 text-green-800",
  Education: "bg-yellow-100 text-yellow-800",
  Theater: "bg-red-100 text-red-800",
  Comedy: "bg-amber-100 text-amber-800",
  Festival: "bg-teal-100 text-teal-800",
  Conference: "bg-indigo-100 text-indigo-800",
  Workshop: "bg-cyan-100 text-cyan-800",
  Other: "bg-gray-100 text-gray-800",
};

function formatDateRange(start: string, end: string): string {
  const s = new Date(start);
  const e = new Date(end);
  const dateStr = s.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
  const startTime = s.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", hour12: true });
  const endTime = e.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", hour12: true });
  return `${dateStr} · ${startTime} – ${endTime}`;
}

function formatLocation(loc: PendingEventListItem["location"], isOnline: boolean): string {
  if (isOnline) return "Online Event";
  return loc.venue_name ? `${loc.venue_name}, ${loc.city}` : `${loc.city}, ${loc.state}`;
}

function formatPrice(price: number): string {
  return price === 0 ? "Free" : `$${price.toFixed(2)}`;
}

// ---------------------------------------------------------------------------
// Skeleton row
// ---------------------------------------------------------------------------

function SkeletonRow() {
  return (
    <div className="animate-pulse rounded-lg border border-gray-200 bg-white p-5">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 space-y-3">
          <div className="flex items-center gap-3">
            <div className="h-5 w-24 rounded-full bg-gray-200" />
            <div className="h-5 w-48 rounded bg-gray-200" />
          </div>
          <div className="h-4 w-64 rounded bg-gray-200" />
          <div className="h-4 w-40 rounded bg-gray-200" />
          <div className="h-4 w-72 rounded bg-gray-200" />
        </div>
        <div className="flex gap-2">
          <div className="h-9 w-24 rounded-md bg-gray-200" />
          <div className="h-9 w-20 rounded-md bg-gray-200" />
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Event row
// ---------------------------------------------------------------------------

interface EventRowProps {
  event: PendingEventListItem;
  onApprove: (id: number) => void;
  onReject: (id: number) => void;
  onImageUploaded: (id: number, imageUrl: string) => void;
  actionError: string | null;
  actionPending: boolean;
}

function EventRow({
  event,
  onApprove,
  onReject,
  onImageUploaded,
  actionError,
  actionPending,
}: EventRowProps) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-5 transition-shadow hover:shadow-sm">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex-1 space-y-2 min-w-0">
          {/* Title + category */}
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${CATEGORY_COLORS[event.category]}`}
            >
              {event.category}
            </span>
            <h3 className="text-base font-semibold text-gray-900 truncate">{event.title}</h3>
          </div>

          {/* About */}
          <p className="text-sm text-gray-600 line-clamp-2">{event.about}</p>

          {/* Meta */}
          <div className="flex flex-wrap gap-x-5 gap-y-1 text-sm text-gray-500">
            <span className="flex items-center gap-1.5">
              <CalendarIcon className="h-4 w-4 shrink-0" />
              {formatDateRange(event.start_time, event.end_time)}
            </span>
            <span className="flex items-center gap-1.5">
              <MapPinIcon className="h-4 w-4 shrink-0" />
              {formatLocation(event.location, event.is_online)}
            </span>
            <span className="flex items-center gap-1.5">
              <UserIcon className="h-4 w-4 shrink-0" />
              Organizer #{event.organizer_user_id}
            </span>
          </div>

          {/* Price + capacity */}
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
            <span className="font-medium text-gray-900">{formatPrice(event.price)}</span>
            <span className="text-gray-500">Capacity: {event.total_capacity}</span>
          </div>

          {actionError && (
            <div className="flex items-center gap-1.5 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
              <ExclamationIcon className="h-4 w-4 shrink-0" />
              {actionError}
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="flex shrink-0 flex-wrap justify-end gap-2">
          <EventImageUploadButton
            eventId={event.id}
            className="inline-flex cursor-pointer items-center justify-center rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50"
            onUploaded={(imageUrl) => onImageUploaded(event.id, imageUrl)}
          />
          <button
            type="button"
            disabled={actionPending}
            onClick={() => onApprove(event.id)}
            className="inline-flex items-center gap-1.5 rounded-md bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <CheckIcon className="h-4 w-4" />
            Approve
          </button>
          <button
            type="button"
            disabled={actionPending}
            onClick={() => onReject(event.id)}
            className="inline-flex items-center gap-1.5 rounded-md border border-red-300 bg-white px-4 py-2 text-sm font-medium text-red-600 hover:bg-red-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <XMarkIcon className="h-4 w-4" />
            Reject
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

interface EventActionState {
  pending: boolean;
  error: string | null;
}

export default function AdminPendingEventsPage() {
  const pathname = usePathname();
  const { user, loading: authLoading } = useAuth();
  const isAdmin = user?.roles.includes("admin") ?? false;
  const signinHref = pathname ? `/signin?next=${encodeURIComponent(pathname)}` : "/signin";

  const [events, setEvents] = useState<PendingEventListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionStates, setActionStates] = useState<Record<number, EventActionState>>({});

  const loadPendingEvents = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const data = await apiFetch<PendingEventListItem[]>("/events/pending");
      setEvents(data);
    } catch (err) {
      setEvents([]);
      setLoadError(
        err instanceof ApiError
          ? String(err.detail)
          : "Failed to load pending events.",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (authLoading || !isAdmin) {
      return;
    }

    loadPendingEvents();
  }, [authLoading, isAdmin, loadPendingEvents]);

  function setActionState(id: number, state: Partial<EventActionState>) {
    setActionStates((prev) => {
      const current = prev[id] ?? { pending: false, error: null };
      return { ...prev, [id]: { ...current, ...state } };
    });
  }

  async function handleApprove(id: number) {
    const original = events.find((e) => e.id === id);
    setActionState(id, { pending: true, error: null });
    setEvents((prev) => prev.filter((e) => e.id !== id));

    try {
      await apiFetch(`/events/${id}/approve`, { method: "POST" });
      setActionStates((prev) => {
        const next = { ...prev };
        delete next[id];
        return next;
      });
    } catch (err) {
      // Restore the event on failure
      if (original) setEvents((prev) => [original, ...prev].sort((a, b) => a.id - b.id));
      const message =
        err instanceof ApiError ? String(err.detail) : "Failed to approve event. Please try again.";
      setActionState(id, { pending: false, error: message });
    }
  }

  async function handleReject(id: number) {
    const original = events.find((e) => e.id === id);
    setActionState(id, { pending: true, error: null });
    setEvents((prev) => prev.filter((e) => e.id !== id));

    try {
      await apiFetch(`/events/${id}/reject`, { method: "POST" });
      setActionStates((prev) => {
        const next = { ...prev };
        delete next[id];
        return next;
      });
    } catch (err) {
      if (original) setEvents((prev) => [original, ...prev].sort((a, b) => a.id - b.id));
      const message =
        err instanceof ApiError ? String(err.detail) : "Failed to reject event. Please try again.";
      setActionState(id, { pending: false, error: message });
    }
  }

  function handleImageUploaded(id: number, imageUrl: string) {
    setEvents((current) =>
      current.map((event) =>
        event.id === id ? { ...event, image_url: imageUrl } : event,
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // Access guard
  // ---------------------------------------------------------------------------
  if (authLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50">
        <div className="rounded-lg border border-gray-200 bg-white p-10 text-center shadow-sm">
          <ShieldCheckIcon className="mx-auto h-12 w-12 animate-pulse text-gray-400" />
          <h2 className="mt-4 text-lg font-semibold text-gray-900">Checking access</h2>
          <p className="mt-2 text-sm text-gray-600">Verifying your administrator permissions.</p>
        </div>
      </div>
    );
  }

  if (!user || !isAdmin) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50">
        <div className="rounded-lg border border-gray-200 bg-white p-10 text-center shadow-sm">
          <ShieldCheckIcon className="mx-auto h-12 w-12 text-gray-400" />
          <h2 className="mt-4 text-lg font-semibold text-gray-900">Access Denied</h2>
          <p className="mt-2 text-sm text-gray-600">You must be signed in as an administrator to view this page.</p>
          {!user ? (
            <a
              href={signinHref}
              className="mt-6 inline-block rounded-md bg-black px-5 py-2 text-sm font-medium text-white hover:bg-gray-800"
            >
              Sign In
            </a>
          ) : (
            <p className="mt-4 text-sm text-gray-500">Signed in as {user.email}</p>
          )}
        </div>
      </div>
    );
  }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------
  return (
    <div className="min-h-screen bg-white text-black font-sans antialiased">
      <Navbar />

      <main className="mx-auto max-w-4xl px-4 py-10 sm:px-6 lg:px-8">
        {/* Page heading */}
        <div className="mb-8 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Pending Event Approvals</h1>
            <p className="mt-1 text-sm text-gray-600">
              Review and approve or reject events submitted by organizers.
            </p>
          </div>
          {!loading && !loadError && (
            <span className="inline-flex h-8 min-w-[2rem] items-center justify-center rounded-full bg-black px-2.5 text-sm font-semibold text-white">
              {events.length}
            </span>
          )}
        </div>

        {/* Load error banner */}
        {loadError && (
          <div className="mb-6 flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">
            <ExclamationIcon className="mt-0.5 h-5 w-5 shrink-0 text-red-500" />
            <div>
              <p className="font-medium">Failed to load pending events</p>
              <p className="mt-0.5">{loadError}</p>
            </div>
            <button
              type="button"
              onClick={loadPendingEvents}
              className="ml-auto shrink-0 rounded border border-red-300 bg-white px-3 py-1 text-xs font-medium text-red-700 hover:bg-red-50"
            >
              Retry
            </button>
          </div>
        )}

        {/* Event list */}
        <div className="space-y-4">
          {loading ? (
            <>
              <SkeletonRow />
              <SkeletonRow />
              <SkeletonRow />
            </>
          ) : events.length === 0 ? (
            <div className="rounded-lg border border-dashed border-gray-300 bg-white py-16 text-center">
              <ShieldCheckIcon className="mx-auto h-10 w-10 text-gray-400" />
              <p className="mt-3 text-sm font-medium text-gray-900">No pending events</p>
              <p className="mt-1 text-sm text-gray-500">All submitted events have been reviewed.</p>
            </div>
          ) : (
            events.map((event) => (
              <EventRow
                key={event.id}
                event={event}
                onApprove={handleApprove}
                onReject={handleReject}
                onImageUploaded={handleImageUploaded}
                actionPending={actionStates[event.id]?.pending ?? false}
                actionError={actionStates[event.id]?.error ?? null}
              />
            ))
          )}
        </div>
      </main>
    </div>
  );
}
