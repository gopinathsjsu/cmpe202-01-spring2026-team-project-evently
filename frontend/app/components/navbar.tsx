"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { AuthRequiredAction } from "@/components/auth-required-action";
import { useAuth } from "@/lib/auth";
import { withNext } from "@/lib/path-with-next";

function SearchIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="m21 21-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
    </svg>
  );
}

export default function Navbar() {
  const pathname = usePathname();
  const { user, loading } = useAuth();
  const isAdmin = user?.roles.includes("admin") ?? false;
  const nextPath = pathname || "/";

  return (
    <header className="sticky top-0 z-50 border-b border-gray-200 bg-white">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-6 px-4 sm:px-6 lg:px-8">
        <div className="flex items-center gap-8">
          <Link href="/" className="flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded bg-black text-white text-sm font-bold">
              E
            </span>
            <span className="text-lg font-semibold">Evently</span>
          </Link>
          <nav className="hidden items-center gap-6 md:flex">
            <AuthRequiredAction
              actionLabel="create an event"
              authenticatedHref="/create"
              nextPath="/create"
              className={`text-sm font-medium ${pathname === "/create" ? "text-black" : "text-gray-700 hover:text-black"}`}
            >
              Create Event
            </AuthRequiredAction>
            {user ? (
              <Link
                href="/calendar"
                className={`text-sm font-medium ${pathname === "/calendar" ? "text-black" : "text-gray-700 hover:text-black"}`}
              >
                My Calendar
              </Link>
            ) : null}
          </nav>
        </div>
        <div className="flex flex-1 items-center justify-center max-w-md px-4">
          <div className="relative w-full">
            <SearchIcon className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
            <input
              type="search"
              placeholder="Search events..."
              className="w-full rounded-md border border-gray-300 bg-gray-50 py-2 pl-9 pr-4 text-sm placeholder:text-gray-500 focus:border-black focus:outline-none focus:ring-1 focus:ring-black"
            />
          </div>
        </div>
        <div className="flex items-center gap-4">
          {loading ? (
            <span className="text-sm text-gray-500">Checking session...</span>
          ) : user ? (
            <>
              {isAdmin && (
                <Link
                  href="/admin/events"
                  className="rounded-md border border-black px-4 py-2 text-sm font-medium text-black hover:bg-gray-50"
                >
                  Admin Queue
                </Link>
              )}
              <span className="hidden text-sm text-gray-700 sm:inline">
                {user.first_name || user.name}
              </span>
              <Link
                href="/logout"
                className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:border-black hover:text-black"
              >
                Sign Out
              </Link>
            </>
          ) : (
            <>
              <Link href={withNext("/signin", nextPath)} className="text-sm font-medium text-gray-700 hover:text-black">
                Sign In
              </Link>
              <Link href={withNext("/signup", nextPath)} className="rounded-md bg-black px-4 py-2 text-sm font-medium text-white hover:bg-gray-800">
                Sign Up
              </Link>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
