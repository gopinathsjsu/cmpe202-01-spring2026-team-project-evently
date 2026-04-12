"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import Navbar from "@/app/components/navbar";
import { ApiError, apiFetch } from "@/lib/api";
import { getPublicApiBase } from "@/lib/api-base";
import { useRequireAuth } from "@/lib/auth";
import type { FullUserDetail } from "@/lib/types";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function resolvePhotoUrl(url: string | null | undefined): string | null {
  if (!url) return null;
  if (url.startsWith("http://") || url.startsWith("https://")) return url;
  return `${getPublicApiBase()}${url}`;
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

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function EditProfilePage() {
  const router = useRouter();
  const { user, loading: authLoading } = useRequireAuth();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [profile, setProfile] = useState<FullUserDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [photoUploading, setPhotoUploading] = useState(false);

  // Form fields
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [username, setUsername] = useState("");
  const [bio, setBio] = useState("");
  const [location, setLocation] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [website, setWebsite] = useState("");
  const [twitter, setTwitter] = useState("");
  const [linkedin, setLinkedin] = useState("");
  const [instagram, setInstagram] = useState("");
  const [facebook, setFacebook] = useState("");
  const [interests, setInterests] = useState<string[]>([]);
  const [newInterest, setNewInterest] = useState("");
  const [photoUrl, setPhotoUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;

    void apiFetch<FullUserDetail>("/users/me")
      .then((res) => {
        if (cancelled) return;
        setProfile(res);
        setFirstName(res.first_name || user.first_name);
        setLastName(res.last_name || user.last_name);
        setUsername(res.username);
        setBio(res.profile.bio ?? "");
        setLocation(res.profile.location ?? "");
        setEmail(res.email || user.email);
        setPhone(res.phone_number ?? "");
        setWebsite(res.profile.website ?? "");

        setTwitter(res.profile.twitter_handle ?? "");
        setLinkedin(res.profile.linkedin_handle ?? "");
        setInstagram(res.profile.instagram_handle ?? "");
        setFacebook(res.profile.facebook_handle ?? "");
        setInterests(res.profile.interests ?? []);
        setPhotoUrl(resolvePhotoUrl(res.profile_photo_url));
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load profile.");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [user]);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!user) return;

    setSaving(true);
    setError(null);
    setSuccess(null);

    try {
      const body: Record<string, unknown> = {};
      if (firstName !== profile?.first_name) body.first_name = firstName;
      if (lastName !== profile?.last_name) body.last_name = lastName;
      if (username !== profile?.username) body.username = username;
      if (email !== profile?.email) body.email = email;
      if (phone !== (profile?.phone_number ?? "")) body.phone_number = phone || null;
      if (bio !== (profile?.profile.bio ?? "")) body.bio = bio || null;
      if (location !== (profile?.profile.location ?? "")) body.location = location || null;
      if (website !== (profile?.profile.website ?? "")) body.website = website || null;
      if (twitter !== (profile?.profile.twitter_handle ?? "")) body.twitter_handle = twitter || null;
      if (linkedin !== (profile?.profile.linkedin_handle ?? "")) body.linkedin_handle = linkedin || null;
      if (instagram !== (profile?.profile.instagram_handle ?? "")) body.instagram_handle = instagram || null;
      if (facebook !== (profile?.profile.facebook_handle ?? "")) body.facebook_handle = facebook || null;

      const interestsChanged =
        JSON.stringify(interests) !== JSON.stringify(profile?.profile.interests ?? []);
      if (interestsChanged) body.interests = interests;

      if (Object.keys(body).length > 0) {
        await apiFetch(`/users/${user.id}`, {
          method: "PATCH",
          body: JSON.stringify(body),
        });
      }

      setSuccess("Profile updated successfully.");
      setTimeout(() => router.push("/profile"), 800);
    } catch (err) {
      setError(
        err instanceof ApiError ? String(err.detail) : "Failed to save changes.",
      );
    } finally {
      setSaving(false);
    }
  }

  async function handlePhotoUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file || !user) return;

    setPhotoUploading(true);
    setError(null);

    try {
      const form = new FormData();
      form.append("file", file);
      const res = await apiFetch<{ profile_photo_url: string | null }>(
        `/users/${user.id}/photo`,
        { method: "POST", body: form },
      );
      setPhotoUrl(resolvePhotoUrl(res.profile_photo_url));
    } catch (err) {
      setError(
        err instanceof ApiError ? String(err.detail) : "Failed to upload photo.",
      );
    } finally {
      setPhotoUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  async function handlePhotoRemove() {
    if (!user) return;
    setPhotoUploading(true);
    setError(null);

    try {
      await apiFetch(`/users/${user.id}/photo`, { method: "DELETE" });
      setPhotoUrl(null);
    } catch (err) {
      setError(
        err instanceof ApiError ? String(err.detail) : "Failed to remove photo.",
      );
    } finally {
      setPhotoUploading(false);
    }
  }

  function addInterest() {
    const trimmed = newInterest.trim();
    if (trimmed && !interests.includes(trimmed)) {
      setInterests([...interests, trimmed]);
    }
    setNewInterest("");
  }

  function removeInterest(tag: string) {
    setInterests(interests.filter((t) => t !== tag));
  }

  const inputClass =
    "w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:border-black focus:outline-none focus:ring-1 focus:ring-black";
  const labelClass = "block text-xs font-medium text-gray-500 mb-1";

  return (
    <div className="min-h-screen bg-white text-black font-sans antialiased">
      <Navbar />

      <main className="mx-auto max-w-3xl px-4 py-8 sm:px-6 lg:px-8">
        {/* Breadcrumb */}
        <nav className="mb-2 text-sm text-gray-500">
          <Link href="/" className="hover:text-black">Home</Link>
          <span className="mx-1">&gt;</span>
          <Link href="/profile" className="hover:text-black">Profile</Link>
          <span className="mx-1">&gt;</span>
          <span className="text-gray-900">Edit Profile</span>
        </nav>

        <h1 className="mb-8 text-3xl font-bold">Edit Profile</h1>

        {authLoading || loading ? (
          <div className="rounded-xl border border-gray-200 p-8 text-sm text-gray-500">
            Loading...
          </div>
        ) : (
          <form onSubmit={handleSave}>
            <div className="rounded-xl border border-gray-200 p-6 sm:p-8 space-y-8">
              {/* Status messages */}
              {error && (
                <div className="rounded-md bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
                  {error}
                </div>
              )}
              {success && (
                <div className="rounded-md bg-green-50 border border-green-200 px-4 py-3 text-sm text-green-700">
                  {success}
                </div>
              )}

              {/* Profile Photo */}
              <div>
                <h2 className="text-base font-semibold mb-4">Profile Photo</h2>
                <div className="flex items-center gap-4">
                  {photoUrl ? (
                    <img
                      src={photoUrl}
                      alt="Profile"
                      className="h-16 w-16 rounded-full object-cover"
                      referrerPolicy="no-referrer"
                    />
                  ) : (
                    <div className="flex h-16 w-16 items-center justify-center rounded-full bg-gray-100 text-lg font-semibold text-gray-500">
                      {initials(firstName, lastName, user?.name ?? "User")}
                    </div>
                  )}
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      disabled={photoUploading}
                      onClick={() => fileInputRef.current?.click()}
                      className="rounded-md bg-black px-4 py-2 text-sm font-medium text-white transition hover:bg-gray-800 disabled:opacity-50"
                    >
                      Upload New Photo
                    </button>
                    {photoUrl && (
                      <button
                        type="button"
                        disabled={photoUploading}
                        onClick={handlePhotoRemove}
                        className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 transition hover:border-black hover:text-black disabled:opacity-50"
                      >
                        Remove
                      </button>
                    )}
                  </div>
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/jpeg,image/png,image/gif"
                    className="hidden"
                    onChange={handlePhotoUpload}
                  />
                </div>
                <p className="mt-2 text-xs text-gray-500">JPG, PNG or GIF. Max size 5MB.</p>
              </div>

              <hr className="border-gray-200" />

              {/* Basic Information */}
              <div>
                <h2 className="text-base font-semibold mb-4">Basic Information</h2>
                <div className="grid gap-4 sm:grid-cols-2">
                  <div>
                    <label htmlFor="firstName" className={labelClass}>First Name</label>
                    <input
                      id="firstName"
                      className={inputClass}
                      value={firstName}
                      onChange={(e) => setFirstName(e.target.value)}
                    />
                  </div>
                  <div>
                    <label htmlFor="lastName" className={labelClass}>Last Name</label>
                    <input
                      id="lastName"
                      className={inputClass}
                      value={lastName}
                      onChange={(e) => setLastName(e.target.value)}
                    />
                  </div>
                </div>
                <div className="mt-4">
                  <label htmlFor="username" className={labelClass}>Username</label>
                  <input
                    id="username"
                    className={inputClass}
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                  />
                </div>
                <div className="mt-4">
                  <label htmlFor="bio" className={labelClass}>Bio</label>
                  <textarea
                    id="bio"
                    rows={3}
                    className={inputClass}
                    value={bio}
                    onChange={(e) => setBio(e.target.value)}
                  />
                </div>
                <div className="mt-4">
                  <label htmlFor="location" className={labelClass}>Location</label>
                  <input
                    id="location"
                    className={inputClass}
                    value={location}
                    onChange={(e) => setLocation(e.target.value)}
                  />
                </div>
              </div>

              <hr className="border-gray-200" />

              {/* Contact Information */}
              <div>
                <h2 className="text-base font-semibold mb-4">Contact Information</h2>
                <div>
                  <label htmlFor="email" className={labelClass}>Email</label>
                  <input
                    id="email"
                    type="email"
                    className={inputClass}
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                  />
                </div>
                <div className="mt-4">
                  <label htmlFor="phone" className={labelClass}>Phone</label>
                  <input
                    id="phone"
                    type="tel"
                    className={inputClass}
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                  />
                </div>
                <div className="mt-4">
                  <label htmlFor="website" className={labelClass}>Website</label>
                  <input
                    id="website"
                    type="url"
                    className={inputClass}
                    placeholder="https://"
                    value={website}
                    onChange={(e) => setWebsite(e.target.value)}
                  />
                </div>
              </div>

              <hr className="border-gray-200" />

              {/* Social Media Links */}
              <div>
                <h2 className="text-base font-semibold mb-4">Social Media Links</h2>
                {([
                  { id: "twitter", label: "Twitter", icon: "🐦", value: twitter, set: setTwitter },
                  { id: "linkedin", label: "LinkedIn", icon: "💼", value: linkedin, set: setLinkedin },
                  { id: "instagram", label: "Instagram", icon: "📷", value: instagram, set: setInstagram },
                  { id: "facebook", label: "Facebook", icon: "👤", value: facebook, set: setFacebook },
                ] as const).map(({ id, label, icon, value, set }) => (
                  <div key={id} className="mt-4 first:mt-0">
                    <label htmlFor={id} className={labelClass}>
                      <span className="mr-1">{icon}</span> {label}
                    </label>
                    <input
                      id={id}
                      className={inputClass}
                      value={value}
                      onChange={(e) => set(e.target.value)}
                    />
                  </div>
                ))}
              </div>

              <hr className="border-gray-200" />

              {/* Interests */}
              <div>
                <h2 className="text-base font-semibold mb-4">Interests</h2>
                <div className="flex flex-wrap gap-2 mb-3">
                  {interests.map((tag) => (
                    <span
                      key={tag}
                      className="inline-flex items-center gap-1 rounded-full border border-gray-200 bg-gray-50 px-3 py-1 text-xs font-medium text-gray-700"
                    >
                      {tag}
                      <button
                        type="button"
                        onClick={() => removeInterest(tag)}
                        className="ml-0.5 text-gray-400 hover:text-red-500"
                        aria-label={`Remove ${tag}`}
                      >
                        &times;
                      </button>
                    </span>
                  ))}
                </div>
                <div className="flex gap-2">
                  <input
                    className={inputClass}
                    placeholder="Add an interest..."
                    value={newInterest}
                    onChange={(e) => setNewInterest(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        e.preventDefault();
                        addInterest();
                      }
                    }}
                  />
                  <button
                    type="button"
                    onClick={addInterest}
                    className="shrink-0 rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:border-black hover:text-black"
                  >
                    Add
                  </button>
                </div>
              </div>
            </div>

            {/* Actions */}
            <div className="mt-6 flex items-center justify-end gap-3">
              <Link
                href="/profile"
                className="rounded-md border border-gray-300 px-5 py-2.5 text-sm font-medium text-gray-700 transition hover:border-black hover:text-black"
              >
                Cancel
              </Link>
              <button
                type="submit"
                disabled={saving}
                className="rounded-md bg-black px-5 py-2.5 text-sm font-medium text-white transition hover:bg-gray-800 disabled:opacity-50"
              >
                {saving ? "Saving..." : "Save Changes"}
              </button>
            </div>
          </form>
        )}
      </main>
    </div>
  );
}
