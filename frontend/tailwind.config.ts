import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#0b0d10",
        panel: "#13171c",
        line: "#1f262e",
        muted: "#6b7785",
      },
    },
  },
  plugins: [],
};
export default config;
