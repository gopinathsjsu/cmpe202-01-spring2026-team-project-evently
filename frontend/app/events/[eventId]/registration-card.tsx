"use client";

import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { AuthRequiredAction } from "@/components/auth-required-action";
import { ApiError, apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth";

interface RegistrationCardProps {
  eventId: number;
  price: number;
  spotsLeft: number;
}

interface AttendanceStatusResponse {
  event_id: number;
  user_id: number;
  status: "going" | "checked_in" | "cancelled" | null;
}

interface AppCalendarStatusResponse {
  event_id: number;
  in_calendar: boolean;
  google_sync_enabled: boolean;
}

interface AppCalendarMutationResponse {
  event_id: number;
  status: "added" | "removed";
  google_synced: boolean;
}

function formatPrice(price: number): string {
  if (price === 0) return "Free";
  return `$${price.toFixed(2)}`;
}

function getErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError && typeof error.detail === "string") {
    return error.detail;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return fallback;
}

export function RegistrationCard({
  eventId,
  price,
  spotsLeft,
}: RegistrationCardProps) {
  const pathname = usePathname();
  const { user, loading: authLoading } = useAuth();
  const [status, setStatus] = useState<AttendanceStatusResponse["status"]>(null);
  const [statusLoading, setStatusLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [calendarLoading, setCalendarLoading] = useState(false);
  const [calendarStatusLoading, setCalendarStatusLoading] = useState(false);
  const [inCalendar, setInCalendar] = useState(false);
  const [googleSyncEnabled, setGoogleSyncEnabled] = useState(false);
  const [calendarMessage, setCalendarMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!user) {
      setStatus(null);
      setError(null);
      setStatusLoading(false);
      return;
    }

    let cancelled = false;
    setStatusLoading(true);

    void apiFetch<AttendanceStatusResponse>(`/events/${eventId}/attendance`)
      .then((response) => {
        if (!cancelled) {
          setStatus(response.status);
          setError(null);
        }
      })
      .catch((nextError: unknown) => {
        if (!cancelled) {
          if (nextError instanceof ApiError && nextError.status === 404) {
            setStatus(null);
            setError(null);
          } else {
            setError(
              nextError instanceof Error
                ? nextError.message
                : "Could not load your registration status.",
            );
          }
        }
      })
      .finally(() => {
        if (!cancelled) {
          setStatusLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [eventId, user]);

  useEffect(() => {
    if (!user) {
      setInCalendar(false);
      setGoogleSyncEnabled(false);
      setCalendarMessage(null);
      setCalendarStatusLoading(false);
      return;
    }

    let cancelled = false;
    setCalendarStatusLoading(true);

    void apiFetch<AppCalendarStatusResponse>(`/events/${eventId}/calendar`)
      .then((response) => {
        if (!cancelled) {
          setInCalendar(response.in_calendar);
          setGoogleSyncEnabled(response.google_sync_enabled);
          setError(null);
        }
      })
      .catch((nextError: unknown) => {
        if (!cancelled) {
          setError(
            getErrorMessage(nextError, "Could not load your calendar status."),
          );
        }
      })
      .finally(() => {
        if (!cancelled) {
          setCalendarStatusLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [eventId, user]);

  async function handleCancelRegistration() {
    const confirmed = window.confirm(
      "Are you sure you want to cancel your registration for this event?",
    );
    if (!confirmed) return;

    setActionLoading(true);
    setCalendarMessage(null);
    setError(null);

    try {
      await apiFetch(`/events/${eventId}/attendance`, {
        method: "DELETE",
      });
      setStatus("cancelled");
    } catch (nextError) {
      setError(getErrorMessage(nextError, "Could not cancel your registration."));
    } finally {
      setActionLoading(false);
    }
  }

  async function handleRegister() {
    setActionLoading(true);
    setCalendarMessage(null);
    setError(null);

    try {
      const response = await apiFetch<AttendanceStatusResponse>(
        `/events/${eventId}/attendance`,
        {
          method: "POST",
        },
      );
      setStatus(response.status);
    } catch (nextError) {
      setError(getErrorMessage(nextError, "Could not register for this event."));
    } finally {
      setActionLoading(false);
    }
  }

  async function handleAddToAppCalendar() {
    setCalendarLoading(true);
    setCalendarMessage(null);
    setError(null);

    try {
      const response = await apiFetch<AppCalendarMutationResponse>(
        `/events/${eventId}/calendar`,
        {
          method: "POST",
        },
      );
      setInCalendar(true);
      setCalendarMessage(
        response.google_synced
          ? "Added to My Calendar and synced to Google Calendar."
          : "Added to My Calendar.",
      );
    } catch (nextError) {
      setError(
        getErrorMessage(
          nextError,
          "Could not add this event to My Calendar.",
        ),
      );
    } finally {
      setCalendarLoading(false);
    }
  }

  async function handleRemoveFromAppCalendar() {
    setCalendarLoading(true);
    setCalendarMessage(null);
    setError(null);

    try {
      const response = await apiFetch<AppCalendarMutationResponse>(
        `/events/${eventId}/calendar`,
        {
          method: "DELETE",
        },
      );
      setInCalendar(false);
      setCalendarMessage(
        response.google_synced
          ? "Removed from My Calendar and Google Calendar."
          : "Removed from My Calendar.",
      );
    } catch (nextError) {
      setError(
        getErrorMessage(
          nextError,
          "Could not remove this event from My Calendar.",
        ),
      );
    } finally {
      setCalendarLoading(false);
    }
  }

  const isRegistered = status === "going";

  return (
    <>
      {error ? (
        <div className="mt-5 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      ) : null}

      {calendarMessage ? (
        <div className="mt-5 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
          {calendarMessage}
        </div>
      ) : null}

      {authLoading || statusLoading ? (
        <div className="mt-5 rounded-lg border border-zinc-200 bg-zinc-50 px-4 py-3 text-sm text-zinc-500">
          Checking registration...
        </div>
      ) : isRegistered ? (
        <>
          <div className="mt-5 flex items-center justify-between border-t border-zinc-200 pt-5 dark:border-zinc-700">
            <span className="text-sm text-zinc-500">Registration</span>
            <span className="text-sm font-semibold text-zinc-900 dark:text-white">
              You&apos;re registered
            </span>
          </div>

          <button
            type="button"
            onClick={handleCancelRegistration}
            disabled={actionLoading}
            className="mt-5 w-full rounded-full border border-red-300 bg-red-50 py-3 text-sm font-semibold text-red-700 transition-colors hover:bg-red-100 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {actionLoading ? "Cancelling..." : "Cancel Registration"}
          </button>
        </>
      ) : (
        <>
          <div className="mt-5 flex items-center justify-between border-t border-zinc-200 pt-5 dark:border-zinc-700">
            <span className="text-sm text-zinc-500">Price</span>
            <span className="text-xl font-bold text-zinc-900 dark:text-zinc-100">{formatPrice(price)}</span>
          </div>

          <AuthRequiredAction
            actionLabel="register for this event"
            onAuthenticatedClick={handleRegister}
            nextPath={pathname || `/events/${eventId}`}
            disabled={spotsLeft <= 0 || actionLoading}
            className="mt-5 w-full rounded-full bg-black py-3 text-sm font-semibold text-white transition-colors hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-white dark:text-black dark:hover:bg-zinc-200"
          >
            {spotsLeft > 0
              ? actionLoading
                ? "Registering..."
                : "Register Now"
              : "Sold Out"}
          </AuthRequiredAction>
        </>
      )}

      <div className="mt-5 flex items-center justify-between border-t border-zinc-200 pt-5 dark:border-zinc-700">
        <span className="text-sm text-zinc-500">My Calendar</span>
        <span className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
          {inCalendar ? "Saved" : "Not saved"}
        </span>
      </div>

      {user && googleSyncEnabled ? (
        <p className="mt-3 text-xs text-zinc-500 dark:text-zinc-400">
          Google Calendar sync is on. Changes here will sync automatically.
        </p>
      ) : null}

      {user && calendarStatusLoading ? (
        <div className="mt-3 rounded-lg border border-zinc-200 bg-zinc-50 px-4 py-3 text-sm text-zinc-500">
          Checking your calendar...
        </div>
      ) : (
        <>
          <AuthRequiredAction
            actionLabel={
              inCalendar ? "remove this event from your calendar" : "save this event to your calendar"
            }
            onAuthenticatedClick={
              inCalendar ? handleRemoveFromAppCalendar : handleAddToAppCalendar
            }
            nextPath={pathname || `/events/${eventId}`}
            disabled={calendarLoading}
            className={`mt-3 w-full rounded-full py-3 text-sm font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${
              inCalendar
                ? "border border-zinc-200 bg-white text-zinc-900 hover:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100 dark:hover:bg-zinc-800"
                : "bg-black text-white hover:bg-zinc-800 dark:bg-white dark:text-black dark:hover:bg-zinc-200"
            }`}
          >
            {calendarLoading
              ? inCalendar
                ? "Removing..."
                : "Saving..."
              : inCalendar
                ? "Remove from My Calendar"
                : "Add to My Calendar"}
          </AuthRequiredAction>
        </>
      )}
    </>
  );
}
