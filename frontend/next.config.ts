import type { NextConfig } from "next";

const isStaticExport = process.env.NEXT_PUBLIC_STATIC_MODE === "true";
const basePath = process.env.NEXT_PUBLIC_BASE_PATH || "";

const nextConfig: NextConfig = {
  /* config options here */
  devIndicators: false,
  ...(isStaticExport
    ? {
        output: "export",
        images: { unoptimized: true },
        ...(basePath ? { basePath, assetPrefix: `${basePath}/` } : {}),
      }
    : {
        cacheComponents: true,
        partialPrefetching: true,
      }),
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
