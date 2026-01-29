/** @type {import('tailwindcss').Config} */
const shared = require("../tldw-frontend/tailwind.config.js")

module.exports = {
  ...shared,
  content: [
    "../packages/ui/src/**/*.{ts,tsx,html}",
    "./**/*.{ts,tsx,html}"
  ]
}
