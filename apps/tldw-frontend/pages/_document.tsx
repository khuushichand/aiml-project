import { Html, Head, Main, NextScript } from "next/document";

const THEME_BOOTSTRAP_SCRIPT = `
(() => {
  try {
    const legacyTheme = window.localStorage.getItem("tldw-theme");
    const storedTheme = window.localStorage.getItem("theme") || legacyTheme;
    if (!window.localStorage.getItem("theme") && legacyTheme) {
      window.localStorage.setItem("theme", legacyTheme);
    }
    const prefersDark =
      typeof window.matchMedia === "function" &&
      window.matchMedia("(prefers-color-scheme: dark)").matches;
    const shouldUseDark =
      storedTheme === "dark" ||
      !storedTheme ||
      (storedTheme === "system" && prefersDark);
    if (shouldUseDark) {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
  } catch (_) {
    // Ignore storage/matchMedia failures and let runtime theme logic recover.
  }
})();
`;

export default function Document() {
  return (
    <Html lang="en">
      <Head>
        <script
          id="tldw-theme-bootstrap"
          dangerouslySetInnerHTML={{ __html: THEME_BOOTSTRAP_SCRIPT }}
        />
      </Head>
      <body className="antialiased arimo">
        <Main />
        <NextScript />
      </body>
    </Html>
  );
}
