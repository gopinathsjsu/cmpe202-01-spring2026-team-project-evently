"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { EventImageUploadButton } from "@/app/components/event-image-upload-button";
import Navbar from "@/app/components/navbar";
import { ApiError, apiFetch } from "@/lib/api";
import { toBrowserSafeBackendUrl } from "@/lib/api-base";
import { useRequireAuth } from "@/lib/auth";
import type {
  EventCategory,
  EventManageDetail,
  EventUpdatePayload,
  Location,
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

function localDate(iso: string): string {
  const d = new Date(iso);
  return [
    d.getFullYear(),
    String(d.getMonth() + 1).padStart(2, "0"),
    String(d.getDate()).padStart(2, "0"),
  ].join("-");
}

function localTime(iso: string): string {
  const d = new Date(iso);
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

function apiErrorMessage(err: unknown, fallback: string): string {
  if (err instanceof ApiError) {
    return typeof err.detail === "string" ? err.detail : JSON.stringify(err.detail);
  }
  return err instanceof Error ? err.message : fallback;
}

export default function EditEventPage() {
  const router = useRouter();
  const params = useParams<{ eventId: string }>();
  const eventId = Number(params.eventId);
  const { user, loading: authLoading } = useRequireAuth();

  const [event, setEvent] = useState<EventManageDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const [title, setTitle] = useState("");
  const [about, setAbout] = useState("");
  const [category, setCategory] = useState<EventCategory>("Other");
  const [price, setPrice] = useState("0");
  const [capacity, setCapacity] = useState("100");
  const [isOnline, setIsOnline] = useState(false);
  const [startDate, setStartDate] = useState("");
  const [startTime, setStartTime] = useState("");
  const [endDate, setEndDate] = useState("");
  const [endTime, setEndTime] = useState("");
  const [venueName, setVenueName] = useState("");
  const [address, setAddress] = useState("");
  const [city, setCity] = useState("");
  const [state, setState] = useState("");
  const [zipCode, setZipCode] = useState("");

  useEffect(() => {
    if (!user || !Number.isFinite(eventId)) return;
    let cancelled = false;

    void apiFetch<EventManageDetail>(`/events/${eventId}/manage`)
      .then((res) => {
        if (cancelled) return;
        setEvent(res);
        setTitle(res.title);
        setAbout(res.about);
        setCategory(res.category);
        setPrice(String(res.price));
        setCapacity(String(res.total_capacity));
        setIsOnline(res.is_online);
        setStartDate(localDate(res.start_time));
        setStartTime(localTime(res.start_time));
        setEndDate(localDate(res.end_time));
        setEndTime(localTime(res.end_time));
        setVenueName(res.location.venue_name ?? "");
        setAddress(res.location.address);
        setCity(res.location.city);
        setState(res.location.state);
        setZipCode(res.location.zip_code);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(apiErrorMessage(err, "Failed to load event."));
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [eventId, user]);

  async function geocodeLocation(): Promise<Location> {
    const params = new URLSearchParams({
      street: address.trim(),
      city: city.trim(),
      state: state.trim(),
      postalcode: zipCode.trim(),
    });
    if (venueName.trim()) {
      params.set("venue_name", venueName.trim());
    }

    const coordinates = await apiFetch<GeocodeResult>(
      `/geocode/?${params.toString()}`,
    );

    return {
      longitude: coordinates.longitude,
      latitude: coordinates.latitude,
      venue_name: venueName.trim() || null,
      address: address.trim(),
      city: city.trim(),
      state: state.trim(),
      zip_code: zipCode.trim(),
    };
  }

  function locationChanged(): boolean {
    if (!event) return false;
    return (
      venueName !== (event.location.venue_name ?? "") ||
      address !== event.location.address ||
      city !== event.location.city ||
      state !== event.location.state ||
      zipCode !== event.location.zip_code
    );
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!event) return;

    setSaving(true);
    setError(null);
    setSuccess(null);

    try {
      const startISO = toISO(startDate, startTime);
      const endISO = toISO(endDate, endTime);
      const nextPrice = Number(price);
      const nextCapacity = Number(capacity);

      if (!title.trim() || !startISO || !endISO) {
        setError("Please complete the required event details.");
        return;
      }
      if (new Date(endISO) <= new Date(startISO)) {
        setError("End time must be after start time.");
        return;
      }
      if (!Number.isFinite(nextPrice) || nextPrice < 0) {
        setError("Price must be a valid non-negative number.");
        return;
      }
      if (!Number.isInteger(nextCapacity) || nextCapacity <= 0) {
        setError("Capacity must be a positive whole number.");
        return;
      }
      if (
        !isOnline &&
        (!address.trim() || !city.trim() || !state.trim() || !zipCode.trim())
      ) {
        setError("Please complete the full location details.");
        return;
      }

      const body: EventUpdatePayload = {};
      if (title.trim() !== event.title) body.title = title.trim();
      if (about !== event.about) body.about = about;
      if (category !== event.category) body.category = category;
      if (nextPrice !== event.price) body.price = nextPrice;
      if (nextCapacity !== event.total_capacity) body.total_capacity = nextCapacity;
      if (startISO !== event.start_time) body.start_time = startISO;
      if (endISO !== event.end_time) body.end_time = endISO;
      if (isOnline !== event.is_online) body.is_online = isOnline;
      if (!isOnline && locationChanged()) {
        body.location = await geocodeLocation();
      }

      let nextStatus = event.status;
      if (Object.keys(body).length > 0) {
        const updated = await apiFetch<EventManageDetail>(`/events/${event.id}`, {
          method: "PATCH",
          body: JSON.stringify(body),
        });
        setEvent(updated);
        nextStatus = updated.status;
      }

      setSuccess("Event updated.");
      const redirectPath =
        nextStatus === "approved"
          ? `/events/${event.id}`
          : "/my-events?tab=created";
      setTimeout(() => router.push(redirectPath), 700);
    } catch (err) {
      setError(apiErrorMessage(err, "Failed to update event."));
    } finally {
      setSaving(false);
    }
  }

  const inputClass =
    "w-full rounded-md border border-gray-300 bg-gray-50 px-3 py-2 text-sm text-black placeholder:text-gray-400 focus:border-black focus:outline-none focus:ring-1 focus:ring-black disabled:opacity-60";
  const labelClass = "block text-sm font-medium text-black";

  return (
    <div className="min-h-screen bg-white text-black font-sans antialiased">
      <Navbar />

      <main className="mx-auto max-w-3xl px-4 py-10 sm:px-6 lg:px-8">
        <nav className="mb-2 text-sm text-gray-500">
          <Link href="/" className="hover:text-black">Home</Link>
          <span className="mx-1">&gt;</span>
          <Link href="/my-events?tab=created" className="hover:text-black">My Events</Link>
          <span className="mx-1">&gt;</span>
          <span className="text-gray-900">Edit Event</span>
        </nav>

        <h1 className="text-3xl font-bold tracking-tight">Edit Event</h1>

        {(authLoading || loading) && (
          <div className="mt-6 rounded-md border border-gray-200 bg-gray-50 px-4 py-3 text-sm text-gray-600">
            Loading event...
          </div>
        )}

        {error && (
          <div className="mt-6 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {success && (
          <div className="mt-6 rounded-md border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-700">
            {success}
          </div>
        )}

        {event && (
          <form onSubmit={handleSubmit} className="mt-8 space-y-6">
            <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
              <div className="space-y-6">
                <div className="overflow-hidden rounded-xl bg-gray-100">
                  {event.image_url ? (
                    <img
                      src={toBrowserSafeBackendUrl(event.image_url)}
                      alt=""
                      className="aspect-[16/7] w-full object-cover"
                    />
                  ) : (
                    <div className="flex aspect-[16/7] items-center justify-center text-sm text-gray-400">
                      Event Banner Image
                    </div>
                  )}
                </div>

                <EventImageUploadButton
                  eventId={event.id}
                  onUploaded={(imageUrl) =>
                    setEvent((current) =>
                      current ? { ...current, image_url: imageUrl } : current,
                    )
                  }
                />

                <div>
                  <label htmlFor="title" className={labelClass}>Event Title*</label>
                  <input id="title" required className={inputClass} value={title} onChange={(e) => setTitle(e.target.value)} />
                </div>

                <div>
                  <label htmlFor="about" className={labelClass}>About</label>
                  <textarea id="about" className={`${inputClass} min-h-32`} value={about} onChange={(e) => setAbout(e.target.value)} />
                </div>

                <div className="grid gap-5 sm:grid-cols-3">
                  <div>
                    <label htmlFor="category" className={labelClass}>Category*</label>
                    <select id="category" required className={inputClass} value={category} onChange={(e) => setCategory(e.target.value as EventCategory)}>
                      {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
                    </select>
                  </div>
                  <div>
                    <label htmlFor="price" className={labelClass}>Price</label>
                    <input id="price" type="number" min="0" step="0.01" className={inputClass} value={price} onChange={(e) => setPrice(e.target.value)} />
                  </div>
                  <div>
                    <label htmlFor="capacity" className={labelClass}>Capacity*</label>
                    <input id="capacity" type="number" min="1" step="1" required className={inputClass} value={capacity} onChange={(e) => setCapacity(e.target.value)} />
                  </div>
                </div>

                <div className="grid gap-5 sm:grid-cols-2">
                  <div>
                    <label htmlFor="start-date" className={labelClass}>Start Date*</label>
                    <input id="start-date" type="date" required className={inputClass} value={startDate} onChange={(e) => setStartDate(e.target.value)} />
                  </div>
                  <div>
                    <label htmlFor="start-time" className={labelClass}>Start Time*</label>
                    <input id="start-time" type="time" required className={inputClass} value={startTime} onChange={(e) => setStartTime(e.target.value)} />
                  </div>
                  <div>
                    <label htmlFor="end-date" className={labelClass}>End Date*</label>
                    <input id="end-date" type="date" required className={inputClass} value={endDate} onChange={(e) => setEndDate(e.target.value)} />
                  </div>
                  <div>
                    <label htmlFor="end-time" className={labelClass}>End Time*</label>
                    <input id="end-time" type="time" required className={inputClass} value={endTime} onChange={(e) => setEndTime(e.target.value)} />
                  </div>
                </div>

                <label className="flex items-center gap-2 text-sm font-medium text-black">
                  <input type="checkbox" checked={isOnline} onChange={(e) => setIsOnline(e.target.checked)} />
                  Online event
                </label>

                {!isOnline && (
                  <>
                    <div>
                      <label htmlFor="venue-name" className={labelClass}>Venue Name</label>
                      <input id="venue-name" className={inputClass} value={venueName} onChange={(e) => setVenueName(e.target.value)} />
                    </div>

                    <div>
                      <label htmlFor="address" className={labelClass}>Street Address*</label>
                      <input id="address" required className={inputClass} value={address} onChange={(e) => setAddress(e.target.value)} />
                    </div>

                    <div className="grid gap-5 sm:grid-cols-3">
                      <div>
                        <label htmlFor="city" className={labelClass}>City*</label>
                        <input id="city" required className={inputClass} value={city} onChange={(e) => setCity(e.target.value)} />
                      </div>
                      <div>
                        <label htmlFor="state" className={labelClass}>State*</label>
                        <input id="state" required className={inputClass} value={state} onChange={(e) => setState(e.target.value)} />
                      </div>
                      <div>
                        <label htmlFor="zip-code" className={labelClass}>ZIP Code*</label>
                        <input id="zip-code" required className={inputClass} value={zipCode} onChange={(e) => setZipCode(e.target.value)} />
                      </div>
                    </div>
                  </>
                )}
              </div>
            </div>

            <div className="flex items-center gap-4 border-t border-gray-200 pt-6">
              <button
                type="submit"
                disabled={saving}
                className="rounded-md bg-black px-6 py-3 text-base font-medium text-white hover:bg-gray-800 disabled:opacity-50"
              >
                {saving ? "Saving..." : "Save Changes"}
              </button>
              <Link href="/my-events?tab=created" className="text-sm font-medium text-gray-600 hover:text-black">
                Cancel
              </Link>
            </div>
          </form>
        )}
      </main>
    </div>
  );
}
