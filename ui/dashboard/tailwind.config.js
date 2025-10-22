/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        primary: {
          50: "#f0f7ff",
          100: "#d9e9ff",
          200: "#b0d4ff",
          300: "#81baff",
          400: "#4d98ff",
          500: "#1f75ff",
          600: "#0f5ee6",
          700: "#0b4cc0",
          800: "#0d3f9b",
          900: "#0f357d",
        },
        compliance: {
          safe: "#1f8a70",
          warn: "#f2c14e",
          block: "#f78154",
        },
      },
    },
  },
  plugins: [],
}
