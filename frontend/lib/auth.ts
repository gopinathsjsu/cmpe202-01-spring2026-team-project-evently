// ==========================================================================
// AUTH MODULE — Single source of truth for authentication.
//
// Currently returns a hardcoded guest user so anyone can create events.
// When you implement real auth (e.g. NextAuth, Clerk, or a custom JWT
// flow), update ONLY this file:
//
//   1. getCurrentUser()  — read the session/token and return the real user
//      or null if not signed in.
//
//   2. useRequireAuth()  — redirect to the sign-in page when the user is
//      not authenticated instead of returning the guest fallback.
//
// Every page/component that needs the current user imports from here,
// so a single change propagates everywhere.
// ==========================================================================

"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

export interface AuthUser {
  id: number;
}

// TODO [auth]: Replace with real session lookup (cookie, JWT, context, etc.)
const GUEST_USER: AuthUser = { id: 1 };

/**
 * Return the currently signed-in user, or `null` if unauthenticated.
 *
 * TODO [auth]: Read the real session here. Example with NextAuth:
 *   const session = await getServerSession(authOptions);
 *   return session?.user ? { id: session.user.id } : null;
 */
export function getCurrentUser(): AuthUser | null {
  return GUEST_USER;
}

/**
 * Client-side hook that ensures the user is signed in.
 * Returns the authenticated user.
 *
 * TODO [auth]: When real auth is wired up, change the body to check the
 * session and call `router.replace("/signin")` when null.
 */
export function useRequireAuth(): AuthUser {
  const router = useRouter();
  const user = getCurrentUser();

  useEffect(() => {
    // TODO [auth]: Uncomment to enforce sign-in:
    // if (!user) router.replace("/signin");
  }, [user, router]);

  // Safe non-null assertion — currently always returns the guest user.
  // Once real auth is in place this will only be reached after the
  // redirect guard above passes.
  return user!;
}
