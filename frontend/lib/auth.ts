"use client";

import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { ApiError, apiFetch } from "@/lib/api";
import { buildNextPath } from "@/lib/auth-redirect";

export interface AuthUser {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  name: string;
  roles: string[];
  picture: string | null;
}

interface AuthSessionResponse {
  user: AuthUser | null;
}

let currentUserPromise: Promise<AuthUser | null> | null = null;

export function clearCurrentUserCache(): void {
  currentUserPromise = null;
}

export async function getCurrentUser(): Promise<AuthUser | null> {
  if (currentUserPromise) {
    return currentUserPromise;
  }

  currentUserPromise = apiFetch<AuthSessionResponse>("/auth/session", {
    cache: "no-store",
  })
    .then((session) => session.user ?? null)
    .catch((error) => {
      if (error instanceof ApiError && error.status === 401) {
        return null;
      }
      throw error;
    })
    .finally(() => {
      currentUserPromise = null;
    });

  return currentUserPromise;
}

export function useAuth(): {
  user: AuthUser | null;
  loading: boolean;
  error: string | null;
} {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    void getCurrentUser()
      .then((nextUser) => {
        if (!cancelled) {
          setUser(nextUser);
          setError(null);
        }
      })
      .catch((nextError) => {
        if (!cancelled) {
          setUser(null);
          setError(
            nextError instanceof Error
              ? nextError.message
              : "Failed to load the current session.",
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

  return { user, loading, error };
}

export function useRequireAuth(): {
  user: AuthUser | null;
  loading: boolean;
  error: string | null;
} {
  const pathname = usePathname();
  const auth = useAuth();

  useEffect(() => {
    if (!auth.loading && !auth.user) {
      const params = new URLSearchParams();
      const search = window.location.search;
      const nextPath = buildNextPath(
        pathname,
        search,
        window.location.hash,
      );
      params.set("next", nextPath);
      window.location.replace(`/signin?${params.toString()}`);
    }
  }, [auth.loading, auth.user, pathname]);

  return auth;
}
