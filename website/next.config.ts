import type { NextConfig } from "next";

// Static export: GitHub Pages serves the landing today, and the site has no server work to do.
const nextConfig: NextConfig = {
  output: "export",
  images: { unoptimized: true },
  reactStrictMode: true,
};

export default nextConfig;
