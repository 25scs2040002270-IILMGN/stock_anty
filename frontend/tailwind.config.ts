import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/features/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        terminal: {
          bg: "#0B0E14",
          card: "#121721",
          border: "#1E2638",
          hover: "#1A2234",
          text: "#E2E8F0",
          muted: "#64748B",
          accent: "#38BDF8",
          up: "#10B981",
          down: "#EF4444",
          stale: "#F59E0B",
          offline: "#6B7280"
        }
      },
      fontFamily: {
        mono: ["JetBrains Mono", "Menlo", "Monaco", "Consolas", "Courier New", "monospace"]
      }
    },
  },
  plugins: [],
};
export default config;

