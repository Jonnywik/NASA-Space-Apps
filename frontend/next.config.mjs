/** @type {import('next').NextConfig} */
const fx = process.env.NEXT_PUBLIC_USE_FIXTURES;
const nextConfig = {
  // Always define the fixtures flag at build time so that, when it is off, the fixture module is dropped
  // from the bundle (see utils/api.js and utils/devFixtures.js).
  //   1      every v5.1 endpoint is answered by synthetic fixtures (no backend needed)
  //   nisar  only the NISAR and camanava_2026 ground-motion endpoints are fixtures; climate and places are real
  env: {
    NEXT_PUBLIC_USE_FIXTURES: fx === "1" || fx === "nisar" ? fx : "0",
  },
  // Hosting (deploy/): TANAW_STATIC_EXPORT=1 builds plain static files into frontend/out, served by the backend.
  ...(process.env.TANAW_STATIC_EXPORT === "1" ? { output: "export" } : {}),
};

export default nextConfig;
