const EXPLICIT_TIMEZONE_RE = /(Z|[+-]\d{2}:\d{2})$/;

export function parseApiDate(iso: string): Date {
  if (EXPLICIT_TIMEZONE_RE.test(iso)) {
    return new Date(iso);
  }

  const match = iso.match(
    /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2})(?:\.\d+)?)?$/,
  );
  if (!match) {
    return new Date(iso);
  }

  const [, year, month, day, hour, minute, second = "0"] = match;
  return new Date(
    Date.UTC(
      Number(year),
      Number(month) - 1,
      Number(day),
      Number(hour),
      Number(minute),
      Number(second),
    ),
  );
}
