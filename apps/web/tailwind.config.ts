import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: ["./src/**/*.{ts,tsx}", "../../packages/shared/src/**/*.ts"],
  theme: {
    extend: {
      colors: {
        background: "#080A0E",
        foreground: "#F4F7FB",
        muted: "#8B97A7",
        border: "rgba(255,255,255,0.10)",
        surface: "rgba(255,255,255,0.065)",
        panel: "#11161E",
        profit: "#4ADE80",
        loss: "#FB7185",
        accent: "#38BDF8",
        amber: "#FBBF24"
      },
      fontFamily: {
        sans: ["var(--font-geist-sans)", "Inter", "system-ui", "sans-serif"]
      },
      boxShadow: {
        glow: "0 24px 80px rgba(56, 189, 248, 0.16)"
      }
    }
  },
  plugins: []
};

export default config;
