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

interface AttendanceMutationResponse {
  event_id: number;
  user_id: number;
  status: "going" | "cancelled";
  in_calendar: boolean;
  google_synced: boolean;
}

interface AppCalendarStatusResponse {
  event_id: number;
  in_calendar: boolean;
  google_sync_enabled: boolean;
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
      const response = await apiFetch<AttendanceMutationResponse>(`/events/${eventId}/attendance`, {
        method: "DELETE",
      });
      setStatus(response.status);
      setInCalendar(response.in_calendar);
      setCalendarMessage(
        response.google_synced
          ? "Registration cancelled. Removed from My Calendar and Google Calendar."
          : "Registration cancelled. Removed from My Calendar.",
      );
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
      const response = await apiFetch<AttendanceMutationResponse>(
        `/events/${eventId}/attendance`,
        {
          method: "POST",
        },
      );
      setStatus(response.status);
      setInCalendar(response.in_calendar);
      setCalendarMessage(
        response.google_synced
          ? "Registered. Added to My Calendar and synced to Google Calendar."
          : "Registered. Added to My Calendar.",
      );
    } catch (nextError) {
      setError(getErrorMessage(nextError, "Could not register for this event."));
    } finally {
      setActionLoading(false);
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
      ) : user ? (
        <p className="mt-3 text-sm text-zinc-500 dark:text-zinc-400">
          {isRegistered
            ? "This event stays in My Calendar while you are registered."
            : "Registering adds this event to My Calendar automatically, and cancelling removes it."}
        </p>
      ) : (
        <p className="mt-3 text-sm text-zinc-500 dark:text-zinc-400">
          Register to have this event added to My Calendar automatically.
        </p>
      )}
    </>
  );
}
