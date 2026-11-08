import type { NextConfig } from "next";

// NEXT_PUBLIC_ variables are inlined at build time; without this one every
// request would go to "undefined/api/...".
if (!process.env.NEXT_PUBLIC_SERVER_URL) {
  throw new Error(
    "NEXT_PUBLIC_SERVER_URL is not set. Add the backend URL to frontend/.env (see README.md).",
  );
}

const nextConfig: NextConfig = {};

export default nextConfig;
