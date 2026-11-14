/** @type {import('next').NextConfig} */
const nextConfig = {
  // Always define the fixtures flag at build time so that, when it is off, the fixture module is dropped
  // from the bundle (see utils/api.js and utils/devFixtures.js).
  env: {
    NEXT_PUBLIC_USE_FIXTURES: process.env.NEXT_PUBLIC_USE_FIXTURES === "1" ? "1" : "0",
  },
};

export default nextConfig;
