import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  images: {
    // User-provided image URLs are arbitrary; disable server-side optimization
    // so Next.js never fetches untrusted remote URLs on the server (SSRF).
    unoptimized: true,
  },
};

export default nextConfig;
