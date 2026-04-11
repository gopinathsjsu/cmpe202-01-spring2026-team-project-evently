"use client";

import Link from "next/link";
import { ReactNode, useState } from "react";

import { useAuth } from "@/lib/auth";

interface AuthRequiredActionProps {
  actionLabel: string;
  authenticatedHref?: string;
  className: string;
  children: ReactNode;
  nextPath: string;
  onAuthenticatedClick?: () => void;
  disabled?: boolean;
}

export function AuthRequiredAction({
  actionLabel,
  authenticatedHref,
  className,
  children,
  nextPath,
  onAuthenticatedClick,
  disabled = false,
}: AuthRequiredActionProps) {
  const { user, loading } = useAuth();
  const [open, setOpen] = useState(false);

  const signinHref = `/signin?next=${encodeURIComponent(nextPath)}`;
  const signupHref = `/signup?next=${encodeURIComponent(nextPath)}`;

  if (user && authenticatedHref) {
    return (
      <Link href={authenticatedHref} className={className}>
        {children}
      </Link>
    );
  }

  if (user && onAuthenticatedClick) {
    return (
      <button
        type="button"
        onClick={onAuthenticatedClick}
        disabled={disabled}
        className={className}
      >
        {children}
      </button>
    );
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        disabled={disabled || loading}
        className={className}
      >
        {children}
      </button>

      {open ? (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 px-4">
          <div className="w-full max-w-md rounded-3xl bg-white p-6 shadow-2xl">
            <h2 className="text-xl font-semibold text-black">Sign in required</h2>
            <p className="mt-3 text-sm text-gray-600">
              You need an account to {actionLabel}. Sign in if you already have
              one, or create an account to continue.
            </p>
            <div className="mt-6 grid gap-3 sm:grid-cols-2">
              <a
                href={signinHref}
                className="inline-flex items-center justify-center rounded-xl border border-gray-300 px-4 py-3 text-sm font-medium text-gray-700 transition hover:border-black hover:text-black"
              >
                Sign In
              </a>
              <a
                href={signupHref}
                className="inline-flex items-center justify-center rounded-xl bg-black px-4 py-3 text-sm font-medium text-white transition hover:bg-gray-800"
              >
                Sign Up
              </a>
            </div>
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="mt-4 w-full rounded-xl px-4 py-3 text-sm font-medium text-gray-500 transition hover:bg-gray-50 hover:text-black"
            >
              Maybe later
            </button>
          </div>
        </div>
      ) : null}
    </>
  );
}
