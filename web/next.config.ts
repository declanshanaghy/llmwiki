import type { NextConfig } from "next";
import path from "path";
import { withSentryConfig } from "@sentry/nextjs";

const nextConfig: NextConfig = {
  output: "standalone",
  outputFileTracingRoot: path.join(__dirname),
  env: {
    SUPABASE_INTERNAL_URL: process.env.SUPABASE_INTERNAL_URL || "",
  },
};

export default withSentryConfig(nextConfig, {
  silent: true,
  disableLogger: true,
});
