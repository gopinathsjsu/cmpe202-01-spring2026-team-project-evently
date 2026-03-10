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
  const [about, setAbout] = useState("");
  const [category, setCategory] = useState<EventCategory>("Other");
  const [price, setPrice] = useState("0");
  const [capacity, setCapacity] = useState("100");
  const [startDate, setStartDate] = useState("");
  const [startTime, setStartTime] = useState("");
  const [endDate, setEndDate] = useState("");
  const [endTime, setEndTime] = useState("");
  const [isOnline, setIsOnline] = useState(false);
  const [imageUrl, setImageUrl] = useState("");

  const [venueName, setVenueName] = useState("");
  const [address, setAddress] = useState("");
  const [city, setCity] = useState("");
  const [state, setState] = useState("");
  const [zipCode, setZipCode] = useState("");
  const [latitude, setLatitude] = useState("37.3382");
  const [longitude, setLongitude] = useState("-121.8863");

  const [schedule, setSchedule] = useState<{ time: string; description: string }[]>([]);

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function addScheduleEntry() {
    setSchedule((s) => [...s, { time: "", description: "" }]);
  }

  function removeScheduleEntry(idx: number) {
    setSchedule((s) => s.filter((_, i) => i !== idx));
  }

  function updateScheduleEntry(idx: number, field: "time" | "description", value: string) {
    setSchedule((s) => s.map((entry, i) => (i === idx ? { ...entry, [field]: value } : entry)));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    const startISO = toISO(startDate, startTime);
    const endISO = toISO(endDate, endTime);

    if (!startISO || !endISO) {
      setError("Please fill in both start and end date/time.");
      return;
    }

    if (new Date(endISO) <= new Date(startISO)) {
      setError("End time must be after start time.");
      return;
    }

    const scheduleEntries: EventScheduleEntry[] = schedule
      .filter((s) => s.time && s.description)
      .map((s) => ({
        start_time: toISO(startDate, s.time),
        description: s.description,
      }));

    const payload: EventCreatePayload = {
      title: title.trim(),
      about: about.trim(),
      organizer_user_id: user.id,
      price: parseFloat(price) || 0,
      total_capacity: parseInt(capacity, 10) || 1,
      start_time: startISO,
      end_time: endISO,
      category,
      is_online: isOnline,
      image_url: imageUrl.trim() || null,
      schedule: scheduleEntries,
      location: {
        longitude: parseFloat(longitude) || 0,
        latitude: parseFloat(latitude) || 0,
        venue_name: venueName.trim() || null,
        address: address.trim(),
        city: city.trim(),
        state: state.trim(),
        zip_code: zipCode.trim(),
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
        <h1 className="text-3xl font-bold tracking-tight">Create Event</h1>
        <p className="mt-2 text-gray-600">Fill in the details below to publish your event.</p>

        {error && (
          <div className="mt-6 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="mt-8 space-y-8">
          {/* ── Basic Info ──────────────────────────────────── */}
          <fieldset className="space-y-5">
            <legend className="text-lg font-semibold">Basic Information</legend>

            <div>
              <label htmlFor="title" className={labelClass}>Event Title *</label>
              <input id="title" required className={inputClass} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Downtown Jazz Night" />
            </div>

            <div>
              <label htmlFor="about" className={labelClass}>Description *</label>
              <textarea id="about" required rows={4} className={inputClass} value={about} onChange={(e) => setAbout(e.target.value)} placeholder="Tell people what your event is about…" />
            </div>

            <div className="grid gap-5 sm:grid-cols-2">
              <div>
                <label htmlFor="category" className={labelClass}>Category *</label>
                <select id="category" required className={inputClass} value={category} onChange={(e) => setCategory(e.target.value as EventCategory)}>
                  {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>
              <div>
                <label htmlFor="image-url" className={labelClass}>Image URL</label>
                <input id="image-url" type="url" className={inputClass} value={imageUrl} onChange={(e) => setImageUrl(e.target.value)} placeholder="https://example.com/image.jpg" />
              </div>
            </div>
          </fieldset>

          {/* ── Date & Time ─────────────────────────────────── */}
          <fieldset className="space-y-5">
            <legend className="text-lg font-semibold">Date & Time</legend>
            <div className="grid gap-5 sm:grid-cols-2">
              <div>
                <label htmlFor="start-date" className={labelClass}>Start Date *</label>
                <input id="start-date" type="date" required className={inputClass} value={startDate} onChange={(e) => setStartDate(e.target.value)} />
              </div>
              <div>
                <label htmlFor="start-time" className={labelClass}>Start Time *</label>
                <input id="start-time" type="time" required className={inputClass} value={startTime} onChange={(e) => setStartTime(e.target.value)} />
              </div>
              <div>
                <label htmlFor="end-date" className={labelClass}>End Date *</label>
                <input id="end-date" type="date" required className={inputClass} value={endDate} onChange={(e) => setEndDate(e.target.value)} />
              </div>
              <div>
                <label htmlFor="end-time" className={labelClass}>End Time *</label>
                <input id="end-time" type="time" required className={inputClass} value={endTime} onChange={(e) => setEndTime(e.target.value)} />
              </div>
            </div>
          </fieldset>

          {/* ── Pricing & Capacity ──────────────────────────── */}
          <fieldset className="space-y-5">
            <legend className="text-lg font-semibold">Pricing & Capacity</legend>
            <div className="grid gap-5 sm:grid-cols-2">
              <div>
                <label htmlFor="price" className={labelClass}>Ticket Price ($)</label>
                <input id="price" type="number" min="0" step="0.01" className={inputClass} value={price} onChange={(e) => setPrice(e.target.value)} />
              </div>
              <div>
                <label htmlFor="capacity" className={labelClass}>Total Capacity *</label>
                <input id="capacity" type="number" min="1" required className={inputClass} value={capacity} onChange={(e) => setCapacity(e.target.value)} />
              </div>
            </div>
          </fieldset>

          {/* ── Location ────────────────────────────────────── */}
          <fieldset className="space-y-5">
            <legend className="text-lg font-semibold">Location</legend>

            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" className="h-4 w-4 rounded border-gray-300 text-black focus:ring-black" checked={isOnline} onChange={(e) => setIsOnline(e.target.checked)} />
              This is an online event
            </label>

            <div className="grid gap-5 sm:grid-cols-2">
              <div className="sm:col-span-2">
                <label htmlFor="venue" className={labelClass}>Venue Name</label>
                <input id="venue" className={inputClass} value={venueName} onChange={(e) => setVenueName(e.target.value)} placeholder="e.g. The Grand Hall" />
              </div>
              <div className="sm:col-span-2">
                <label htmlFor="address" className={labelClass}>Address *</label>
                <input id="address" required className={inputClass} value={address} onChange={(e) => setAddress(e.target.value)} placeholder="123 Main St" />
              </div>
              <div>
                <label htmlFor="city" className={labelClass}>City *</label>
                <input id="city" required className={inputClass} value={city} onChange={(e) => setCity(e.target.value)} placeholder="San Jose" />
              </div>
              <div>
                <label htmlFor="state" className={labelClass}>State *</label>
                <input id="state" required className={inputClass} value={state} onChange={(e) => setState(e.target.value)} placeholder="CA" />
              </div>
              <div>
                <label htmlFor="zip" className={labelClass}>ZIP Code *</label>
                <input id="zip" required className={inputClass} value={zipCode} onChange={(e) => setZipCode(e.target.value)} placeholder="95112" />
              </div>
            </div>

            <div className="grid gap-5 sm:grid-cols-2">
              <div>
                <label htmlFor="lat" className={labelClass}>Latitude</label>
                <input id="lat" type="number" step="any" className={inputClass} value={latitude} onChange={(e) => setLatitude(e.target.value)} />
              </div>
              <div>
                <label htmlFor="lng" className={labelClass}>Longitude</label>
                <input id="lng" type="number" step="any" className={inputClass} value={longitude} onChange={(e) => setLongitude(e.target.value)} />
              </div>
            </div>
          </fieldset>

          {/* ── Schedule ────────────────────────────────────── */}
          <fieldset className="space-y-5">
            <legend className="text-lg font-semibold">Schedule (optional)</legend>
            <p className="text-sm text-gray-500">Add agenda items for your event.</p>

            {schedule.map((entry, idx) => (
              <div key={idx} className="flex items-start gap-3">
                <div className="w-36 shrink-0">
                  <input
                    type="time"
                    className={inputClass}
                    value={entry.time}
                    onChange={(e) => updateScheduleEntry(idx, "time", e.target.value)}
                    placeholder="Time"
                  />
                </div>
                <input
                  className={`${inputClass} flex-1`}
                  value={entry.description}
                  onChange={(e) => updateScheduleEntry(idx, "description", e.target.value)}
                  placeholder="What's happening?"
                />
                <button type="button" onClick={() => removeScheduleEntry(idx)} className="mt-2 text-sm text-red-600 hover:text-red-800">
                  Remove
                </button>
              </div>
            ))}

            <button type="button" onClick={addScheduleEntry} className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50">
              + Add Schedule Item
            </button>
          </fieldset>

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
