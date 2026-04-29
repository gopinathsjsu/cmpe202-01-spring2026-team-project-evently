"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import Navbar from "@/app/components/navbar";
import { ApiError, apiFetch } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";
import { buildCreateEventPayload } from "@/lib/create-event-payload";
import type {
  EventCategory,
  EventDetail,
} from "@/lib/types";

type GeocodeResult = {
  latitude: number;
  longitude: number;
  display_name: string | null;
};

const CATEGORIES: EventCategory[] = [
  "Music",
  "Business",
  "Arts",
  "Food",
  "Sports",
  "Education",
  "Theater",
  "Comedy",
  "Festival",
  "Conference",
  "Workshop",
  "Other",
];

function toISO(date: string, time: string): string {
  if (!date || !time) return "";
  return new Date(`${date}T${time}`).toISOString();
}

export default function CreateEventPage() {
  const router = useRouter();
  const { user, loading: authLoading, error: authError } = useRequireAuth();

  const [title, setTitle] = useState("");
  const [category, setCategory] = useState<EventCategory>("Other");
  const [startDate, setStartDate] = useState("");
  const [startTime, setStartTime] = useState("");
  const [endDate, setEndDate] = useState("");
  const [endTime, setEndTime] = useState("");
  const [venueName, setVenueName] = useState("");
  const [address, setAddress] = useState("");
  const [city, setCity] = useState("");
  const [state, setState] = useState("");
  const [zipCode, setZipCode] = useState("");

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

    if (!user) {
      setError("You need to sign in before creating an event.");
      return;
    }

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

    if (
      !address.trim() ||
      !city.trim() ||
      !state.trim() ||
      !zipCode.trim()
    ) {
      setError("Please complete the full location details.");
      return;
    }

    setSubmitting(true);
    try {
      const params = new URLSearchParams({
        street: address.trim(),
        city: city.trim(),
        state: state.trim(),
        postalcode: zipCode.trim(),
      });
      const coordinates = await apiFetch<GeocodeResult>(
        `/geocode/?${params.toString()}`,
      );

      const payload = buildCreateEventPayload({
        title,
        category,
        startISO,
        endISO,
        venueName,
        address,
        city,
        state,
        zipCode,
        latitude: coordinates.latitude,
        longitude: coordinates.longitude,
      });

      if (
        !Number.isFinite(payload.location.latitude) ||
        !Number.isFinite(payload.location.longitude)
      ) {
        setError("We could not resolve valid coordinates for this address.");
        return;
      }

      const created = await apiFetch<EventDetail>("/events/", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      router.push(`/events/${created.id}`);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 401) {
          window.location.replace(`/signin?next=${encodeURIComponent("/create")}`);
          return;
        }
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
      <Navbar />

      <main className="mx-auto max-w-3xl px-4 py-10 sm:px-6 lg:px-8">
        <h1 className="text-3xl font-bold tracking-tight">Create New Event</h1>

        {authLoading && (
          <div className="mt-6 rounded-md border border-gray-200 bg-gray-50 px-4 py-3 text-sm text-gray-600">
            Loading your session...
          </div>
        )}

        {authError && (
          <div className="mt-6 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {authError}
          </div>
        )}

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
                  disabled={authLoading || !user}
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
                  disabled={authLoading || !user}
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
                    disabled={authLoading || !user}
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
                    disabled={authLoading || !user}
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
                    disabled={authLoading || !user}
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
                    disabled={authLoading || !user}
                    className={inputClass}
                    value={endTime}
                    onChange={(e) => setEndTime(e.target.value)}
                  />
                </div>
              </div>

              <div>
                <label htmlFor="venue-name" className={labelClass}>
                  Venue Name
                </label>
                <input
                  id="venue-name"
                  disabled={authLoading || !user}
                  className={inputClass}
                  value={venueName}
                  onChange={(e) => setVenueName(e.target.value)}
                  placeholder="Optional venue name"
                />
              </div>

              <div>
                <label htmlFor="address" className={labelClass}>
                  Street Address*
                </label>
                <input
                  id="address"
                  required
                  disabled={authLoading || !user}
                  className={inputClass}
                  value={address}
                  onChange={(e) => setAddress(e.target.value)}
                  placeholder="123 Main St"
                />
              </div>

              <div className="grid gap-5 sm:grid-cols-3">
                <div>
                  <label htmlFor="city" className={labelClass}>
                    City*
                  </label>
                  <input
                    id="city"
                    required
                    disabled={authLoading || !user}
                    className={inputClass}
                    value={city}
                    onChange={(e) => setCity(e.target.value)}
                    placeholder="San Jose"
                  />
                </div>
                <div>
                  <label htmlFor="state" className={labelClass}>
                    State*
                  </label>
                  <input
                    id="state"
                    required
                    disabled={authLoading || !user}
                    className={inputClass}
                    value={state}
                    onChange={(e) => setState(e.target.value)}
                    placeholder="CA"
                  />
                </div>
                <div>
                  <label htmlFor="zip-code" className={labelClass}>
                    ZIP Code*
                  </label>
                  <input
                    id="zip-code"
                    required
                    disabled={authLoading || !user}
                    className={inputClass}
                    value={zipCode}
                    onChange={(e) => setZipCode(e.target.value)}
                    placeholder="95112"
                  />
                </div>
              </div>
            </div>
          </div>

          {/* ── Submit ──────────────────────────────────────── */}
          <div className="flex items-center gap-4 border-t border-gray-200 pt-6">
            <button
              type="submit"
              disabled={submitting || authLoading || !user}
              className="rounded-md bg-black px-6 py-3 text-base font-medium text-white hover:bg-gray-800 disabled:opacity-50"
            >
              {submitting ? "Publishing…" : "Publish Event"}
            </button>
            <Link
              href="/"
              className="text-sm font-medium text-gray-600 hover:text-black"
            >
              Cancel
            </Link>
          </div>
        </form>
      </main>
    </div>
  );
}
