"use client";

import { useAuth } from "@/lib/auth";

export function AuthNav() {
  const { user, loading } = useAuth();
  const isAdmin = user?.roles.includes("admin") ?? false;

  if (loading) {
    return (
      <div className="flex items-center gap-4">
        <span className="text-sm text-gray-500">Checking session...</span>
      </div>
    );
  }

  if (user) {
    return (
      <div className="flex items-center gap-4">
        {isAdmin && (
          <a
            href="/admin/events"
            className="rounded-md border border-black px-4 py-2 text-sm font-medium text-black hover:bg-gray-50"
          >
            Admin Queue
          </a>
        )}
        <span className="hidden text-sm text-gray-700 sm:inline">
          {user.first_name || user.name}
        </span>
        <a
          href="/logout"
          className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:border-black hover:text-black"
        >
          Sign Out
        </a>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-4">
      <a href="/signin" className="text-sm font-medium text-gray-700 hover:text-black">
        Sign In
      </a>
      <a
        href="/signup"
        className="rounded-md bg-black px-4 py-2 text-sm font-medium text-white hover:bg-gray-800"
      >
        Sign Up
      </a>
    </div>
  );
}
