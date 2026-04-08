"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import Navbar from "@/app/components/navbar";
import { apiFetch } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";
import { buildEventUrl } from "@/lib/calendar-links";

type CalendarView = "Month" | "Week" | "Day";
type ActivityAction = "attended" | "created" | "registered";

interface ActivityItem {
  event_id: number;
  event_title: string;
  event_image_url: string | null;
  action: ActivityAction;
  date: string;
}

interface ActivityResponse {
  items: ActivityItem[];
}

interface CalendarSource {
  label: string;
  color: string;
  action: ActivityAction;
}

const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const CALENDAR_SOURCES: CalendarSource[] = [
  { label: "Created Events", color: "bg-black", action: "created" },
  { label: "Registered Events", color: "bg-blue-600", action: "registered" },
  { label: "Attended Events", color: "bg-gray-400", action: "attended" },
];

function PlusIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 5.25v13.5M5.25 12h13.5" />
    </svg>
  );
}

function UploadIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 16.5V7.5m0 0L8.25 11.25M12 7.5l3.75 3.75M4.5 16.5v.75A2.25 2.25 0 006.75 19.5h10.5a2.25 2.25 0 002.25-2.25v-.75" />
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

function CalendarIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 3.75v2.5m7.5-2.5v2.5M4.5 8.25h15m-15 .75v9A2.25 2.25 0 006.75 20.25h10.5A2.25 2.25 0 0019.5 18V9a2.25 2.25 0 00-2.25-2.25H6.75A2.25 2.25 0 004.5 9Z" />
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

function actionLabel(action: ActivityAction): string {
  if (action === "created") return "Hosting";
  if (action === "registered") return "Going";
  return "Attended";
}

function actionClasses(action: ActivityAction): string {
  if (action === "created") return "bg-black text-white";
  if (action === "registered") return "bg-blue-600 text-white";
  return "bg-gray-200 text-gray-700";
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

export default function CalendarPage() {
  const { user, loading: authLoading, error: authError } = useRequireAuth();
  const [activeView, setActiveView] = useState<CalendarView>("Month");
  const [displayMonth, setDisplayMonth] = useState(() => startOfMonth(new Date()));
  const [calendarLoadedAt] = useState(() => Date.now());
  const [activity, setActivity] = useState<ActivityItem[]>([]);
  const [activityLoading, setActivityLoading] = useState(true);
  const [activityError, setActivityError] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;

    let cancelled = false;

    void apiFetch<ActivityResponse>(`/users/${user.id}/activity?limit=24`)
      .then((response) => {
        if (!cancelled) {
          setActivity(response.items);
          setActivityError(null);
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setActivity([]);
          setActivityError(
            error instanceof Error
              ? error.message
              : "Could not load your calendar items.",
          );
        }
      })
      .finally(() => {
        if (!cancelled) {
          setActivityLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [user]);

  const normalizedActivity = useMemo(
    () =>
      [...activity]
        .filter((item) => !Number.isNaN(new Date(item.date).getTime()))
        .sort(
          (left, right) =>
            new Date(left.date).getTime() - new Date(right.date).getTime(),
        ),
    [activity],
  );

  const activityByDate = useMemo(() => {
    const groups = new Map<string, ActivityItem[]>();

    for (const item of normalizedActivity) {
      const key = dateKey(new Date(item.date));
      const existing = groups.get(key) ?? [];
      existing.push(item);
      groups.set(key, existing);
    }

    return groups;
  }, [normalizedActivity]);

  const gridDays = useMemo(() => {
    const monthStart = startOfMonth(displayMonth);
    const gridStart = addDays(monthStart, -monthStart.getDay());

    return Array.from({ length: 42 }, (_, index) => addDays(gridStart, index));
  }, [displayMonth]);

  const upcomingEvents = useMemo(() => {
    return normalizedActivity
      .filter((item) => new Date(item.date).getTime() >= calendarLoadedAt)
      .slice(0, 5);
  }, [calendarLoadedAt, normalizedActivity]);

  const pastEvents = useMemo(() => {
    return [...normalizedActivity]
      .filter((item) => new Date(item.date).getTime() < calendarLoadedAt)
      .sort(
        (left, right) =>
          new Date(right.date).getTime() - new Date(left.date).getTime(),
      )
      .slice(0, 6);
  }, [calendarLoadedAt, normalizedActivity]);

  const selectedMonthItems = useMemo(
    () =>
      normalizedActivity.filter((item) => {
        const date = new Date(item.date);
        return (
          date.getFullYear() === displayMonth.getFullYear() &&
          date.getMonth() === displayMonth.getMonth()
        );
      }),
    [displayMonth, normalizedActivity],
  );

  const exportableEvents = useMemo(() => {
    const seen = new Set<string>();

    return normalizedActivity.filter((item) => {
      if (new Date(item.date).getTime() < calendarLoadedAt) {
        return false;
      }

      const key = `${item.event_id}-${item.date}`;
      if (seen.has(key)) {
        return false;
      }

      seen.add(key);
      return true;
    });
  }, [calendarLoadedAt, normalizedActivity]);

  function handleGoogleCalendarExport() {
    if (exportableEvents.length === 0) {
      return;
    }

    const lines = [
      "BEGIN:VCALENDAR",
      "VERSION:2.0",
      "PRODID:-//Evently//Personal Planner//EN",
      "CALSCALE:GREGORIAN",
      "METHOD:PUBLISH",
      ...exportableEvents.flatMap((item) => {
        const start = new Date(item.date);
        const end = new Date(start.getTime() + 2 * 60 * 60 * 1000);

        return [
          "BEGIN:VEVENT",
          `UID:evently-${item.event_id}-${start.getTime()}@evently.local`,
          `DTSTAMP:${toIcsDate(new Date().toISOString())}`,
          `DTSTART:${toIcsDate(item.date)}`,
          `DTEND:${toIcsDate(end.toISOString())}`,
          `SUMMARY:${escapeIcsText(item.event_title)}`,
          `DESCRIPTION:${escapeIcsText(`Imported from Evently Personal Planner (${actionLabel(item.action)})`)}`,
          `URL:${buildEventUrl(window.location.origin, item.event_id)}`,
          "END:VEVENT",
        ];
      }),
      "END:VCALENDAR",
    ];

    const file = new Blob([lines.join("\r\n")], {
      type: "text/calendar;charset=utf-8",
    });
    const url = URL.createObjectURL(file);
    const link = document.createElement("a");
    link.href = url;
    link.download = "evently-personal-planner.ics";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);

    window.open("https://calendar.google.com/", "_blank", "noopener,noreferrer");
  }

  return (
    <div className="min-h-screen bg-[#f6f4ee] text-black">
      <Navbar />

      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        {authLoading ? (
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
                  Personal Planner
                </p>
                <h1 className="mt-2 text-3xl font-semibold tracking-tight">
                  {user?.first_name ? `${user.first_name}'s Calendar` : "My Calendar"}
                </h1>
                <p className="mt-2 max-w-2xl text-sm text-gray-600">
                  Track the events you are hosting, planning to attend, and recently joined in one place.
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
                  className="inline-flex items-center justify-center gap-2 rounded-xl border border-gray-300 px-4 py-3 text-sm font-medium text-gray-700 transition hover:border-black hover:text-black"
                >
                  <UploadIcon className="h-4 w-4" />
                  Import Events
                </button>
                <button
                  type="button"
                  onClick={handleGoogleCalendarExport}
                  disabled={exportableEvents.length === 0}
                  className="inline-flex items-center justify-center gap-2 rounded-xl bg-black px-4 py-3 text-sm font-medium text-white transition hover:bg-gray-800 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <CalendarIcon className="h-4 w-4" />
                  Add to Google Calendar
                </button>
              </div>
            </section>

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
                      className="inline-flex w-full items-center justify-center gap-2 rounded-xl border border-gray-300 px-4 py-3 text-sm font-medium text-gray-700 transition hover:border-black hover:text-black"
                    >
                      <UploadIcon className="h-4 w-4" />
                      Import Events
                    </button>
                  </div>
                </div>

                <div className="rounded-3xl border border-gray-200 bg-white p-5 shadow-sm">
                  <h2 className="text-base font-semibold">My Calendars</h2>
                  <ul className="mt-4 space-y-3">
                    {CALENDAR_SOURCES.map((source) => (
                      <li key={source.action} className="flex items-center gap-3 text-sm text-gray-700">
                        <span className={`h-3 w-3 rounded-full ${source.color}`} />
                        <span>{source.label}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                <div className="rounded-3xl border border-gray-200 bg-white p-5 shadow-sm">
                  <h2 className="text-base font-semibold">Upcoming Events</h2>
                  {activityLoading ? (
                    <p className="mt-4 text-sm text-gray-500">Loading upcoming events...</p>
                  ) : upcomingEvents.length > 0 ? (
                    <div className="mt-4 space-y-4">
                      {upcomingEvents.map((item) => (
                        <div key={`${item.event_id}-${item.action}-${item.date}`} className="border-l-2 border-gray-900 pl-3">
                          <Link
                            href={`/events/${item.event_id}`}
                            className="text-sm font-semibold text-gray-900 transition hover:text-gray-600"
                          >
                            {item.event_title}
                          </Link>
                          <p className="mt-1 text-xs uppercase tracking-[0.18em] text-gray-500">
                            {actionLabel(item.action)}
                          </p>
                          <p className="mt-1 text-xs text-gray-500">{formatEventTime(item.date)}</p>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="mt-4 text-sm text-gray-500">
                      Your upcoming plans will appear here once you create or join events.
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
                          onClick={() => setDisplayMonth((current) => addMonths(current, -1))}
                          className="rounded-full border border-gray-200 p-2 text-gray-600 transition hover:border-black hover:text-black"
                          aria-label="Previous month"
                        >
                          <ChevronLeftIcon className="h-4 w-4" />
                        </button>
                        <span className="min-w-40 text-lg font-medium">{formatMonthLabel(displayMonth)}</span>
                        <button
                          type="button"
                          onClick={() => setDisplayMonth((current) => addMonths(current, 1))}
                          className="rounded-full border border-gray-200 p-2 text-gray-600 transition hover:border-black hover:text-black"
                          aria-label="Next month"
                        >
                          <ChevronRightIcon className="h-4 w-4" />
                        </button>
                      </div>
                    </div>
                  </div>

                  <div className="flex flex-wrap items-center gap-2">
                    {(["Month", "Week", "Day"] as CalendarView[]).map((view) => (
                      <button
                        key={view}
                        type="button"
                        onClick={() => setActiveView(view)}
                        className={`rounded-xl px-4 py-2 text-sm font-medium transition ${
                          activeView === view
                            ? "bg-black text-white"
                            : "border border-gray-200 text-gray-600 hover:border-black hover:text-black"
                        }`}
                      >
                        {view}
                      </button>
                    ))}
                    <button
                      type="button"
                      onClick={() => {
                        setDisplayMonth(startOfMonth(new Date()));
                        setActiveView("Month");
                      }}
                      className="rounded-xl border border-gray-200 px-4 py-2 text-sm font-medium text-gray-600 transition hover:border-black hover:text-black"
                    >
                      Today
                    </button>
                  </div>
                </div>

                {activityError ? (
                  <div className="px-6 py-6 text-sm text-red-700">{activityError}</div>
                ) : activeView !== "Month" ? (
                  <div className="px-6 py-10">
                    <div className="rounded-2xl border border-dashed border-gray-300 bg-gray-50 p-8 text-center">
                      <CalendarIcon className="mx-auto h-10 w-10 text-gray-400" />
                      <p className="mt-4 text-lg font-medium text-gray-900">
                        {activeView} view is coming next
                      </p>
                      <p className="mt-2 text-sm text-gray-500">
                        Month view is ready now, with your event activity mapped onto the calendar.
                      </p>
                    </div>
                  </div>
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
                        const items = activityByDate.get(dateKey(day)) ?? [];
                        const isCurrentMonth = day.getMonth() === displayMonth.getMonth();
                        const isToday = dateKey(day) === dateKey(new Date());

                        return (
                          <div
                            key={`${day.toISOString()}-${index}`}
                            className={`min-h-32 border-r border-b border-gray-200 px-3 py-3 text-left align-top transition hover:bg-gray-50 ${index % 7 === 6 ? "border-r-0" : ""}`}
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
                              {items.length > 0 ? (
                                <span className="text-xs text-gray-400">{items.length} item{items.length > 1 ? "s" : ""}</span>
                              ) : null}
                            </div>

                            <div className="mt-3 space-y-2">
                              {items.slice(0, 2).map((item) => (
                                <Link
                                  key={`${item.event_id}-${item.action}-${item.date}`}
                                  href={`/events/${item.event_id}`}
                                  className={`truncate rounded-lg px-2.5 py-1.5 text-xs font-medium ${actionClasses(item.action)}`}
                                >
                                  {item.event_title}
                                </Link>
                              ))}
                              {items.length > 2 ? (
                                <div className="text-xs font-medium text-gray-500">
                                  +{items.length - 2} more
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
                          key={`${item.event_id}-${item.action}-${item.date}-summary`}
                          href={`/events/${item.event_id}`}
                          className="rounded-2xl border border-gray-200 bg-[#faf8f3] p-4"
                        >
                          <div className="flex items-center justify-between gap-3">
                            <p className="text-sm font-semibold text-gray-900">
                              {item.event_title}
                            </p>
                            <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] ${actionClasses(item.action)}`}>
                              {actionLabel(item.action)}
                            </span>
                          </div>
                          <p className="mt-3 text-sm text-gray-500">{formatEventTime(item.date)}</p>
                        </Link>
                      ))}
                    </div>
                  ) : (
                    <p className="mt-4 text-sm text-gray-500">
                      No events are scheduled for this month yet.
                    </p>
                  )}
                </div>

                <div className="rounded-3xl border border-gray-200 bg-white p-6 shadow-sm">
                  <h2 className="text-lg font-semibold">Past Events</h2>
                  {pastEvents.length > 0 ? (
                    <div className="mt-5 grid gap-4 sm:grid-cols-2">
                      {pastEvents.map((item) => (
                        <Link
                          key={`${item.event_id}-${item.action}-${item.date}-past`}
                          href={`/events/${item.event_id}`}
                          className="rounded-2xl border border-gray-200 bg-white p-4 transition hover:border-gray-300 hover:bg-gray-50"
                        >
                          <div className="flex items-center justify-between gap-3">
                            <p className="text-sm font-semibold text-gray-900">
                              {item.event_title}
                            </p>
                            <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] ${actionClasses(item.action)}`}>
                              {actionLabel(item.action)}
                            </span>
                          </div>
                          <p className="mt-3 text-sm text-gray-500">{formatEventTime(item.date)}</p>
                        </Link>
                      ))}
                    </div>
                  ) : (
                    <p className="mt-4 text-sm text-gray-500">
                      Your past events will appear here after they happen.
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
                      Create and manage events with ease.
                    </p>
                  </div>
                </div>
                <div className="mt-6 grid gap-5 text-sm text-gray-600">
                  <Link href="/create" className="transition hover:text-black">Create Events</Link>
                  <Link href="/help" className="transition hover:text-black">Help Center</Link>
                  <Link href="/" className="transition hover:text-black">Browse Events</Link>
                </div>
              </footer>
            </section>
          </>
        )}
      </main>
    </div>
  );
}
