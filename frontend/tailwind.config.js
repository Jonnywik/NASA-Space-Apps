/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "var(--background)",
        foreground: "var(--foreground)",
        primary: "var(--primary)",
        "primary-strong": "var(--primary-strong)",
        "primary-soft": "var(--primary-soft)",
        ground: "var(--ground)",
        surface: "var(--surface)",
        ink: "var(--ink)",
        muted: "var(--muted)",
        line: "var(--line)",
        "line-strong": "var(--line-strong)",
        "demo-bg": "var(--demo-bg)",
        "demo-ink": "var(--demo-ink)",
        "water-1": "var(--water-1)",
        "water-2": "var(--water-2)",
        "water-3": "var(--water-3)",
        "water-4": "var(--water-4)",
        veg: "var(--veg)",
        "perm-water": "var(--perm-water)",
        "motion-away": "var(--motion-away-3)",
        "motion-toward": "var(--motion-toward-2)",
        scenario: "var(--scenario-stroke)",
      },
      fontFamily: {
        sans: ["var(--font-sans)", "Inter", "system-ui", "sans-serif"],
        serif: ["var(--font-serif)", "Source Serif 4", "Georgia", "serif"],
      },
    },
  },
  plugins: [],
};
