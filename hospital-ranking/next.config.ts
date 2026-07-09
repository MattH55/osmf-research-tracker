import type { NextConfig } from "next";

/** Served at https://opensourcemed.info/hospital-ranking via Vercel path routing */
const basePath = "/hospital-ranking";

const nextConfig: NextConfig = {
  basePath,
  assetPrefix: basePath,
};

export default nextConfig;
