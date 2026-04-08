export function withNext(path: string, nextPath: string): string {
  return `${path}?next=${encodeURIComponent(nextPath)}`;
}
