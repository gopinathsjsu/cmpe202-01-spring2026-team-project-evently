export function buildNextPath(
  pathname: string | null,
  search: string,
  hash: string,
): string {
  const basePath = pathname || "/";
  return `${basePath}${search}${hash}`;
}
