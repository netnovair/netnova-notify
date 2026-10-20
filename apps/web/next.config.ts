import type { NextConfig } from "next";

const apiInternalUrl = process.env.API_INTERNAL_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  // Self-contained server output for the Docker image in infra/.
  output: "standalone",
  // Development previews are served through a proxy host (e.g. *.e2b.app).
  // This only affects `next dev`; production origins are unrestricted by this list.
  allowedDevOrigins: ["*.e2b.app", "localhost:3000", "127.0.0.1:3000"],
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: `${apiInternalUrl}/api/v1/:path*`,
      },
    ];
  },
  async headers() {
    return [
      {
        source: "/sw.js",
        headers: [
          { key: "Cache-Control", value: "no-cache, no-store, must-revalidate" },
          { key: "Service-Worker-Allowed", value: "/" },
        ],
      },
      {
        // The panel is an authenticated admin app: never let a proxy or the
        // browser serve a stale HTML document that points at old JS bundles.
        // Static assets under /_next/static stay immutable and cacheable.
        source: "/:path((?!_next/static|_next/image|icons|favicon).*)",
        headers: [{ key: "Cache-Control", value: "no-store, must-revalidate" }],
      },
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=(), payment=()",
          },
        ],
      },
    ];
  },
};

export default nextConfig;
