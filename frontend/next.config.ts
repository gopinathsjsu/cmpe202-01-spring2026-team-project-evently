import type { NextConfig } from "next";

/**
 * Proxies browser/RSC requests from same-origin `/api/*` to the real backend (e.g. HTTP ALB),
 * avoiding mixed-content when the site is served over HTTPS (Amplify).
 *
 * Set `BACKEND_PROXY_TARGET` at build time (Amplify env). No trailing slash.
 */
function backendProxyTarget(): string | undefined {
  const raw = process.env.BACKEND_PROXY_TARGET?.trim();
  return raw ? raw.replace(/\/$/, "") : undefined;
}

const nextConfig: NextConfig = {
  images: {
    // User-provided image URLs are arbitrary; disable server-side optimization
    // so Next.js never fetches untrusted remote URLs on the server (SSRF).
    unoptimized: true,
  },
  async rewrites() {
    const target = backendProxyTarget();
    if (!target) {
      return [];
    }
    return [{ source: "/api/:path*", destination: `${target}/:path*` }];
  },
};

export default nextConfig;
