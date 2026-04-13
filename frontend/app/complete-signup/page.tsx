"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useMemo, useState } from "react";

import Navbar from "@/app/components/navbar";
import { ApiError, apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth";

interface PendingSignupUser {
  email: string;
  first_name: string;
  last_name: string;
  suggested_username: string;
  picture: string | null;
}

interface PendingSignupResponse {
  pending: PendingSignupUser | null;
}

interface CompleteSignupResponse {
  user: {
    id: number;
    email: string;
    first_name: string;
    last_name: string;
    name: string;
    roles: string[];
    picture: string | null;
  };
  redirect_to: string;
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

export default function CompleteSignupPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const [pending, setPending] = useState<PendingSignupUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [username, setUsername] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [phoneNumber, setPhoneNumber] = useState("");
  const [bio, setBio] = useState("");
  const [location, setLocation] = useState("");
  const [website, setWebsite] = useState("");
  const [twitter, setTwitter] = useState("");
  const [instagram, setInstagram] = useState("");
  const [facebook, setFacebook] = useState("");
  const [linkedin, setLinkedin] = useState("");
  const [interestsInput, setInterestsInput] = useState("");

  useEffect(() => {
    if (!authLoading && user) {
      router.replace("/profile");
    }
  }, [authLoading, router, user]);

  useEffect(() => {
    let cancelled = false;

    void apiFetch<PendingSignupResponse>("/auth/pending-signup", {
      cache: "no-store",
    })
      .then((response) => {
        if (cancelled) {
          return;
        }
        setPending(response.pending);
        setUsername(response.pending?.suggested_username ?? "");
        setFirstName(response.pending?.first_name ?? "");
        setLastName(response.pending?.last_name ?? "");
        setError(null);
      })
      .catch((nextError: unknown) => {
        if (!cancelled) {
          setError(
            getErrorMessage(nextError, "Could not load your signup session."),
          );
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const interests = useMemo(
    () =>
      interestsInput
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean),
    [interestsInput],
  );

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);

    try {
      const response = await apiFetch<CompleteSignupResponse>(
        "/auth/complete-signup",
        {
          method: "POST",
          body: JSON.stringify({
            username,
            first_name: firstName,
            last_name: lastName,
            phone_number: phoneNumber || null,
            bio: bio || null,
            location: location || null,
            website: website || null,
            twitter_handle: twitter || null,
            instagram_handle: instagram || null,
            facebook_handle: facebook || null,
            linkedin_handle: linkedin || null,
            interests,
          }),
        },
      );

      window.location.replace(response.redirect_to || "/profile");
    } catch (nextError: unknown) {
      setError(
        getErrorMessage(nextError, "Could not finish creating your account."),
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen bg-[#f6f4ee] text-black">
      <Navbar />
      <main className="mx-auto max-w-4xl px-4 py-10 sm:px-6 lg:px-8">
        <div className="rounded-3xl border border-gray-200 bg-white p-6 shadow-sm sm:p-8">
          <p className="text-sm font-medium uppercase tracking-[0.2em] text-gray-500">
            Google Sign Up
          </p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight">
            Complete your Evently account
          </h1>
          <p className="mt-3 max-w-2xl text-sm text-gray-600">
            Your Google account is verified. Finish setting up your Evently
            profile so we can add you to the system.
          </p>

          {loading || authLoading ? (
            <div className="mt-8 rounded-2xl border border-gray-200 bg-gray-50 px-4 py-6 text-sm text-gray-600">
              Loading your signup session...
            </div>
          ) : pending === null ? (
            <div className="mt-8 rounded-2xl border border-gray-200 bg-gray-50 p-6">
              <p className="text-sm text-gray-700">
                No pending Google signup was found. Continue with Google to
                create your Evently account.
              </p>
              <div className="mt-5 flex flex-wrap gap-3">
                <a
                  href="/signup"
                  className="inline-flex items-center justify-center rounded-xl bg-black px-4 py-3 text-sm font-medium text-white transition hover:bg-gray-800"
                >
                  Continue with Google
                </a>
                <Link
                  href="/"
                  className="inline-flex items-center justify-center rounded-xl border border-gray-300 px-4 py-3 text-sm font-medium text-gray-700 transition hover:border-black hover:text-black"
                >
                  Back to Home
                </Link>
              </div>
            </div>
          ) : (
            <form className="mt-8 space-y-8" onSubmit={handleSubmit}>
              <section className="grid gap-5 sm:grid-cols-2">
                <label className="block">
                  <span className="mb-2 block text-sm font-medium text-gray-700">
                    Email
                  </span>
                  <input
                    type="email"
                    value={pending.email}
                    disabled
                    className="w-full rounded-xl border border-gray-200 bg-gray-100 px-4 py-3 text-sm text-gray-500"
                  />
                </label>
                <label className="block">
                  <span className="mb-2 block text-sm font-medium text-gray-700">
                    Username
                  </span>
                  <input
                    type="text"
                    value={username}
                    onChange={(event) => setUsername(event.target.value)}
                    required
                    className="w-full rounded-xl border border-gray-300 px-4 py-3 text-sm outline-none transition focus:border-black"
                  />
                </label>
                <label className="block">
                  <span className="mb-2 block text-sm font-medium text-gray-700">
                    First Name
                  </span>
                  <input
                    type="text"
                    value={firstName}
                    onChange={(event) => setFirstName(event.target.value)}
                    className="w-full rounded-xl border border-gray-300 px-4 py-3 text-sm outline-none transition focus:border-black"
                  />
                </label>
                <label className="block">
                  <span className="mb-2 block text-sm font-medium text-gray-700">
                    Last Name
                  </span>
                  <input
                    type="text"
                    value={lastName}
                    onChange={(event) => setLastName(event.target.value)}
                    className="w-full rounded-xl border border-gray-300 px-4 py-3 text-sm outline-none transition focus:border-black"
                  />
                </label>
              </section>

              <section className="grid gap-5 sm:grid-cols-2">
                <label className="block sm:col-span-2">
                  <span className="mb-2 block text-sm font-medium text-gray-700">
                    Bio
                  </span>
                  <textarea
                    value={bio}
                    onChange={(event) => setBio(event.target.value)}
                    rows={4}
                    className="w-full rounded-xl border border-gray-300 px-4 py-3 text-sm outline-none transition focus:border-black"
                  />
                </label>
                <label className="block">
                  <span className="mb-2 block text-sm font-medium text-gray-700">
                    Phone Number
                  </span>
                  <input
                    type="text"
                    value={phoneNumber}
                    onChange={(event) => setPhoneNumber(event.target.value)}
                    className="w-full rounded-xl border border-gray-300 px-4 py-3 text-sm outline-none transition focus:border-black"
                  />
                </label>
                <label className="block">
                  <span className="mb-2 block text-sm font-medium text-gray-700">
                    Location
                  </span>
                  <input
                    type="text"
                    value={location}
                    onChange={(event) => setLocation(event.target.value)}
                    className="w-full rounded-xl border border-gray-300 px-4 py-3 text-sm outline-none transition focus:border-black"
                  />
                </label>
                <label className="block sm:col-span-2">
                  <span className="mb-2 block text-sm font-medium text-gray-700">
                    Website
                  </span>
                  <input
                    type="url"
                    value={website}
                    onChange={(event) => setWebsite(event.target.value)}
                    className="w-full rounded-xl border border-gray-300 px-4 py-3 text-sm outline-none transition focus:border-black"
                  />
                </label>
              </section>

              <section className="grid gap-5 sm:grid-cols-2">
                <label className="block">
                  <span className="mb-2 block text-sm font-medium text-gray-700">
                    Twitter
                  </span>
                  <input
                    type="text"
                    value={twitter}
                    onChange={(event) => setTwitter(event.target.value)}
                    className="w-full rounded-xl border border-gray-300 px-4 py-3 text-sm outline-none transition focus:border-black"
                  />
                </label>
                <label className="block">
                  <span className="mb-2 block text-sm font-medium text-gray-700">
                    Instagram
                  </span>
                  <input
                    type="text"
                    value={instagram}
                    onChange={(event) => setInstagram(event.target.value)}
                    className="w-full rounded-xl border border-gray-300 px-4 py-3 text-sm outline-none transition focus:border-black"
                  />
                </label>
                <label className="block">
                  <span className="mb-2 block text-sm font-medium text-gray-700">
                    Facebook
                  </span>
                  <input
                    type="text"
                    value={facebook}
                    onChange={(event) => setFacebook(event.target.value)}
                    className="w-full rounded-xl border border-gray-300 px-4 py-3 text-sm outline-none transition focus:border-black"
                  />
                </label>
                <label className="block">
                  <span className="mb-2 block text-sm font-medium text-gray-700">
                    LinkedIn
                  </span>
                  <input
                    type="text"
                    value={linkedin}
                    onChange={(event) => setLinkedin(event.target.value)}
                    className="w-full rounded-xl border border-gray-300 px-4 py-3 text-sm outline-none transition focus:border-black"
                  />
                </label>
                <label className="block sm:col-span-2">
                  <span className="mb-2 block text-sm font-medium text-gray-700">
                    Interests
                  </span>
                  <input
                    type="text"
                    value={interestsInput}
                    onChange={(event) => setInterestsInput(event.target.value)}
                    placeholder="Music, Technology, Sports"
                    className="w-full rounded-xl border border-gray-300 px-4 py-3 text-sm outline-none transition focus:border-black"
                  />
                </label>
              </section>

              {error ? (
                <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                  {error}
                </div>
              ) : null}

              <div className="flex flex-wrap gap-3">
                <button
                  type="submit"
                  disabled={submitting}
                  className="inline-flex items-center justify-center rounded-xl bg-black px-5 py-3 text-sm font-medium text-white transition hover:bg-gray-800 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {submitting ? "Creating account..." : "Create Account"}
                </button>
                <a
                  href="/logout"
                  className="inline-flex items-center justify-center rounded-xl border border-gray-300 px-5 py-3 text-sm font-medium text-gray-700 transition hover:border-black hover:text-black"
                >
                  Start Over
                </a>
              </div>
            </form>
          )}
        </div>
      </main>
    </div>
  );
}
