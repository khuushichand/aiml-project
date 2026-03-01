import { useEffect, useRef, useState } from 'react';

type UseMonitoringMessagesArgs = {
  successAutoClearMs?: number;
};

const DEFAULT_SUCCESS_AUTO_CLEAR_MS = 4000;

export const useMonitoringMessages = ({
  successAutoClearMs = DEFAULT_SUCCESS_AUTO_CLEAR_MS,
}: UseMonitoringMessagesArgs = {}) => {
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const successTimerRef = useRef<number | null>(null);

  useEffect(() => {
    if (!success) {
      if (successTimerRef.current !== null) {
        window.clearTimeout(successTimerRef.current);
        successTimerRef.current = null;
      }
      return;
    }

    if (successTimerRef.current !== null) {
      window.clearTimeout(successTimerRef.current);
    }
    successTimerRef.current = window.setTimeout(() => {
      setSuccess('');
      successTimerRef.current = null;
    }, successAutoClearMs);

    return () => {
      if (successTimerRef.current !== null) {
        window.clearTimeout(successTimerRef.current);
        successTimerRef.current = null;
      }
    };
  }, [success, successAutoClearMs]);

  return {
    error,
    setError,
    success,
    setSuccess,
  };
};
