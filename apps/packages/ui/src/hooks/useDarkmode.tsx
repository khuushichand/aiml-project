import React from "react";
import { createWithEqualityFn } from "zustand/traditional";
import { useSetting } from "@/hooks/useSetting";
import { THEME_SETTING } from "@/services/settings/ui-settings";

type DarkModeState = {
  mode: "system" | "dark" | "light";
  setMode: (mode: "system" | "dark" | "light") => void;
};

export const useDarkModeStore = createWithEqualityFn<DarkModeState>((set) => ({
  mode: "dark",
  setMode: (mode) => set({ mode }),
}));

const SYSTEM_THEME_MEDIA_QUERY = "(prefers-color-scheme: dark)";

const resolveThemeMode = (
  mode: DarkModeState["mode"]
): "dark" | "light" => {
  if (mode === "dark" || mode === "light") return mode;
  if (typeof window === "undefined") return "dark";
  return window.matchMedia(SYSTEM_THEME_MEDIA_QUERY).matches ? "dark" : "light";
};

export const useDarkMode = () => {
  const { mode, setMode } = useDarkModeStore();
  const [themePreference, setThemePreference] = useSetting(THEME_SETTING);

  const applyTheme = React.useCallback(
    (nextMode: "dark" | "light") => {
      if (typeof document === "undefined") return;
      document.documentElement.classList.remove("dark", "light");
      document.documentElement.classList.add(nextMode);
      setMode(nextMode);
    },
    [setMode]
  );

  React.useEffect(() => {
    if (typeof window === "undefined") return;
    const mediaQueryList = window.matchMedia(SYSTEM_THEME_MEDIA_QUERY);
    const applyResolvedTheme = () => {
      applyTheme(resolveThemeMode(themePreference));
    };

    applyResolvedTheme();

    if (themePreference !== "system") return;

    const onSystemThemeChange = () => applyResolvedTheme();
    if (typeof mediaQueryList.addEventListener === "function") {
      mediaQueryList.addEventListener("change", onSystemThemeChange);
      return () =>
        mediaQueryList.removeEventListener("change", onSystemThemeChange);
    }
    mediaQueryList.addListener(onSystemThemeChange);
    return () => mediaQueryList.removeListener(onSystemThemeChange);
  }, [applyTheme, themePreference]);

  const toggleDarkMode = () => {
    const newMode = mode === "dark" ? "light" : "dark";
    applyTheme(newMode);
    void setThemePreference(newMode);
  };

  return { mode, toggleDarkMode };
};
