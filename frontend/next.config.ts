import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  images: {
    // User-provided image URLs are arbitrary; disable server-side optimisation
    // for those images (via the `unoptimized` prop at the call-site) so
    // Next.js never fetches untrusted remote URLs on the server.
    unoptimized: true,
  },
};

export default nextConfig;
