"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import Navbar from "@/app/components/navbar";
import { apiFetch } from "@/lib/api";
import { useRequireAuth } from "@/lib/auth";
import type { UserDetail } from "@/lib/types";

function detailValue(value: string | null | undefined, fallback = "Not provided"): string {
  const normalized = value?.trim();
  return normalized ? normalized : fallback;
}

function initials(firstName: string | null | undefined, lastName: string | null | undefined, fallback: string): string {
  const letters = [firstName, lastName]
    .map((part) => part?.trim().charAt(0) ?? "")
    .join("")
    .toUpperCase();
  if (letters) {
    return letters;
  }
  return fallback.trim().charAt(0).toUpperCase() || "U";
}

export default function ProfilePage() {
  const { user, loading: authLoading, error: authError } = useRequireAuth();
  const [profile, setProfile] = useState<UserDetail | null>(null);
  const [profileLoading, setProfileLoading] = useState(true);
  const [profileError, setProfileError] = useState<string | null>(null);

  useEffect(() => {
    if (!user) {
      return;
    }

    let cancelled = false;

    void apiFetch<UserDetail>(`/users/${user.id}`)
      .then((response) => {
        if (!cancelled) {
          setProfile(response);
          setProfileError(null);
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setProfile(null);
          setProfileError(
            error instanceof Error ? error.message : "Could not load your profile.",
          );
        }
      })
      .finally(() => {
        if (!cancelled) {
          setProfileLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [user]);

  const displayFirstName = profile?.first_name || user?.first_name || "";
  const displayLastName = profile?.last_name || user?.last_name || "";
  const displayName = [displayFirstName, displayLastName].filter(Boolean).join(" ").trim() || user?.name || "Your Profile";

  return (
    <div className="min-h-screen bg-[#f6f4ee] text-black">
      <Navbar />

      <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6 lg:px-8">
        {authLoading || (user !== null && profileLoading) ? (
          <div className="rounded-3xl border border-gray-200 bg-white p-8 text-sm text-gray-600 shadow-sm">
            Loading your profile...
          </div>
        ) : authError ? (
          <div className="rounded-3xl border border-red-200 bg-red-50 p-8 text-sm text-red-700 shadow-sm">
            {authError}
          </div>
        ) : (
          <div className="grid gap-6 lg:grid-cols-[340px_minmax(0,1fr)]">
            <section className="rounded-3xl border border-gray-200 bg-white p-6 shadow-sm">
              <div className="flex items-center gap-4">
                <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-black text-lg font-semibold text-white">
                  {initials(displayFirstName, displayLastName, user?.name ?? "User")}
                </div>
                <div>
                  <p className="text-sm uppercase tracking-[0.18em] text-gray-500">Profile</p>
                  <h1 className="mt-1 text-2xl font-semibold tracking-tight">{displayName}</h1>
                  <p className="mt-1 text-sm text-gray-500">{user?.email ?? "Signed-in account"}</p>
                </div>
              </div>

              <div className="mt-6 grid gap-4 sm:grid-cols-2">
                <div className="rounded-2xl border border-gray-200 bg-[#faf8f3] p-4">
                  <p className="text-xs uppercase tracking-[0.16em] text-gray-500">Events Created</p>
                  <p className="mt-2 text-2xl font-semibold text-gray-900">
                    {profile?.events_created_count ?? 0}
                  </p>
                </div>
                <div className="rounded-2xl border border-gray-200 bg-[#faf8f3] p-4">
                  <p className="text-xs uppercase tracking-[0.16em] text-gray-500">Events Attended</p>
                  <p className="mt-2 text-2xl font-semibold text-gray-900">
                    {profile?.events_attended_count ?? 0}
                  </p>
                </div>
              </div>

              <div className="mt-6 flex flex-wrap gap-3">
                <Link
                  href="/calendar"
                  className="inline-flex items-center justify-center rounded-xl bg-black px-4 py-3 text-sm font-medium text-white transition hover:bg-gray-800"
                >
                  Open My Calendar
                </Link>
                <Link
                  href="/create"
                  className="inline-flex items-center justify-center rounded-xl border border-gray-300 px-4 py-3 text-sm font-medium text-gray-700 transition hover:border-black hover:text-black"
                >
                  Create Event
                </Link>
              </div>
            </section>

            <section className="space-y-6">
              {profileError ? (
                <div className="rounded-3xl border border-red-200 bg-red-50 p-6 text-sm text-red-700 shadow-sm">
                  {profileError}
                </div>
              ) : null}

              <div className="rounded-3xl border border-gray-200 bg-white p-6 shadow-sm">
                <h2 className="text-lg font-semibold">About</h2>
                <p className="mt-4 text-sm leading-6 text-gray-600">
                  {detailValue(profile?.profile.bio, "No bio added yet.")}
                </p>
              </div>

              <div className="rounded-3xl border border-gray-200 bg-white p-6 shadow-sm">
                <h2 className="text-lg font-semibold">Details</h2>
                <dl className="mt-5 grid gap-5 sm:grid-cols-2">
                  <div>
                    <dt className="text-xs uppercase tracking-[0.16em] text-gray-500">Username</dt>
                    <dd className="mt-2 text-sm text-gray-800">{detailValue(profile?.username)}</dd>
                  </div>
                  <div>
                    <dt className="text-xs uppercase tracking-[0.16em] text-gray-500">Location</dt>
                    <dd className="mt-2 text-sm text-gray-800">
                      {detailValue(profile?.profile.location)}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs uppercase tracking-[0.16em] text-gray-500">Website</dt>
                    <dd className="mt-2 text-sm text-gray-800">{detailValue(profile?.profile.website)}</dd>
                  </div>
                  <div>
                    <dt className="text-xs uppercase tracking-[0.16em] text-gray-500">Interests</dt>
                    <dd className="mt-2 text-sm text-gray-800">
                      {profile?.profile.interests.length
                        ? profile.profile.interests.join(", ")
                        : "No interests added yet."}
                    </dd>
                  </div>
                </dl>
              </div>

              <div className="rounded-3xl border border-gray-200 bg-white p-6 shadow-sm">
                <h2 className="text-lg font-semibold">Social</h2>
                <dl className="mt-5 grid gap-5 sm:grid-cols-2">
                  <div>
                    <dt className="text-xs uppercase tracking-[0.16em] text-gray-500">Twitter</dt>
                    <dd className="mt-2 text-sm text-gray-800">
                      {detailValue(profile?.profile.twitter_handle)}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs uppercase tracking-[0.16em] text-gray-500">Instagram</dt>
                    <dd className="mt-2 text-sm text-gray-800">
                      {detailValue(profile?.profile.instagram_handle)}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs uppercase tracking-[0.16em] text-gray-500">Facebook</dt>
                    <dd className="mt-2 text-sm text-gray-800">
                      {detailValue(profile?.profile.facebook_handle)}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs uppercase tracking-[0.16em] text-gray-500">LinkedIn</dt>
                    <dd className="mt-2 text-sm text-gray-800">
                      {detailValue(profile?.profile.linkedin_handle)}
                    </dd>
                  </div>
                </dl>
              </div>
            </section>
          </div>
        )}
      </main>
    </div>
  );
}
