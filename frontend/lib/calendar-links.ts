export function buildEventUrl(origin: string, eventId: number): string {
  return new URL(`/events/${eventId}`, origin).toString();
}
