"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { ApiError, apiFetch } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";
import type {
  EventCategory,
  EventCreatePayload,
  EventDetail,
  EventScheduleEntry,
} from "@/lib/types";

const CATEGORIES: EventCategory[] = [
  "Music", "Business", "Arts", "Food", "Sports", "Education",
  "Theater", "Comedy", "Festival", "Conference", "Workshop", "Other",
];

function toISO(date: string, time: string): string {
  if (!date || !time) return "";
  return new Date(`${date}T${time}`).toISOString();
}

export default function CreateEventPage() {
  const router = useRouter();

  // TODO [auth]: When real auth is wired up in lib/auth.ts, this hook will
  // redirect unauthenticated users to the sign-in page automatically.
  const user = useRequireAuth();

  const [title, setTitle] = useState("");
  const [category, setCategory] = useState<EventCategory>("Other");
  const [startDate, setStartDate] = useState("");
  const [startTime, setStartTime] = useState("");
  const [endDate, setEndDate] = useState("");
  const [endTime, setEndTime] = useState("");
  const [location, setLocation] = useState("");

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const now = new Date();
  const todayStr =
    now.getFullYear() +
    "-" +
    String(now.getMonth() + 1).padStart(2, "0") +
    "-" +
    String(now.getDate()).padStart(2, "0");
  const currentTimeStr =
    String(now.getHours()).padStart(2, "0") +
    ":" +
    String(now.getMinutes()).padStart(2, "0");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    const startISO = toISO(startDate, startTime);
    const endISO = toISO(endDate, endTime);

    if (!startISO || !endISO) {
      setError("Please fill in both start and end date/time.");
      return;
    }

    if (new Date(startISO) < new Date()) {
      setError("Start date/time must be now or in the future.");
      return;
    }

    if (new Date(endISO) <= new Date(startISO)) {
      setError("End time must be after start time.");
      return;
    }

    const payload: EventCreatePayload = {
      title: title.trim(),
      about: "",
      organizer_user_id: user.id,
      price: 0,
      total_capacity: 100,
      start_time: startISO,
      end_time: endISO,
      category,
      is_online: false,
      image_url: null,
      schedule: [] as EventScheduleEntry[],
      location: {
        longitude: 0,
        latitude: 0,
        venue_name: null,
        address: location.trim(),
        city: "San Jose",
        state: "CA",
        zip_code: "00000",
      },
    };

    setSubmitting(true);
    try {
      const created = await apiFetch<EventDetail>("/events/", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      router.push(`/events/${created.id}`);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(
          typeof err.detail === "string"
            ? err.detail
            : JSON.stringify(err.detail),
        );
      } else {
        setError(err instanceof Error ? err.message : "Something went wrong.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  const inputClass =
    "w-full rounded-md border border-gray-300 bg-gray-50 px-3 py-2 text-sm text-black placeholder:text-gray-400 focus:border-black focus:outline-none focus:ring-1 focus:ring-black";
  const labelClass = "block text-sm font-medium text-black";

  return (
    <div className="min-h-screen bg-white text-black font-sans antialiased">
      {/* Header */}
      <header className="sticky top-0 z-50 border-b border-gray-200 bg-white">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-6 px-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-8">
            <a href="/" className="flex items-center gap-2">
              <span className="flex h-8 w-8 items-center justify-center rounded bg-black text-white text-sm font-bold">E</span>
              <span className="text-lg font-semibold">Evently</span>
            </a>
            <nav className="hidden items-center gap-6 md:flex">
              <a href="/" className="text-sm font-medium text-gray-700 hover:text-black">Browse Events</a>
              <a href="/create" className="text-sm font-medium text-black">Create Event</a>
            </nav>
          </div>
          <div className="flex items-center gap-4">
            <a href="/signin" className="text-sm font-medium text-gray-700 hover:text-black">Sign In</a>
            <a href="/signup" className="rounded-md bg-black px-4 py-2 text-sm font-medium text-white hover:bg-gray-800">Sign Up</a>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-4 py-10 sm:px-6 lg:px-8">
        <h1 className="text-3xl font-bold tracking-tight">Create New Event</h1>

        {error && (
          <div className="mt-6 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="mt-8">
          <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
            <div className="space-y-6">
              <div>
                <label htmlFor="title" className={labelClass}>
                  Event Title*
                </label>
                <input
                  id="title"
                  required
                  className={inputClass}
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="Enter event title"
                />
              </div>

              <div>
                <label htmlFor="category" className={labelClass}>
                  Category*
                </label>
                <select
                  id="category"
                  required
                  className={inputClass}
                  value={category}
                  onChange={(e) => setCategory(e.target.value as EventCategory)}
                >
                  <option value="" disabled>
                    Select category
                  </option>
                  {CATEGORIES.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid gap-5 sm:grid-cols-2">
                <div>
                  <label htmlFor="start-date" className={labelClass}>
                    Start Date*
                  </label>
                  <input
                    id="start-date"
                    type="date"
                    required
                    min={todayStr}
                    className={inputClass}
                    value={startDate}
                    onChange={(e) => setStartDate(e.target.value)}
                  />
                </div>
                <div>
                  <label htmlFor="start-time" className={labelClass}>
                    Start Time*
                  </label>
                  <input
                    id="start-time"
                    type="time"
                    required
                    min={startDate === todayStr ? currentTimeStr : undefined}
                    className={inputClass}
                    value={startTime}
                    onChange={(e) => setStartTime(e.target.value)}
                  />
                </div>
                <div>
                  <label htmlFor="end-date" className={labelClass}>
                    End Date*
                  </label>
                  <input
                    id="end-date"
                    type="date"
                    required
                    min={startDate || todayStr}
                    className={inputClass}
                    value={endDate}
                    onChange={(e) => setEndDate(e.target.value)}
                  />
                </div>
                <div>
                  <label htmlFor="end-time" className={labelClass}>
                    End Time*
                  </label>
                  <input
                    id="end-time"
                    type="time"
                    required
                    min={endDate === startDate ? startTime : undefined}
                    className={inputClass}
                    value={endTime}
                    onChange={(e) => setEndTime(e.target.value)}
                  />
                </div>
              </div>

              <div>
                <label htmlFor="location" className={labelClass}>
                  Location*
                </label>
                <input
                  id="location"
                  required
                  className={inputClass}
                  value={location}
                  onChange={(e) => setLocation(e.target.value)}
                  placeholder="Enter venue address"
                />
              </div>
            </div>
          </div>

          {/* ── Submit ──────────────────────────────────────── */}
          <div className="flex items-center gap-4 border-t border-gray-200 pt-6">
            <button
              type="submit"
              disabled={submitting}
              className="rounded-md bg-black px-6 py-3 text-base font-medium text-white hover:bg-gray-800 disabled:opacity-50"
            >
              {submitting ? "Publishing…" : "Publish Event"}
            </button>
            <a href="/" className="text-sm font-medium text-gray-600 hover:text-black">
              Cancel
            </a>
          </div>
        </form>
      </main>
    </div>
  );
}
