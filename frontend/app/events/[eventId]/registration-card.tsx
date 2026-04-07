"use client";

import { useEffect, useState } from "react";

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

function formatPrice(price: number): string {
  if (price === 0) return "Free";
  return `$${price.toFixed(2)}`;
}

export function RegistrationCard({
  eventId,
  price,
  spotsLeft,
}: RegistrationCardProps) {
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

  const isRegistered = status === "going";

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
            <span className="text-xl font-bold">{formatPrice(price)}</span>
          </div>

          <button
            type="button"
            disabled={spotsLeft <= 0}
            className="mt-5 w-full rounded-full bg-black py-3 text-sm font-semibold text-white transition-colors hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-white dark:text-black dark:hover:bg-zinc-200"
          >
            {spotsLeft > 0 ? "Register Now" : "Sold Out"}
          </button>
        </>
      )}
    </>
  );
}
