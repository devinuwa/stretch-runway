import type { NextConfig } from "next";

/**
 * Telemetry is disabled via NEXT_TELEMETRY_DISABLED=1 (.env.local / .env.example
 * and documented for PowerShell in frontend/README.md). Next 16 has no
 * `telemetry` key in NextConfig — setting it there fails typecheck.
 */
const nextConfig: NextConfig = {};

export default nextConfig;
