"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import Navbar from "@/app/components/navbar";
import { apiFetch } from "@/lib/api";
import {
  activityLabel,
  formatProfileDate,
  initials,
  resolvePhotoUrl,
} from "@/lib/profile-utils";
import { useRequireAuth } from "@/lib/auth";
import type { ActivityItem, ActivityResponse, FullUserDetail } from "@/lib/types";

// ---------------------------------------------------------------------------
// Icons
// ---------------------------------------------------------------------------

function PencilIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10" />
    </svg>
  );
}

function UserIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" />
    </svg>
  );
}

function TicketIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 6v.75m0 3v.75m0 3v.75m0 3V18m-9-5.25h5.25M7.5 15h3M3.375 5.25c-.621 0-1.125.504-1.125 1.125v3.026a2.999 2.999 0 010 5.198v3.026c0 .621.504 1.125 1.125 1.125h17.25c.621 0 1.125-.504 1.125-1.125v-3.026a2.999 2.999 0 010-5.198V6.375c0-.621-.504-1.125-1.125-1.125H3.375z" />
    </svg>
  );
}

function CalendarIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5" />
    </svg>
  );
}

function HeartIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M21 8.25c0-2.485-2.099-4.5-4.688-4.5-1.935 0-3.597 1.126-4.312 2.733-.715-1.607-2.377-2.733-4.313-2.733C5.1 3.75 3 5.765 3 8.25c0 7.22 9 12 9 12s9-4.78 9-12z" />
    </svg>
  );
}

function CogIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.24-.438.613-.431.992a6.759 6.759 0 010 .255c-.007.378.138.75.43.99l1.005.828c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.02-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 010-.255c.007-.378-.138-.75-.43-.99l-1.004-.828a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.281z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
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

function EnvelopeIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M21.75 6.75v10.5a2.25 2.25 0 01-2.25 2.25h-15a2.25 2.25 0 01-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25m19.5 0v.243a2.25 2.25 0 01-1.07 1.916l-7.5 4.615a2.25 2.25 0 01-2.36 0L3.32 8.91a2.25 2.25 0 01-1.07-1.916V6.75" />
    </svg>
  );
}

function PhoneIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 6.75c0 8.284 6.716 15 15 15h2.25a2.25 2.25 0 002.25-2.25v-1.372c0-.516-.351-.966-.852-1.091l-4.423-1.106c-.44-.11-.902.055-1.173.417l-.97 1.293c-.282.376-.769.542-1.21.38a12.035 12.035 0 01-7.143-7.143c-.162-.441.004-.928.38-1.21l1.293-.97c.363-.271.527-.734.417-1.173L6.963 3.102a1.125 1.125 0 00-1.091-.852H4.5A2.25 2.25 0 002.25 4.5v2.25z" />
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

// ---------------------------------------------------------------------------
// Quick Links sidebar
// ---------------------------------------------------------------------------

const QUICK_LINKS = [
  { href: "/profile", label: "Profile", icon: UserIcon },
  { href: "/calendar", label: "My Calendar", icon: CalendarIcon },
  { href: "/my-events", label: "My Events", icon: TicketIcon },
  { href: "#", label: "Favorites", icon: HeartIcon },
  { href: "#", label: "Settings", icon: CogIcon },
] as const;

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function ProfilePage() {
  const { user, loading: authLoading, error: authError } = useRequireAuth();
  const [profile, setProfile] = useState<FullUserDetail | null>(null);
  const [profileLoading, setProfileLoading] = useState(true);
  const [profileError, setProfileError] = useState<string | null>(null);
  const [activity, setActivity] = useState<ActivityItem[]>([]);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;

    void apiFetch<FullUserDetail>("/users/me")
      .then((res) => {
        if (!cancelled) {
          setProfile(res);
          setProfileError(null);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setProfile(null);
          setProfileError(
            err instanceof Error ? err.message : "Could not load your profile.",
          );
        }
      })
      .finally(() => {
        if (!cancelled) setProfileLoading(false);
      });

    void apiFetch<ActivityResponse>(`/users/${user.id}/activity`)
      .then((res) => {
        if (!cancelled) setActivity(res.items);
      })
      .catch(() => {});

    return () => {
      cancelled = true;
    };
  }, [user]);

  // Use auth session name to match navbar exactly
  const displayName =
    [user?.first_name, user?.last_name].filter(Boolean).join(" ").trim() ||
    user?.name ||
    "Your Profile";
  const photoUrl =
    resolvePhotoUrl(profile?.profile_photo_url) ??
    resolvePhotoUrl(user?.picture);


  return (
    <div className="min-h-screen bg-white text-black font-sans antialiased">
      <Navbar />

      <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6 lg:px-8">
        {/* Breadcrumb */}
        <nav className="mb-2 text-sm text-gray-500">
          <Link href="/" className="hover:text-black">Home</Link>
          <span className="mx-1">&gt;</span>
          <span className="text-gray-900">Profile</span>
        </nav>

        {/* Page heading */}
        <div className="mb-8 flex items-center justify-between">
          <h1 className="text-3xl font-bold">My Profile</h1>
          <Link
            href="/profile/edit"
            className="inline-flex items-center gap-2 rounded-lg bg-black px-5 py-2.5 text-sm font-medium text-white transition hover:bg-gray-800"
          >
            <PencilIcon className="h-4 w-4" />
            Edit Profile
          </Link>
        </div>

        {authLoading || (user !== null && profileLoading) ? (
          <div className="rounded-xl border border-gray-200 bg-white p-8 text-sm text-gray-500">
            Loading your profile...
          </div>
        ) : authError ? (
          <div className="rounded-xl border border-red-200 bg-red-50 p-8 text-sm text-red-700">
            {authError}
          </div>
        ) : profileError ? (
          <div className="rounded-xl border border-red-200 bg-red-50 p-8 text-sm text-red-700">
            {profileError}
          </div>
        ) : (
          <div className="grid gap-6 lg:grid-cols-[300px_minmax(0,1fr)]">
            {/* ── Left sidebar ─────────────────────────────── */}
            <div className="space-y-6">
              {/* Profile card */}
              <div className="rounded-xl border border-gray-200 p-6 text-center">
                {photoUrl ? (
                  <img
                    src={photoUrl}
                    alt={displayName}
                    className="mx-auto h-24 w-24 rounded-full object-cover"
                    referrerPolicy="no-referrer"
                  />
                ) : (
                  <div className="mx-auto flex h-24 w-24 items-center justify-center rounded-full bg-gray-100 text-2xl font-semibold text-gray-500">
                    {initials(user?.first_name, user?.last_name, user?.name ?? "User")}
                  </div>
                )}
                <h2 className="mt-4 text-lg font-semibold">{displayName}</h2>
                <p className="text-sm text-gray-500">@{profile?.username ?? "username"}</p>
                {profile?.profile.location && (
                  <p className="mt-1 flex items-center justify-center gap-1 text-sm text-gray-500">
                    <MapPinIcon className="h-4 w-4 text-blue-500" />
                    {profile.profile.location}
                  </p>
                )}

                <div className="mt-5 flex items-center justify-center divide-x divide-gray-200">
                  <div className="px-4 text-center">
                    <p className="text-xl font-semibold">{profile?.events_attended_count ?? 0}</p>
                    <p className="text-xs text-gray-500">Events Attended</p>
                  </div>
                  <div className="px-4 text-center">
                    <p className="text-xl font-semibold">{profile?.events_created_count ?? 0}</p>
                    <p className="text-xs text-gray-500">Events Created</p>
                  </div>
                </div>
              </div>

              {/* Quick Links */}
              <div className="rounded-xl border border-gray-200 p-5">
                <h3 className="mb-3 text-sm font-semibold">Quick Links</h3>
                <nav className="space-y-1">
                  {QUICK_LINKS.map(({ href, label, icon: Icon }) => {
                    const active = label === "Profile";
                    return (
                      <Link
                        key={label}
                        href={href}
                        className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition ${
                          active
                            ? "bg-black text-white"
                            : "text-gray-700 hover:bg-gray-100"
                        }`}
                      >
                        <Icon className="h-4 w-4" />
                        {label}
                      </Link>
                    );
                  })}
                </nav>
              </div>
            </div>

            {/* ── Right content ─────────────────────────────── */}
            <div className="space-y-6">
              {/* About */}
              <section className="rounded-xl border border-gray-200 p-6">
                <div className="flex items-center justify-between">
                  <h2 className="text-lg font-semibold">About</h2>
                  <Link href="/profile/edit" className="text-gray-400 hover:text-black">
                    <PencilIcon className="h-4 w-4" />
                  </Link>
                </div>
                <p className="mt-4 text-sm leading-6 text-gray-600">
                  {profile?.profile.bio || "No bio added yet."}
                </p>
                {profile?.profile.interests && profile.profile.interests.length > 0 && (
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

              {/* Contact Information */}
              <section className="rounded-xl border border-gray-200 p-6">
                <div className="flex items-center justify-between">
                  <h2 className="text-lg font-semibold">Contact Information</h2>
                  <Link href="/profile/edit" className="text-gray-400 hover:text-black">
                    <PencilIcon className="h-4 w-4" />
                  </Link>
                </div>
                <dl className="mt-4 space-y-4">
                  <div className="flex items-start gap-3">
                    <EnvelopeIcon className="mt-0.5 h-5 w-5 shrink-0 text-gray-400" />
                    <div>
                      <dt className="text-xs font-medium text-gray-500">Email</dt>
                      <dd className="text-sm text-gray-900">{user?.email ?? "Not provided"}</dd>
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    <PhoneIcon className="mt-0.5 h-5 w-5 shrink-0 text-gray-400" />
                    <div>
                      <dt className="text-xs font-medium text-gray-500">Phone</dt>
                      <dd className="text-sm text-gray-900">{profile?.phone_number || "Not provided"}</dd>
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    <GlobeIcon className="mt-0.5 h-5 w-5 shrink-0 text-gray-400" />
                    <div>
                      <dt className="text-xs font-medium text-gray-500">Website</dt>
                      <dd className="text-sm text-gray-900">{profile?.profile.website || "Not provided"}</dd>
                    </div>
                  </div>
                </dl>
              </section>

              {/* Social Media */}
              <section className="rounded-xl border border-gray-200 p-6">
                <div className="flex items-center justify-between">
                  <h2 className="text-lg font-semibold">Social Media</h2>
                  <Link href="/profile/edit" className="text-gray-400 hover:text-black">
                    <PencilIcon className="h-4 w-4" />
                  </Link>
                </div>
                <div className="mt-4 grid gap-3 sm:grid-cols-2">
                  {([
                    { label: "Twitter", value: profile?.profile.twitter_handle, color: "text-sky-500" },
                    { label: "LinkedIn", value: profile?.profile.linkedin_handle, color: "text-blue-700" },
                    { label: "Instagram", value: profile?.profile.instagram_handle, color: "text-pink-500" },
                    { label: "Facebook", value: profile?.profile.facebook_handle, color: "text-blue-600" },
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

              {/* Recent Activity */}
              <section className="rounded-xl border border-gray-200 p-6">
                <h2 className="text-lg font-semibold">Recent Activity</h2>
                {activity.length === 0 ? (
                  <p className="mt-4 text-sm text-gray-500">No recent activity.</p>
                ) : (
                  <div className="mt-4 space-y-4">
                    {activity.map((item) => (
                      <Link
                        key={`${item.event_id}-${item.action}`}
                        href={`/events/${item.event_id}`}
                        className="flex items-center gap-4 rounded-lg p-2 transition hover:bg-gray-50"
                      >
                        <div className="h-10 w-10 shrink-0 overflow-hidden rounded-lg bg-gray-100">
                          {item.event_image_url && (
                            <img
                              src={resolvePhotoUrl(item.event_image_url) ?? ""}
                              alt=""
                              className="h-full w-full object-cover"
                            />
                          )}
                        </div>
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-sm font-medium text-gray-900">
                            {activityLabel(item.action)} {item.event_title}
                          </p>
                          <p className="text-xs text-gray-500">{formatProfileDate(item.date)}</p>
                        </div>
                      </Link>
                    ))}
                  </div>
                )}
              </section>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
