import { toBrowserSafeBackendUrl } from "@/lib/api-base";
import type { ActivityItem } from "@/lib/types";

export function resolvePhotoUrl(url: string | null | undefined): string | null {
  if (!url) return null;
  return toBrowserSafeBackendUrl(url);
}

export function initials(
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

export function formatProfileDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", {
    month: "long",
    day: "numeric",
    year: "numeric",
  });
}

export function activityLabel(action: ActivityItem["action"]): string {
  switch (action) {
    case "attended":
      return "Attended";
    case "created":
      return "Created";
    case "registered":
      return "Registered for";
  }
}
