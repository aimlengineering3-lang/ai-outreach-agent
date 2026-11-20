import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Text
        ink: { DEFAULT: "#0F1A2B", soft: "#46526A", mute: "#5F6B84" },
        // Surfaces
        page: "#ECEFF4",
        surface: "#FFFFFF",
        sunken: "#F5F7FA",
        line: { DEFAULT: "#D8DEE8", strong: "#BAC3D2" },
        rail: { DEFAULT: "#0F1A2B", hover: "#18263D", text: "#C5CDDB", mute: "#8592AA" },
        // Brand (same orange family as the old Streamlit dashboard,
        // darkened one step so white text on buttons passes contrast)
        accent: { DEFAULT: "#C8481F", dark: "#A63A15", bright: "#E85D2F", soft: "#FDEDE6" },
        // Status
        ok: { DEFAULT: "#1E7A45", soft: "#E3F3EA" },
        warn: { DEFAULT: "#9A5B00", soft: "#FFF1D0" },
        danger: { DEFAULT: "#B3321F", soft: "#FBE6E2" },
      },
      fontFamily: {
        sans: ["var(--font-ui)", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
      },
      borderRadius: {
        card: "12px",
      },
      boxShadow: {
        card: "0 1px 2px rgba(15, 26, 43, 0.05)",
        pop: "0 12px 32px rgba(15, 26, 43, 0.18)",
      },
    },
  },
  plugins: [],
};

export default config;
