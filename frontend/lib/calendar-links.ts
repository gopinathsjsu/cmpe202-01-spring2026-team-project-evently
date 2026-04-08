export function buildEventUrl(origin: string, eventId: number): string {
  return new URL(`/events/${eventId}`, origin).toString();
}

export function shouldShowAddToCalendar(
  isOrganizer: boolean,
  status: "going" | "checked_in" | "cancelled" | null,
): boolean {
  return isOrganizer || status === "going" || status === "checked_in";
}
