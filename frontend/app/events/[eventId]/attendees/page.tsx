"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import Navbar from "@/app/components/navbar";
import { ApiError, apiFetch } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";
import type {
  CheckInResponse,
  EventAttendeesResponse,
  EventAttendeeItem,
  RemoveAttendeeResponse,
  UndoCheckInResponse,
} from "@/lib/types";

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

function getInitials(first: string, last: string): string {
  return `${first[0] ?? ""}${last[0] ?? ""}`.toUpperCase();
}

function getApiErrorMessage(err: unknown, fallback: string): string {
  if (err instanceof ApiError && typeof err.detail === "string") return err.detail;
  if (err instanceof Error) return err.message;
  return fallback;
}

function downloadCsv(attendees: EventAttendeeItem[], eventTitle: string): void {
  const header = ["First Name", "Last Name", "Email", "Status", "Checked In At"];
  const rows = attendees.map((a) => [
    a.first_name,
    a.last_name,
    a.email,
    a.status === "checked_in" ? "Checked In" : "Going",
    a.checked_in_at ? formatDate(a.checked_in_at) + " " + formatTime(a.checked_in_at) : "",
  ]);
  const csv = [header, ...rows]
    .map((row) => row.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(","))
    .join("\n");
  const blob = new Blob([csv], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${eventTitle.replace(/[^a-z0-9]/gi, "_")}_attendees.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

// ---------------------------------------------------------------------------
// Icons
// ---------------------------------------------------------------------------

function SearchIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <circle cx="11" cy="11" r="8" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-4.35-4.35" />
    </svg>
  );
}

function DownloadIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
    </svg>
  );
}

function CheckIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
    </svg>
  );
}

function XMarkIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
    </svg>
  );
}

function UsersIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 19.128a9.38 9.38 0 002.625.372 9.337 9.337 0 004.121-.952 4.125 4.125 0 00-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 018.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0111.964-3.07M12 6.375a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zm8.25 2.25a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z" />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Stat card
// ---------------------------------------------------------------------------

function StatCard({
  label,
  value,
  sub,
  color,
}: {
  label: string;
  value: number | string;
  sub?: string;
  color: "zinc" | "green" | "blue" | "orange";
}) {
  const colorMap: Record<string, string> = {
    zinc: "bg-zinc-50 border-zinc-200 text-zinc-900",
    green: "bg-emerald-50 border-emerald-200 text-emerald-700",
    blue: "bg-blue-50 border-blue-200 text-blue-700",
    orange: "bg-orange-50 border-orange-200 text-orange-700",
  };
  return (
    <div className={`rounded-xl border p-4 ${colorMap[color]}`}>
      <p className="text-xs font-medium uppercase tracking-wide opacity-60">{label}</p>
      <p className="mt-1 text-2xl font-bold">{value}</p>
      {sub && <p className="mt-0.5 text-xs opacity-60">{sub}</p>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Attendee row
// ---------------------------------------------------------------------------

function AttendeeRow({
  attendee,
  onCheckIn,
  onUndoCheckIn,
  onRemove,
  busy,
}: {
  attendee: EventAttendeeItem;
  onCheckIn: (userId: number) => void;
  onUndoCheckIn: (userId: number) => void;
  onRemove: (userId: number, name: string) => void;
  busy: boolean;
}) {
  const isCheckedIn = attendee.status === "checked_in";
  const fullName = `${attendee.first_name} ${attendee.last_name}`;

  return (
    <div className="flex items-center gap-3 rounded-xl border border-gray-200 bg-white px-4 py-3 shadow-sm transition hover:shadow-md">
      {/* Avatar */}
      <div className="relative shrink-0">
        {attendee.profile_photo_url ? (
          <img
            src={attendee.profile_photo_url}
            alt={fullName}
            className="h-10 w-10 rounded-full object-cover"
          />
        ) : (
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-zinc-200 text-sm font-bold text-zinc-600">
            {getInitials(attendee.first_name, attendee.last_name)}
          </div>
        )}
        {isCheckedIn && (
          <span className="absolute -bottom-0.5 -right-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-emerald-500 ring-2 ring-white">
            <CheckIcon className="h-2.5 w-2.5 text-white" />
          </span>
        )}
      </div>

      {/* Info */}
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-semibold text-gray-900">{fullName}</p>
        <p className="truncate text-xs text-gray-500">{attendee.email}</p>
        {isCheckedIn && attendee.checked_in_at && (
          <p className="mt-0.5 text-xs text-emerald-600">
            Checked in {formatDate(attendee.checked_in_at)} at {formatTime(attendee.checked_in_at)}
          </p>
        )}
      </div>

      {/* Status badge */}
      <span
        className={`hidden shrink-0 rounded-full px-2.5 py-1 text-xs font-semibold sm:inline-flex ${
          isCheckedIn
            ? "bg-emerald-100 text-emerald-700"
            : "bg-blue-100 text-blue-700"
        }`}
      >
        {isCheckedIn ? "Checked In" : "Going"}
      </span>

      {/* Actions */}
      <div className="flex shrink-0 items-center gap-2">
        {isCheckedIn ? (
          <button
            type="button"
            onClick={() => onUndoCheckIn(attendee.user_id)}
            disabled={busy}
            title="Undo check-in"
            className="inline-flex items-center gap-1.5 rounded-lg border border-amber-300 bg-amber-50 px-3 py-1.5 text-xs font-medium text-amber-700 transition hover:bg-amber-100 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <XMarkIcon className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">Undo</span>
          </button>
        ) : (
          <button
            type="button"
            onClick={() => onCheckIn(attendee.user_id)}
            disabled={busy}
            title="Check in"
            className="inline-flex items-center gap-1.5 rounded-lg border border-emerald-300 bg-emerald-50 px-3 py-1.5 text-xs font-medium text-emerald-700 transition hover:bg-emerald-100 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <CheckIcon className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">Check In</span>
          </button>
        )}

        <button
          type="button"
          onClick={() => onRemove(attendee.user_id, fullName)}
          disabled={busy}
          title="Remove attendee"
          className="inline-flex items-center gap-1.5 rounded-lg border border-red-200 bg-red-50 px-3 py-1.5 text-xs font-medium text-red-600 transition hover:bg-red-100 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <XMarkIcon className="h-3.5 w-3.5" />
          <span className="hidden sm:inline">Remove</span>
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Skeleton
// ---------------------------------------------------------------------------

function SkeletonRow() {
  return (
    <div className="flex items-center gap-3 rounded-xl border border-gray-200 bg-white px-4 py-3 animate-pulse">
      <div className="h-10 w-10 shrink-0 rounded-full bg-gray-200" />
      <div className="flex-1 space-y-2">
        <div className="h-3.5 w-40 rounded bg-gray-200" />
        <div className="h-3 w-32 rounded bg-gray-200" />
      </div>
      <div className="h-6 w-16 rounded-full bg-gray-200" />
      <div className="flex gap-2">
        <div className="h-7 w-20 rounded-lg bg-gray-200" />
        <div className="h-7 w-20 rounded-lg bg-gray-200" />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Toast
// ---------------------------------------------------------------------------

interface Toast {
  id: number;
  message: string;
  type: "success" | "error";
}

let toastCounter = 0;

function ToastList({ toasts }: { toasts: Toast[] }) {
  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
      {toasts.map((t) => (
        <div
          key={t.id}
          className={`rounded-lg px-4 py-3 text-sm font-medium shadow-lg transition ${
            t.type === "success"
              ? "bg-emerald-600 text-white"
              : "bg-red-600 text-white"
          }`}
        >
          {t.message}
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

type StatusFilter = "all" | "going" | "checked_in";

export default function AttendeesPage() {
  const params = useParams<{ eventId: string }>();
  const eventId = params?.eventId ?? "";

  const { user, loading: authLoading } = useRequireAuth();

  const [data, setData] = useState<EventAttendeesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyUsers, setBusyUsers] = useState<Set<number>>(new Set());
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [toasts, setToasts] = useState<Toast[]>([]);

  const showToast = useCallback((message: string, type: Toast["type"]) => {
    const id = ++toastCounter;
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 3500);
  }, []);

  const fetchAttendees = useCallback(async () => {
    if (!eventId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch<EventAttendeesResponse>(`/events/${eventId}/attendees`);
      setData(res);
    } catch (err) {
      setError(getApiErrorMessage(err, "Could not load attendees."));
    } finally {
      setLoading(false);
    }
  }, [eventId]);

  useEffect(() => {
    if (!user) return;
    void fetchAttendees();
  }, [user, fetchAttendees]);

  const filteredAttendees = useMemo(() => {
    if (!data) return [];
    let list = data.attendees;
    if (statusFilter !== "all") list = list.filter((a) => a.status === statusFilter);
    if (search.trim()) {
      const q = search.trim().toLowerCase();
      list = list.filter(
        (a) =>
          a.first_name.toLowerCase().includes(q) ||
          a.last_name.toLowerCase().includes(q) ||
          a.email.toLowerCase().includes(q),
      );
    }
    return list;
  }, [data, search, statusFilter]);

  function setBusy(userId: number, busy: boolean) {
    setBusyUsers((prev) => {
      const next = new Set(prev);
      busy ? next.add(userId) : next.delete(userId);
      return next;
    });
  }

  async function handleCheckIn(userId: number) {
    setBusy(userId, true);
    try {
      const res = await apiFetch<CheckInResponse>(
        `/events/${eventId}/attendees/${userId}/check-in`,
        { method: "POST" },
      );
      setData((prev) =>
        prev
          ? {
              ...prev,
              checked_in_count: prev.checked_in_count + 1,
              going_count: prev.going_count - 1,
              attendees: prev.attendees.map((a) =>
                a.user_id === userId
                  ? { ...a, status: "checked_in", checked_in_at: res.checked_in_at }
                  : a,
              ),
            }
          : prev,
      );
      showToast("Attendee checked in.", "success");
    } catch (err) {
      showToast(getApiErrorMessage(err, "Could not check in attendee."), "error");
    } finally {
      setBusy(userId, false);
    }
  }

  async function handleUndoCheckIn(userId: number) {
    setBusy(userId, true);
    try {
      await apiFetch<UndoCheckInResponse>(
        `/events/${eventId}/attendees/${userId}/check-in`,
        { method: "DELETE" },
      );
      setData((prev) =>
        prev
          ? {
              ...prev,
              checked_in_count: prev.checked_in_count - 1,
              going_count: prev.going_count + 1,
              attendees: prev.attendees.map((a) =>
                a.user_id === userId
                  ? { ...a, status: "going", checked_in_at: null }
                  : a,
              ),
            }
          : prev,
      );
      showToast("Check-in undone.", "success");
    } catch (err) {
      showToast(getApiErrorMessage(err, "Could not undo check-in."), "error");
    } finally {
      setBusy(userId, false);
    }
  }

  async function handleRemove(userId: number, name: string) {
    const confirmed = window.confirm(
      `Remove ${name} from this event? They will be able to re-register if spots are available.`,
    );
    if (!confirmed) return;

    setBusy(userId, true);
    try {
      await apiFetch<RemoveAttendeeResponse>(
        `/events/${eventId}/attendees/${userId}`,
        { method: "DELETE" },
      );
      setData((prev) => {
        if (!prev) return prev;
        const removed = prev.attendees.find((a) => a.user_id === userId);
        return {
          ...prev,
          going_count:
            removed?.status === "going" ? prev.going_count - 1 : prev.going_count,
          checked_in_count:
            removed?.status === "checked_in"
              ? prev.checked_in_count - 1
              : prev.checked_in_count,
          attendees: prev.attendees.filter((a) => a.user_id !== userId),
        };
      });
      showToast(`${name} removed from the event.`, "success");
    } catch (err) {
      showToast(getApiErrorMessage(err, "Could not remove attendee."), "error");
    } finally {
      setBusy(userId, false);
    }
  }

  const isLoading = authLoading || loading;
  const totalRegistered = data ? data.going_count + data.checked_in_count : 0;
  const spotsRemaining = data ? Math.max(0, data.total_capacity - totalRegistered) : 0;

  return (
    <div className="min-h-screen bg-gray-50 font-sans antialiased">
      <Navbar />

      <main className="mx-auto max-w-5xl px-4 py-8 sm:px-6 lg:px-8">
        {/* Breadcrumb */}
        <nav className="mb-4 flex items-center gap-1.5 text-sm text-gray-500">
          <Link href="/" className="hover:text-black">Home</Link>
          <span>/</span>
          <Link href="/my-events" className="hover:text-black">My Events</Link>
          <span>/</span>
          {data ? (
            <Link href={`/events/${eventId}`} className="hover:text-black">
              {data.event_title}
            </Link>
          ) : (
            <span className="text-gray-400">Event</span>
          )}
          <span>/</span>
          <span className="text-gray-900 font-medium">Attendees</span>
        </nav>

        {/* Header */}
        <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 sm:text-3xl">
              {data ? `${data.event_title} — Attendees` : "Attendee Management"}
            </h1>
            <p className="mt-1 text-sm text-gray-500">
              Manage RSVPs and check in guests for your event.
            </p>
          </div>
          {data && data.attendees.length > 0 && (
            <button
              type="button"
              onClick={() => downloadCsv(data.attendees, data.event_title)}
              className="inline-flex items-center gap-2 rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 shadow-sm transition hover:bg-gray-50"
            >
              <DownloadIcon className="h-4 w-4" />
              Export CSV
            </button>
          )}
        </div>

        {/* Error */}
        {error && (
          <div className="mb-6 rounded-xl border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-700">
            {error}
          </div>
        )}

        {/* Stats */}
        {isLoading ? (
          <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4 animate-pulse">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="h-20 rounded-xl bg-gray-200" />
            ))}
          </div>
        ) : data ? (
          <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <StatCard label="Total RSVPs" value={totalRegistered} sub={`of ${data.total_capacity} capacity`} color="zinc" />
            <StatCard label="Checked In" value={data.checked_in_count} sub="arrived" color="green" />
            <StatCard label="Going" value={data.going_count} sub="not yet arrived" color="blue" />
            <StatCard label="Spots Left" value={spotsRemaining} sub="available" color="orange" />
          </div>
        ) : null}

        {/* Filters */}
        <div className="mb-4 flex flex-wrap items-center gap-3">
          <div className="relative flex-1 min-w-[200px]">
            <SearchIcon className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              placeholder="Search by name or email…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full rounded-lg border border-gray-300 bg-white py-2 pl-9 pr-4 text-sm text-gray-900 placeholder:text-gray-400 focus:border-black focus:outline-none focus:ring-1 focus:ring-black"
            />
          </div>
          <div className="flex gap-1 rounded-lg border border-gray-200 bg-white p-1">
            {(
              [
                { key: "all" as StatusFilter, label: "All" },
                { key: "going" as StatusFilter, label: "Going" },
                { key: "checked_in" as StatusFilter, label: "Checked In" },
              ] as const
            ).map(({ key, label }) => (
              <button
                key={key}
                type="button"
                onClick={() => setStatusFilter(key)}
                className={`rounded-md px-3 py-1.5 text-sm font-medium transition ${
                  statusFilter === key
                    ? "bg-black text-white shadow-sm"
                    : "text-gray-500 hover:text-black"
                }`}
              >
                {label}
                {data && (
                  <span className={`ml-1.5 text-xs ${statusFilter === key ? "opacity-75" : "text-gray-400"}`}>
                    {key === "all"
                      ? totalRegistered
                      : key === "going"
                      ? data.going_count
                      : data.checked_in_count}
                  </span>
                )}
              </button>
            ))}
          </div>
        </div>

        {/* List */}
        {isLoading ? (
          <div className="space-y-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <SkeletonRow key={i} />
            ))}
          </div>
        ) : filteredAttendees.length === 0 ? (
          <div className="rounded-xl border border-dashed border-gray-300 py-16 text-center">
            <UsersIcon className="mx-auto h-10 w-10 text-gray-300" />
            <p className="mt-3 text-sm font-medium text-gray-900">
              {data && totalRegistered === 0
                ? "No attendees yet"
                : "No attendees match your filters"}
            </p>
            <p className="mt-1 text-sm text-gray-500">
              {data && totalRegistered === 0
                ? "Attendees will appear here once people register."
                : "Try adjusting your search or filter."}
            </p>
            {search || statusFilter !== "all" ? (
              <button
                type="button"
                onClick={() => { setSearch(""); setStatusFilter("all"); }}
                className="mt-4 text-sm font-medium text-black underline"
              >
                Clear filters
              </button>
            ) : null}
          </div>
        ) : (
          <div className="space-y-2">
            {filteredAttendees.map((attendee) => (
              <AttendeeRow
                key={attendee.user_id}
                attendee={attendee}
                onCheckIn={handleCheckIn}
                onUndoCheckIn={handleUndoCheckIn}
                onRemove={handleRemove}
                busy={busyUsers.has(attendee.user_id)}
              />
            ))}
          </div>
        )}

        {/* Results count */}
        {!isLoading && data && filteredAttendees.length > 0 && (
          <p className="mt-4 text-center text-xs text-gray-400">
            Showing {filteredAttendees.length} of {totalRegistered} attendee
            {totalRegistered !== 1 ? "s" : ""}
          </p>
        )}
      </main>

      <ToastList toasts={toasts} />
    </div>
  );
}
