"use client";

import Link from "next/link";
import Image from "next/image";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import Navbar from "@/app/components/navbar";
import { ApiError, apiFetch } from "@/lib/api";
import { toBrowserSafeBackendUrl } from "@/lib/api-base";
import { useAuth } from "@/lib/auth";
import type { ActivityItem, ActivityResponse, UserDetail } from "@/lib/types";

type ProfileResult = {
  userId: number;
  profile: UserDetail | null;
  error: string | null;
};

function resolvePhotoUrl(url: string | null | undefined): string | null {
  if (!url) return null;
  return toBrowserSafeBackendUrl(url);
}

function initials(
  firstName: string | null | undefined,
  lastName: string | null | undefined,
  fallback: string,
): string {
  const letters = [firstName, lastName]
    .map((part) => part?.trim().charAt(0) ?? "")
    .join("")
    .toUpperCase();
  return letters || fallback.trim().charAt(0).toUpperCase() || "U";
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", {
    month: "long",
    day: "numeric",
    year: "numeric",
  });
}

function externalHref(url: string): string {
  return /^https?:\/\//i.test(url) ? url : `https://${url}`;
}

function activityLabel(action: ActivityItem["action"]): string {
  switch (action) {
    case "attended":
      return "Attended";
    case "created":
      return "Created";
    case "registered":
      return "Registered for";
  }
}

function PencilIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10" />
    </svg>
  );
}

function MapPinIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 10.5a3 3 0 11-6 0 3 3 0 016 0z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 10.5c0 7.142-7.5 11.25-7.5 11.25S4.5 17.642 4.5 10.5a7.5 7.5 0 1115 0z" />
    </svg>
  );
}

function GlobeIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 21a9.004 9.004 0 008.716-6.747M12 21a9.004 9.004 0 01-8.716-6.747M12 21c2.485 0 4.5-4.03 4.5-9S14.485 3 12 3m0 18c-2.485 0-4.5-4.03-4.5-9S9.515 3 12 3m0 0a8.997 8.997 0 017.843 4.582M12 3a8.997 8.997 0 00-7.843 4.582m15.686 0A11.953 11.953 0 0112 10.5c-2.998 0-5.74-1.1-7.843-2.918m15.686 0A8.959 8.959 0 0121 12c0 .778-.099 1.533-.284 2.253m0 0A17.919 17.919 0 0112 16.5c-3.162 0-6.133-.815-8.716-2.247m0 0A9.015 9.015 0 013 12c0-1.605.42-3.113 1.157-4.418" />
    </svg>
  );
}

export default function PublicProfilePage() {
  const params = useParams<{ userId?: string | string[] }>();
  const { user } = useAuth();
  const [profileResult, setProfileResult] = useState<ProfileResult | null>(null);
  const [activity, setActivity] = useState<ActivityItem[]>([]);

  const userId = useMemo(() => {
    const raw = Array.isArray(params.userId) ? params.userId[0] : params.userId;
    const parsed = Number(raw);
    return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
  }, [params.userId]);

  useEffect(() => {
    if (userId === null) {
      return;
    }

    let cancelled = false;

    void apiFetch<UserDetail>(`/users/${userId}`)
      .then((res) => {
        if (!cancelled) {
          setProfileResult({ userId, profile: res, error: null });
        }
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        let error = "Could not load profile.";
        if (err instanceof ApiError && err.status === 404) {
          error = "User not found.";
        } else if (err instanceof Error) {
          error = err.message;
        }
        setProfileResult({ userId, profile: null, error });
      });

    return () => {
      cancelled = true;
    };
  }, [userId]);

  const resultMatches = userId !== null && profileResult?.userId === userId;
  const profile = resultMatches ? profileResult.profile : null;
  const isOwner = user !== null && profile !== null && user.id === profile.id;
  const visibleActivity = isOwner ? activity : [];
  const displayName =
    profile === null
      ? "Profile"
      : [profile.first_name, profile.last_name].filter(Boolean).join(" ").trim() ||
        profile.username;
  const photoUrl = resolvePhotoUrl(profile?.profile_photo_url);

  useEffect(() => {
    if (!isOwner || profile === null) {
      return;
    }

    let cancelled = false;
    void apiFetch<ActivityResponse>(`/users/${profile.id}/activity`)
      .then((res) => {
        if (!cancelled) setActivity(res.items);
      })
      .catch(() => {
        if (!cancelled) setActivity([]);
      });

    return () => {
      cancelled = true;
    };
  }, [isOwner, profile]);

  const displayError = userId === null ? "User not found." : resultMatches ? profileResult.error : null;
  const isLoading = userId !== null && !resultMatches;

  return (
    <div className="min-h-screen bg-white text-black font-sans antialiased">
      <Navbar />

      <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6 lg:px-8">
        <nav className="mb-2 text-sm text-gray-500">
          <Link href="/" className="hover:text-black">Home</Link>
          <span className="mx-1">&gt;</span>
          <span className="text-gray-900">{displayName}</span>
        </nav>

        <div className="mb-8 flex items-center justify-between gap-4">
          <h1 className="text-3xl font-bold">{displayName}</h1>
          {isOwner && (
            <Link
              href="/profile/edit"
              className="inline-flex items-center gap-2 rounded-lg bg-black px-5 py-2.5 text-sm font-medium text-white transition hover:bg-gray-800"
            >
              <PencilIcon className="h-4 w-4" />
              Edit Profile
            </Link>
          )}
        </div>

        {isLoading ? (
          <div className="rounded-xl border border-gray-200 bg-white p-8 text-sm text-gray-500">
            Loading profile...
          </div>
        ) : displayError ? (
          <div className="rounded-xl border border-red-200 bg-red-50 p-8 text-sm text-red-700">
            {displayError}
          </div>
        ) : profile ? (
          <div className="grid gap-6 lg:grid-cols-[300px_minmax(0,1fr)]">
            <div className="space-y-6">
              <div className="rounded-xl border border-gray-200 p-6 text-center">
                {photoUrl ? (
                  <Image
                    src={photoUrl}
                    alt={displayName}
                    width={96}
                    height={96}
                    className="mx-auto h-24 w-24 rounded-full object-cover"
                    referrerPolicy="no-referrer"
                  />
                ) : (
                  <div className="mx-auto flex h-24 w-24 items-center justify-center rounded-full bg-gray-100 text-2xl font-semibold text-gray-500">
                    {initials(profile.first_name, profile.last_name, profile.username)}
                  </div>
                )}
                <h2 className="mt-4 text-lg font-semibold">{displayName}</h2>
                <p className="text-sm text-gray-500">@{profile.username}</p>
                {profile.profile.location && (
                  <p className="mt-1 flex items-center justify-center gap-1 text-sm text-gray-500">
                    <MapPinIcon className="h-4 w-4 text-blue-500" />
                    {profile.profile.location}
                  </p>
                )}

                <div className="mt-5 flex items-center justify-center divide-x divide-gray-200">
                  <div className="px-4 text-center">
                    <p className="text-xl font-semibold">{profile.events_attended_count}</p>
                    <p className="text-xs text-gray-500">Events Attended</p>
                  </div>
                  <div className="px-4 text-center">
                    <p className="text-xl font-semibold">{profile.events_created_count}</p>
                    <p className="text-xs text-gray-500">Events Created</p>
                  </div>
                </div>
              </div>

              {profile.profile.website && (
                <a
                  href={externalHref(profile.profile.website)}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center gap-3 rounded-xl border border-gray-200 p-5 text-sm font-medium text-gray-700 transition hover:border-black hover:text-black"
                >
                  <GlobeIcon className="h-5 w-5 shrink-0 text-gray-400" />
                  <span className="min-w-0 truncate">{profile.profile.website}</span>
                </a>
              )}
            </div>

            <div className="space-y-6">
              <section className="rounded-xl border border-gray-200 p-6">
                <h2 className="text-lg font-semibold">About</h2>
                <p className="mt-4 text-sm leading-6 text-gray-600">
                  {profile.profile.bio || "No bio added yet."}
                </p>
                {profile.profile.interests.length > 0 && (
                  <div className="mt-4 flex flex-wrap gap-2">
                    {profile.profile.interests.map((tag) => (
                      <span
                        key={tag}
                        className="rounded-full border border-gray-200 px-3 py-1 text-xs font-medium text-gray-700"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                )}
              </section>

              <section className="rounded-xl border border-gray-200 p-6">
                <h2 className="text-lg font-semibold">Social Media</h2>
                <div className="mt-4 grid gap-3 sm:grid-cols-2">
                  {([
                    { label: "Twitter", value: profile.profile.twitter_handle, color: "text-sky-500" },
                    { label: "LinkedIn", value: profile.profile.linkedin_handle, color: "text-blue-700" },
                    { label: "Instagram", value: profile.profile.instagram_handle, color: "text-pink-500" },
                    { label: "Facebook", value: profile.profile.facebook_handle, color: "text-blue-600" },
                  ] as const).map(({ label, value, color }) => (
                    <div
                      key={label}
                      className="flex items-center gap-3 rounded-lg border border-gray-200 px-4 py-3"
                    >
                      <span className={`text-lg font-bold ${color}`}>
                        {label.charAt(0)}
                      </span>
                      <div className="min-w-0">
                        <p className="text-xs text-gray-500">{label}</p>
                        <p className="truncate text-sm text-gray-900">
                          {value || "Not connected"}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </section>

              {isOwner && (
                <section className="rounded-xl border border-gray-200 p-6">
                  <h2 className="text-lg font-semibold">Recent Activity</h2>
                  {visibleActivity.length === 0 ? (
                    <p className="mt-4 text-sm text-gray-500">No recent activity.</p>
                  ) : (
                    <div className="mt-4 space-y-4">
                      {visibleActivity.map((item) => (
                        <Link
                          key={`${item.event_id}-${item.action}`}
                          href={`/events/${item.event_id}`}
                          className="flex items-center gap-4 rounded-lg p-2 transition hover:bg-gray-50"
                        >
                          <div className="h-10 w-10 shrink-0 overflow-hidden rounded-lg bg-gray-100">
                            {item.event_image_url && (
                              <Image
                                src={toBrowserSafeBackendUrl(item.event_image_url)}
                                alt=""
                                width={40}
                                height={40}
                                className="h-full w-full object-cover"
                              />
                            )}
                          </div>
                          <div className="min-w-0 flex-1">
                            <p className="truncate text-sm font-medium text-gray-900">
                              {activityLabel(item.action)} {item.event_title}
                            </p>
                            <p className="text-xs text-gray-500">{formatDate(item.date)}</p>
                          </div>
                        </Link>
                      ))}
                    </div>
                  )}
                </section>
              )}
            </div>
          </div>
        ) : null}
      </main>
    </div>
  );
}
