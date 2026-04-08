export function withNext(path: string, nextPath: string): string {
  const [pathWithoutHash, hash = ""] = path.split("#", 2);
  const [pathname, query = ""] = pathWithoutHash.split("?", 2);
  const params = new URLSearchParams(query);

  params.set("next", nextPath);

  const nextQuery = params.toString();
  const hashSuffix = hash ? `#${hash}` : "";

  return `${pathname}${nextQuery ? `?${nextQuery}` : ""}${hashSuffix}`;
}
