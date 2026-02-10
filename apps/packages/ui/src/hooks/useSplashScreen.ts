import { useCallback, useEffect, useState } from "react";
import { randomSplashCard } from "../data/splash-cards";
import { randomSplashMessage } from "../data/splash-messages";
import type { SplashCard } from "../components/Common/SplashScreen/engine/types";

const STORAGE_KEY = "tldw_splash_disabled";

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
  show: () => void;
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
  const [disabled, setDisabledState] = useState(false);

  // Read preference from localStorage
  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored === "true") {
        setDisabledState(true);
      }
    } catch { /* localStorage unavailable */ }
  }, []);

  const dismiss = useCallback(() => setVisible(false), []);

  const show = useCallback(() => {
    if (disabled) return;
    const c = randomSplashCard();
    setCard(c);
    setMessage(c.subtitle || randomSplashMessage());
    setVisible(true);
  }, [disabled]);

  const setDisabled = useCallback((v: boolean) => {
    setDisabledState(v);
    if (v) {
      setVisible(false);
    }
    try { localStorage.setItem(STORAGE_KEY, String(v)); } catch { /* noop */ }
  }, []);

  return { visible, card, message, dismiss, show, disabled, setDisabled };
}
