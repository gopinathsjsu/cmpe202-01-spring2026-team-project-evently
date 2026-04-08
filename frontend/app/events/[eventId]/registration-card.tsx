"use client";

import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { AuthRequiredAction } from "@/components/auth-required-action";
import { ApiError, apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth";

interface RegistrationCardProps {
  eventId: number;
  addToCalendarUrl: string;
  organizerUserId: number;
  price: number;
  spotsLeft: number;
}

interface AttendanceStatusResponse {
  event_id: number;
  user_id: number;
  status: "going" | "checked_in" | "cancelled" | null;
}

function formatPrice(price: number): string {
  if (price === 0) return "Free";
  return `$${price.toFixed(2)}`;
}

export function RegistrationCard({
  eventId,
  addToCalendarUrl,
  organizerUserId,
  price,
  spotsLeft,
}: RegistrationCardProps) {
  const pathname = usePathname();
  const { user, loading: authLoading } = useAuth();
  const [status, setStatus] = useState<AttendanceStatusResponse["status"]>(null);
  const [statusLoading, setStatusLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
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

  async function handleCancelRegistration() {
    const confirmed = window.confirm(
      "Are you sure you want to cancel your registration for this event?",
    );
    if (!confirmed) return;

    setActionLoading(true);
    setError(null);

    try {
      await apiFetch(`/events/${eventId}/attendance`, {
        method: "DELETE",
      });
      setStatus("cancelled");
    } catch (nextError) {
      setError(
        nextError instanceof Error
          ? nextError.message
          : "Could not cancel your registration.",
      );
    } finally {
      setActionLoading(false);
    }
  }

  async function handleRegister() {
    setActionLoading(true);
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
      setError(
        nextError instanceof Error
          ? nextError.message
          : "Could not register for this event.",
      );
    } finally {
      setActionLoading(false);
    }
  }

  const isRegistered = status === "going";
  const isOrganizer = user?.id === organizerUserId;
  const isOnCalendar = isOrganizer || status === "going" || status === "checked_in";

  return (
    <>
      {error ? (
        <div className="mt-5 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
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

      {!isOnCalendar ? (
        <a
          href={addToCalendarUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-3 flex w-full items-center justify-center gap-2 rounded-full border border-zinc-200 py-3 text-sm font-semibold transition-colors hover:bg-zinc-50 dark:border-zinc-700 dark:hover:bg-zinc-800"
        >
          <svg viewBox="0 0 24 24" className="h-4 w-4 fill-none stroke-current" strokeWidth={2}>
            <rect x="3" y="4" width="18" height="18" rx="2" />
            <line x1="16" y1="2" x2="16" y2="6" />
            <line x1="8" y1="2" x2="8" y2="6" />
            <line x1="3" y1="10" x2="21" y2="10" />
          </svg>
          Add to Calendar
        </a>
      ) : null}
    </>
  );
}
