"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import Navbar from "@/app/components/navbar";
import { apiFetch } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";
import { buildEventUrl } from "@/lib/calendar-links";

interface CalendarItem {
  event_id: number;
  event_title: string;
  event_image_url: string | null;
  start_time: string;
  end_time: string | null;
  added_at: string;
  google_synced: boolean;
  google_calendar_event_url: string | null;
}

interface CalendarResponse {
  items: CalendarItem[];
  google_sync_enabled: boolean;
}

interface GoogleCalendarSyncResponse {
  google_sync_enabled: boolean;
  synced_count: number;
  skipped_count: number;
  status: "enabled";
}

interface CalendarViewOption {
  label: string;
  enabled: boolean;
}

const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const CALENDAR_VIEW_OPTIONS: CalendarViewOption[] = [
  { label: "Month", enabled: true },
  { label: "Week", enabled: false },
  { label: "Day", enabled: false },
];

function PlusIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 5.25v13.5M5.25 12h13.5" />
    </svg>
  );
}

function CalendarIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 3.75v2.5m7.5-2.5v2.5M4.5 8.25h15m-15 .75v9A2.25 2.25 0 006.75 20.25h10.5A2.25 2.25 0 0019.5 18V9a2.25 2.25 0 00-2.25-2.25H6.75A2.25 2.25 0 004.5 9Z" />
    </svg>
  );
}

function RefreshIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992V4.356m-1.857 13.299A9 9 0 118.18 5.334L3 10.5" />
    </svg>
  );
}

function ChevronLeftIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="m15.75 19.5-7.5-7.5 7.5-7.5" />
    </svg>
  );
}

function ChevronRightIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="m8.25 4.5 7.5 7.5-7.5 7.5" />
    </svg>
  );
}

function formatMonthLabel(date: Date): string {
  return date.toLocaleDateString("en-US", { month: "long", year: "numeric" });
}

function formatEventTime(dateString: string): string {
  return new Date(dateString).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function dateKey(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function syncLabel(item: CalendarItem): string {
  return item.google_synced ? "Google Synced" : "Evently Only";
}

function syncClasses(item: CalendarItem): string {
  return item.google_synced
    ? "bg-emerald-100 text-emerald-800"
    : "bg-zinc-100 text-zinc-700";
}

function startOfMonth(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), 1);
}

function addDays(date: Date, amount: number): Date {
  const next = new Date(date);
  next.setDate(next.getDate() + amount);
  return next;
}

function addMonths(date: Date, amount: number): Date {
  return new Date(date.getFullYear(), date.getMonth() + amount, 1);
}

function escapeIcsText(value: string): string {
  return value
    .replace(/\\/g, "\\\\")
    .replace(/\n/g, "\\n")
    .replace(/,/g, "\\,")
    .replace(/;/g, "\\;");
}

function toIcsDate(dateString: string): string {
  return new Date(dateString).toISOString().replace(/[-:]|\.\d{3}/g, "");
}

function getErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error) {
    return error.message;
  }
  return fallback;
}

export default function CalendarPage() {
  const { user, loading: authLoading, error: authError } = useRequireAuth();
  const [isHydrated, setIsHydrated] = useState(false);
  const [displayMonth, setDisplayMonth] = useState<Date | null>(null);
  const [calendarLoadedAt, setCalendarLoadedAt] = useState<number | null>(null);
  const [items, setItems] = useState<CalendarItem[]>([]);
  const [googleSyncEnabled, setGoogleSyncEnabled] = useState(false);
  const [calendarLoading, setCalendarLoading] = useState(true);
  const [calendarError, setCalendarError] = useState<string | null>(null);
  const [syncLoading, setSyncLoading] = useState(false);
  const [syncMessage, setSyncMessage] = useState<string | null>(null);
  const [syncError, setSyncError] = useState<string | null>(null);

  useEffect(() => {
    setIsHydrated(true);
    setDisplayMonth(startOfMonth(new Date()));
    setCalendarLoadedAt(Date.now());
  }, []);

  useEffect(() => {
    if (!user) {
      setItems([]);
      setGoogleSyncEnabled(false);
      setCalendarLoading(false);
      return;
    }

    let cancelled = false;
    setCalendarLoading(true);

    void apiFetch<CalendarResponse>(`/users/${user.id}/calendar`)
      .then((response) => {
        if (!cancelled) {
          setItems(response.items);
          setGoogleSyncEnabled(response.google_sync_enabled);
          setCalendarError(null);
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setItems([]);
          setCalendarError(
            getErrorMessage(error, "Could not load your saved calendar."),
          );
        }
      })
      .finally(() => {
        if (!cancelled) {
          setCalendarLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [user]);

  const normalizedItems = useMemo(
    () =>
      [...items]
        .filter((item) => !Number.isNaN(new Date(item.start_time).getTime()))
        .sort(
          (left, right) =>
            new Date(left.start_time).getTime() - new Date(right.start_time).getTime(),
        ),
    [items],
  );

  const itemsByDate = useMemo(() => {
    const groups = new Map<string, CalendarItem[]>();

    for (const item of normalizedItems) {
      const key = dateKey(new Date(item.start_time));
      const existing = groups.get(key) ?? [];
      existing.push(item);
      groups.set(key, existing);
    }

    return groups;
  }, [normalizedItems]);

  const gridDays = useMemo(() => {
    if (displayMonth === null) {
      return [];
    }
    const monthStart = startOfMonth(displayMonth);
    const gridStart = addDays(monthStart, -monthStart.getDay());
    return Array.from({ length: 42 }, (_, index) => addDays(gridStart, index));
  }, [displayMonth]);

  const upcomingEvents = useMemo(() => {
    if (calendarLoadedAt === null) {
      return [];
    }
    return normalizedItems
      .filter((item) => new Date(item.start_time).getTime() >= calendarLoadedAt)
      .slice(0, 5);
  }, [calendarLoadedAt, normalizedItems]);

  const pastEvents = useMemo(() => {
    if (calendarLoadedAt === null) {
      return [];
    }
    return [...normalizedItems]
      .filter((item) => new Date(item.start_time).getTime() < calendarLoadedAt)
      .sort(
        (left, right) =>
          new Date(right.start_time).getTime() - new Date(left.start_time).getTime(),
      )
      .slice(0, 6);
  }, [calendarLoadedAt, normalizedItems]);

  const selectedMonthItems = useMemo(
    () => {
      if (displayMonth === null) {
        return [];
      }

      return normalizedItems.filter((item) => {
        const date = new Date(item.start_time);
        return (
          date.getFullYear() === displayMonth.getFullYear() &&
          date.getMonth() === displayMonth.getMonth()
        );
      });
    },
    [displayMonth, normalizedItems],
  );

  const todayKey = useMemo(() => {
    if (calendarLoadedAt === null) {
      return null;
    }
    return dateKey(new Date(calendarLoadedAt));
  }, [calendarLoadedAt]);

  async function reloadCalendar() {
    if (!user) {
      return;
    }

    const response = await apiFetch<CalendarResponse>(`/users/${user.id}/calendar`);
    setItems(response.items);
    setGoogleSyncEnabled(response.google_sync_enabled);
    setCalendarError(null);
  }

  async function handleSyncToGoogleCalendar() {
    if (!user) {
      return;
    }

    setSyncLoading(true);
    setSyncMessage(null);
    setSyncError(null);

    try {
      const response = await apiFetch<GoogleCalendarSyncResponse>(
        `/users/${user.id}/calendar/sync/google`,
        {
          method: "POST",
        },
      );
      await reloadCalendar();
      setGoogleSyncEnabled(response.google_sync_enabled);
      setSyncMessage(
        response.synced_count > 0
          ? `Synced ${response.synced_count} saved event${response.synced_count === 1 ? "" : "s"} to Google Calendar.`
          : "Google Calendar sync is enabled for your saved events.",
      );
    } catch (error: unknown) {
      setSyncError(
        getErrorMessage(error, "Could not sync your calendar to Google."),
      );
    } finally {
      setSyncLoading(false);
    }
  }

  function handleCalendarExport() {
    if (normalizedItems.length === 0) {
      return;
    }

    const lines = [
      "BEGIN:VCALENDAR",
      "VERSION:2.0",
      "PRODID:-//Evently//Saved Calendar//EN",
      "CALSCALE:GREGORIAN",
      "METHOD:PUBLISH",
      ...normalizedItems.map((item) => {
        const end =
          item.end_time && !Number.isNaN(new Date(item.end_time).getTime())
            ? item.end_time
            : new Date(new Date(item.start_time).getTime() + 2 * 60 * 60 * 1000).toISOString();

        return [
          "BEGIN:VEVENT",
          `UID:evently-${item.event_id}@evently.local`,
          `DTSTAMP:${toIcsDate(new Date().toISOString())}`,
          `DTSTART:${toIcsDate(item.start_time)}`,
          `DTEND:${toIcsDate(end)}`,
          `SUMMARY:${escapeIcsText(item.event_title)}`,
          `DESCRIPTION:${escapeIcsText("Saved from Evently My Calendar")}`,
          `URL:${buildEventUrl(window.location.origin, item.event_id)}`,
          "END:VEVENT",
        ].join("\r\n");
      }),
      "END:VCALENDAR",
    ];

    const file = new Blob([lines.join("\r\n")], {
      type: "text/calendar;charset=utf-8",
    });
    const url = URL.createObjectURL(file);
    const link = document.createElement("a");
    link.href = url;
    link.download = "evently-my-calendar.ics";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }

  return (
    <div className="min-h-screen bg-[#f6f4ee] text-black">
      <Navbar />

      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        {!isHydrated || displayMonth === null || calendarLoadedAt === null || authLoading ? (
          <div className="rounded-3xl border border-gray-200 bg-white p-8 text-sm text-gray-600 shadow-sm">
            Loading your calendar...
          </div>
        ) : authError ? (
          <div className="rounded-3xl border border-red-200 bg-red-50 p-8 text-sm text-red-700 shadow-sm">
            {authError}
          </div>
        ) : (
          <>
            <section className="mb-8 flex flex-col gap-4 rounded-3xl border border-gray-200 bg-white px-6 py-6 shadow-sm sm:flex-row sm:items-end sm:justify-between">
              <div>
                <p className="text-sm font-medium uppercase tracking-[0.2em] text-gray-500">
                  Saved Calendar
                </p>
                <h1 className="mt-2 text-3xl font-semibold tracking-tight">
                  {user?.first_name ? `${user.first_name}'s Calendar` : "My Calendar"}
                </h1>
                <p className="mt-2 max-w-2xl text-sm text-gray-600">
                  Save events here first, then sync your Evently calendar to Google Calendar whenever you are ready.
                </p>
              </div>
              <div className="grid gap-3 sm:grid-cols-3">
                <Link
                  href="/create"
                  className="inline-flex items-center justify-center gap-2 rounded-xl bg-black px-4 py-3 text-sm font-medium text-white transition hover:bg-gray-800"
                >
                  <PlusIcon className="h-4 w-4" />
                  Create New Event
                </Link>
                <button
                  type="button"
                  onClick={handleSyncToGoogleCalendar}
                  disabled={syncLoading}
                  className="inline-flex items-center justify-center gap-2 rounded-xl border border-gray-300 bg-white px-4 py-3 text-sm font-medium text-gray-800 transition hover:border-black hover:text-black disabled:cursor-not-allowed disabled:opacity-60"
                >
                  <RefreshIcon className="h-4 w-4" />
                  {syncLoading
                    ? "Syncing..."
                    : googleSyncEnabled
                      ? "Resync Google Calendar"
                      : "Sync to Google Calendar"}
                </button>
                <button
                  type="button"
                  onClick={handleCalendarExport}
                  disabled={normalizedItems.length === 0}
                  className="inline-flex items-center justify-center gap-2 rounded-xl bg-black px-4 py-3 text-sm font-medium text-white transition hover:bg-gray-800 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <CalendarIcon className="h-4 w-4" />
                  Export Calendar (.ics)
                </button>
              </div>
            </section>

            {syncError ? (
              <div className="mb-6 rounded-3xl border border-red-200 bg-red-50 px-6 py-4 text-sm text-red-700 shadow-sm">
                {syncError}
              </div>
            ) : null}

            {syncMessage ? (
              <div className="mb-6 rounded-3xl border border-emerald-200 bg-emerald-50 px-6 py-4 text-sm text-emerald-700 shadow-sm">
                {syncMessage}
              </div>
            ) : null}

            <section className="grid gap-6 lg:grid-cols-[280px_minmax(0,1fr)]">
              <aside className="space-y-6">
                <div className="rounded-3xl border border-gray-200 bg-white p-5 shadow-sm">
                  <h2 className="text-base font-semibold">Quick Actions</h2>
                  <div className="mt-4 space-y-3">
                    <Link
                      href="/create"
                      className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-black px-4 py-3 text-sm font-medium text-white transition hover:bg-gray-800"
                    >
                      <PlusIcon className="h-4 w-4" />
                      Create New Event
                    </Link>
                    <button
                      type="button"
                      onClick={handleSyncToGoogleCalendar}
                      disabled={syncLoading}
                      className="inline-flex w-full items-center justify-center gap-2 rounded-xl border border-gray-300 px-4 py-3 text-sm font-medium text-gray-700 transition hover:border-black hover:text-black disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      <RefreshIcon className="h-4 w-4" />
                      {syncLoading ? "Syncing..." : "Sync to Google Calendar"}
                    </button>
                  </div>
                </div>

                <div className="rounded-3xl border border-gray-200 bg-white p-5 shadow-sm">
                  <h2 className="text-base font-semibold">My Calendars</h2>
                  <ul className="mt-4 space-y-3 text-sm text-gray-700">
                    <li className="flex items-center gap-3">
                      <span className="h-3 w-3 rounded-full bg-black" />
                      <span>Evently Saved Events</span>
                    </li>
                    <li className="flex items-center gap-3">
                      <span
                        className={`h-3 w-3 rounded-full ${
                          googleSyncEnabled ? "bg-emerald-500" : "bg-gray-300"
                        }`}
                      />
                      <span>
                        Google Calendar {googleSyncEnabled ? "Connected" : "Not Connected"}
                      </span>
                    </li>
                  </ul>
                </div>

                <div className="rounded-3xl border border-gray-200 bg-white p-5 shadow-sm">
                  <h2 className="text-base font-semibold">Upcoming Saved Events</h2>
                  {calendarLoading ? (
                    <p className="mt-4 text-sm text-gray-500">Loading saved events...</p>
                  ) : upcomingEvents.length > 0 ? (
                    <div className="mt-4 space-y-4">
                      {upcomingEvents.map((item) => (
                        <div key={`${item.event_id}-${item.start_time}`} className="border-l-2 border-gray-900 pl-3">
                          <Link
                            href={`/events/${item.event_id}`}
                            className="text-sm font-semibold text-gray-900 transition hover:text-gray-600"
                          >
                            {item.event_title}
                          </Link>
                          <p className="mt-1 text-xs uppercase tracking-[0.18em] text-gray-500">
                            {syncLabel(item)}
                          </p>
                          <p className="mt-1 text-xs text-gray-500">
                            {formatEventTime(item.start_time)}
                          </p>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="mt-4 text-sm text-gray-500">
                      Save events from their detail pages to build your personal calendar.
                    </p>
                  )}
                </div>
              </aside>

              <section className="rounded-3xl border border-gray-200 bg-white shadow-sm">
                <div className="flex flex-col gap-4 border-b border-gray-200 px-5 py-5 sm:flex-row sm:items-center sm:justify-between sm:px-6">
                  <div className="flex flex-wrap items-center gap-4">
                    <div className="flex items-center gap-3">
                      <h2 className="text-3xl font-semibold tracking-tight">Calendar</h2>
                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          onClick={() =>
                            setDisplayMonth((current) =>
                              addMonths(current ?? startOfMonth(new Date()), -1),
                            )
                          }
                          className="rounded-full border border-gray-200 p-2 text-gray-600 transition hover:border-black hover:text-black"
                          aria-label="Previous month"
                        >
                          <ChevronLeftIcon className="h-4 w-4" />
                        </button>
                        <span className="min-w-40 text-lg font-medium">{formatMonthLabel(displayMonth)}</span>
                        <button
                          type="button"
                          onClick={() =>
                            setDisplayMonth((current) =>
                              addMonths(current ?? startOfMonth(new Date()), 1),
                            )
                          }
                          className="rounded-full border border-gray-200 p-2 text-gray-600 transition hover:border-black hover:text-black"
                          aria-label="Next month"
                        >
                          <ChevronRightIcon className="h-4 w-4" />
                        </button>
                      </div>
                    </div>
                  </div>

                  <div className="flex flex-wrap items-center gap-2">
                    {CALENDAR_VIEW_OPTIONS.map((view) => (
                      <button
                        key={view.label}
                        type="button"
                        disabled={!view.enabled}
                        className={`rounded-xl px-4 py-2 text-sm font-medium transition ${
                          view.enabled
                            ? "bg-black text-white"
                            : "border border-gray-200 text-gray-400 disabled:cursor-not-allowed disabled:opacity-70"
                        }`}
                        title={view.enabled ? undefined : `${view.label} view is coming soon.`}
                      >
                        {view.label}
                      </button>
                    ))}
                    <button
                      type="button"
                      onClick={() => setDisplayMonth(startOfMonth(new Date()))}
                      className="rounded-xl border border-gray-200 px-4 py-2 text-sm font-medium text-gray-600 transition hover:border-black hover:text-black"
                    >
                      Today
                    </button>
                  </div>
                </div>

                {calendarError ? (
                  <div className="px-6 py-6 text-sm text-red-700">{calendarError}</div>
                ) : (
                  <div className="px-4 pb-4 pt-5 sm:px-6 sm:pb-6">
                    <div className="grid grid-cols-7 overflow-hidden rounded-2xl border border-gray-200">
                      {DAYS.map((day) => (
                        <div
                          key={day}
                          className="border-b border-r border-gray-200 bg-gray-50 px-3 py-3 text-center text-xs font-semibold uppercase tracking-[0.16em] text-gray-500 last:border-r-0"
                        >
                          {day}
                        </div>
                      ))}
                        {gridDays.map((day, index) => {
                          const dayItems = itemsByDate.get(dateKey(day)) ?? [];
                          const isCurrentMonth = day.getMonth() === displayMonth.getMonth();
                          const isToday = todayKey !== null && dateKey(day) === todayKey;

                        return (
                          <div
                            key={`${day.toISOString()}-${index}`}
                            className={`min-h-32 border-b border-r border-gray-200 px-3 py-3 text-left align-top transition hover:bg-gray-50 ${index % 7 === 6 ? "border-r-0" : ""}`}
                          >
                            <div className="flex items-center justify-between">
                              <span
                                className={`inline-flex h-8 w-8 items-center justify-center rounded-full text-sm font-medium ${
                                  isToday
                                    ? "bg-black text-white"
                                    : isCurrentMonth
                                      ? "text-gray-900"
                                      : "text-gray-300"
                                }`}
                              >
                                {day.getDate()}
                              </span>
                              {dayItems.length > 0 ? (
                                <span className="text-xs text-gray-400">
                                  {dayItems.length} item{dayItems.length > 1 ? "s" : ""}
                                </span>
                              ) : null}
                            </div>

                            <div className="mt-3 space-y-2">
                              {dayItems.slice(0, 2).map((item) => (
                                <Link
                                  key={`${item.event_id}-${item.start_time}`}
                                  href={`/events/${item.event_id}`}
                                  className={`block truncate rounded-lg px-2.5 py-1.5 text-xs font-medium ${syncClasses(item)}`}
                                >
                                  {item.event_title}
                                </Link>
                              ))}
                              {dayItems.length > 2 ? (
                                <div className="text-xs font-medium text-gray-500">
                                  +{dayItems.length - 2} more
                                </div>
                              ) : null}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </section>
            </section>

            <section className="mt-8 grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
              <div className="space-y-6">
                <div className="rounded-3xl border border-gray-200 bg-white p-6 shadow-sm">
                  <h2 className="text-lg font-semibold">This Month</h2>
                  {selectedMonthItems.length > 0 ? (
                    <div className="mt-5 grid gap-4 sm:grid-cols-2">
                      {selectedMonthItems.slice(0, 6).map((item) => (
                        <Link
                          key={`${item.event_id}-${item.start_time}-summary`}
                          href={`/events/${item.event_id}`}
                          className="rounded-2xl border border-gray-200 bg-[#faf8f3] p-4"
                        >
                          <div className="flex items-center justify-between gap-3">
                            <p className="text-sm font-semibold text-gray-900">
                              {item.event_title}
                            </p>
                            <span
                              className={`rounded-full px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] ${syncClasses(item)}`}
                            >
                              {syncLabel(item)}
                            </span>
                          </div>
                          <p className="mt-3 text-sm text-gray-500">
                            {formatEventTime(item.start_time)}
                          </p>
                        </Link>
                      ))}
                    </div>
                  ) : (
                    <p className="mt-4 text-sm text-gray-500">
                      No saved events are scheduled for this month yet.
                    </p>
                  )}
                </div>

                <div className="rounded-3xl border border-gray-200 bg-white p-6 shadow-sm">
                  <h2 className="text-lg font-semibold">Past Saved Events</h2>
                  {pastEvents.length > 0 ? (
                    <div className="mt-5 grid gap-4 sm:grid-cols-2">
                      {pastEvents.map((item) => (
                        <Link
                          key={`${item.event_id}-${item.start_time}-past`}
                          href={`/events/${item.event_id}`}
                          className="rounded-2xl border border-gray-200 bg-white p-4 transition hover:border-gray-300 hover:bg-gray-50"
                        >
                          <div className="flex items-center justify-between gap-3">
                            <p className="text-sm font-semibold text-gray-900">
                              {item.event_title}
                            </p>
                            <span
                              className={`rounded-full px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] ${syncClasses(item)}`}
                            >
                              {syncLabel(item)}
                            </span>
                          </div>
                          <p className="mt-3 text-sm text-gray-500">
                            {formatEventTime(item.start_time)}
                          </p>
                        </Link>
                      ))}
                    </div>
                  ) : (
                    <p className="mt-4 text-sm text-gray-500">
                      Your past saved events will appear here after they happen.
                    </p>
                  )}
                </div>
              </div>

              <footer className="rounded-3xl border border-gray-200 bg-white p-6 shadow-sm">
                <div className="flex items-center gap-3">
                  <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-black text-sm font-semibold text-white">
                    E
                  </span>
                  <div>
                    <p className="font-semibold">Evently</p>
                    <p className="text-sm text-gray-500">
                      Your saved events stay in Evently first, with Google sync available whenever you turn it on.
                    </p>
                  </div>
                </div>
              </footer>
            </section>
          </>
        )}
      </main>
    </div>
  );
}
