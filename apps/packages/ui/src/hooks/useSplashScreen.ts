import { useCallback, useState } from "react";
import { randomSplashCard } from "../data/splash-cards";
import { randomSplashMessage } from "../data/splash-messages";
import type { SplashCard } from "../components/Common/SplashScreen/engine/types";
import { useSetting } from "@/hooks/useSetting";
import {
  SPLASH_DISABLED_SETTING,
  SPLASH_ENABLED_CARD_NAMES_SETTING,
  SPLASH_DURATION_SECONDS_MAX,
  SPLASH_DURATION_SECONDS_MIN,
  SPLASH_DURATION_SECONDS_SETTING
} from "@/services/settings/ui-settings";

interface SplashScreenState {
  /** Whether to show the splash overlay right now. */
  visible: boolean;
  /** The selected card for this session. */
  card: SplashCard | null;
  /** Random loading message. */
  message: string;
  /** Dismiss the splash (click / keypress / timeout). */
  dismiss: () => void;
  /** Trigger a fresh random splash (used after successful login action). */
  show: (options?: { force?: boolean }) => void;
  /** Whether splashes are disabled in user prefs. */
  disabled: boolean;
  /** Toggle splash preference. */
  setDisabled: (v: boolean) => void;
}

/**
 * Manages splash screen state.
 * Splash is event-driven and shown only when `show()` is called.
 */
export function useSplashScreen(): SplashScreenState {
  const [visible, setVisible] = useState(false);
  const [card, setCard] = useState<SplashCard | null>(null);
  const [message, setMessage] = useState("");
  const [disabled, setDisabledPreference] = useSetting(SPLASH_DISABLED_SETTING);
  const [enabledCardNames] = useSetting(SPLASH_ENABLED_CARD_NAMES_SETTING);
  const [durationSeconds] = useSetting(SPLASH_DURATION_SECONDS_SETTING);

  const resolveDurationSeconds = useCallback(() => {
    const fallback = durationSeconds;
    if (typeof window === "undefined") return fallback;
    const localStorageKey = SPLASH_DURATION_SECONDS_SETTING.localStorageKey;
    if (!localStorageKey) return fallback;
    try {
      const raw = window.localStorage.getItem(localStorageKey);
      if (raw === null || raw === "") return fallback;
      const parsed = Math.round(Number(raw));
      if (!Number.isFinite(parsed)) return fallback;
      return Math.min(
        SPLASH_DURATION_SECONDS_MAX,
        Math.max(SPLASH_DURATION_SECONDS_MIN, parsed)
      );
    } catch {
      return fallback;
    }
  }, [durationSeconds]);

  const dismiss = useCallback(() => setVisible(false), []);

  const show = useCallback((options?: { force?: boolean }) => {
    if (disabled && !options?.force) return;
    const c = randomSplashCard({ enabledNames: enabledCardNames });
    const effectiveDurationSeconds = resolveDurationSeconds();
    setCard({
      ...c,
      duration: Math.round(effectiveDurationSeconds * 1000)
    });
    setMessage(c.subtitle || randomSplashMessage());
    setVisible(true);
  }, [disabled, enabledCardNames, resolveDurationSeconds]);

  const setDisabled = useCallback((v: boolean) => {
    if (v) {
      setVisible(false);
    }
    void setDisabledPreference(v);
  }, [setDisabledPreference]);

  return { visible, card, message, dismiss, show, disabled, setDisabled };
}
