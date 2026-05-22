import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink:     "#05050f",
        surface: "#0d0d1a",
        line:    "#00994d",
        muted:   "#4a5a8a",
      },
    },
  },
  plugins: [],
};
export default config;
