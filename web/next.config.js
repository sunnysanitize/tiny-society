/** @type {import('next').NextConfig} */
module.exports = {
  reactStrictMode: true,
  // Emit a self-contained server bundle for a small production Docker image.
  output: "standalone",
};
