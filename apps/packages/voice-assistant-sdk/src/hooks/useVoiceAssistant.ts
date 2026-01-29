/**
 * useVoiceAssistant
 *
 * React hook for voice assistant integration.
 * Provides a complete voice assistant experience with audio capture and playback.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { VoiceAssistantClient } from '../client/VoiceAssistantClient';
import { AudioCapture } from '../audio/AudioCapture';
import { AudioPlayer } from '../audio/AudioPlayer';
import type {
  VoiceAssistantConfig,
  VoiceAssistantState,
  WSTranscriptionMessage,
  WSIntentMessage,
  WSActionResultMessage,
  WSErrorMessage,
  WSTTSChunkMessage,
  WSTTSEndMessage,
} from '../types';

export interface UseVoiceAssistantOptions extends Omit<VoiceAssistantConfig, 'wsUrl' | 'token'> {
  /** WebSocket URL for the voice assistant endpoint */
  wsUrl: string;
  /** Authentication token */
  token: string;
  /** Auto-connect on mount (default: false) */
  autoConnect?: boolean;
  /** Auto-play TTS responses (default: true) */
  autoPlayTTS?: boolean;
}

export interface UseVoiceAssistantReturn {
  // Connection state
  isConnected: boolean;
  isConnecting: boolean;
  sessionId: string | null;
  userId: number | null;

  // Voice state
  state: VoiceAssistantState;
  isListening: boolean;
  isProcessing: boolean;
  isSpeaking: boolean;

  // Audio levels
  audioLevel: number;

  // Results
  transcription: string | null;
  intent: WSIntentMessage | null;
  actionResult: WSActionResultMessage | null;
  error: WSErrorMessage | null;

  // Conversation history
  history: Array<{
    role: 'user' | 'assistant';
    content: string;
    timestamp: Date;
  }>;

  // Actions
  connect: () => Promise<void>;
  disconnect: () => void;
  startListening: () => Promise<void>;
  stopListening: () => void;
  sendText: (text: string) => void;
  cancel: () => void;
  clearHistory: () => void;

  // TTS controls
  stopTTS: () => void;
  setTTSVolume: (volume: number) => void;
}

export function useVoiceAssistant(options: UseVoiceAssistantOptions): UseVoiceAssistantReturn {
  const {
    wsUrl,
    token,
    autoConnect = false,
    autoPlayTTS = true,
    ...clientOptions
  } = options;

  // Refs
  const clientRef = useRef<VoiceAssistantClient | null>(null);
  const captureRef = useRef<AudioCapture | null>(null);
  const playerRef = useRef<AudioPlayer | null>(null);

  // Connection state
  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [userId, setUserId] = useState<number | null>(null);

  // Voice state
  const [state, setState] = useState<VoiceAssistantState>('idle' as VoiceAssistantState);
  const [isListening, setIsListening] = useState(false);

  // Audio level
  const [audioLevel, setAudioLevel] = useState(0);

  // Results
  const [transcription, setTranscription] = useState<string | null>(null);
  const [intent, setIntent] = useState<WSIntentMessage | null>(null);
  const [actionResult, setActionResult] = useState<WSActionResultMessage | null>(null);
  const [error, setError] = useState<WSErrorMessage | null>(null);

  // Conversation history
  const [history, setHistory] = useState<Array<{
    role: 'user' | 'assistant';
    content: string;
    timestamp: Date;
  }>>([]);

  // Derived state
  const isProcessing = state === ('processing' as VoiceAssistantState);
  const isSpeaking = state === ('speaking' as VoiceAssistantState);

  // Initialize client
  useEffect(() => {
    const client = new VoiceAssistantClient({
      wsUrl,
      token,
      ...clientOptions,
    });

    const capture = new AudioCapture({
      sampleRate: clientOptions.sampleRate ?? 16000,
    });

    const player = new AudioPlayer();

    // Client event handlers
    client.on('connected', () => {
      setIsConnected(true);
      setIsConnecting(false);
    });

    client.on('disconnected', () => {
      setIsConnected(false);
      setIsConnecting(false);
    });

    client.on('authenticated', (data) => {
      setSessionId(data.session_id);
      setUserId(data.user_id);
    });

    client.on('stateChange', (newState) => {
      setState(newState);
    });

    client.on('transcription', (data: WSTranscriptionMessage) => {
      setTranscription(data.text);
      if (data.is_final && data.text) {
        setHistory((prev) => [
          ...prev,
          { role: 'user', content: data.text, timestamp: new Date() },
        ]);
      }
    });

    client.on('intent', (data: WSIntentMessage) => {
      setIntent(data);
    });

    client.on('actionResult', (data: WSActionResultMessage) => {
      setActionResult(data);
      if (data.response_text) {
        setHistory((prev) => [
          ...prev,
          { role: 'assistant', content: data.response_text, timestamp: new Date() },
        ]);
      }
    });

    client.on('ttsChunk', (data: WSTTSChunkMessage) => {
      if (autoPlayTTS) {
        player.addChunk(data.data, data.sequence, data.format);
      }
    });

    client.on('ttsEnd', (_data: WSTTSEndMessage) => {
      // TTS playback will continue until audio queue is empty
    });

    client.on('error', (data: WSErrorMessage) => {
      setError(data);
    });

    // Audio capture handlers
    capture.on('data', (audioData) => {
      if (client.isConnected()) {
        client.sendAudio(audioData);
      }
    });

    capture.on('level', (level) => {
      setAudioLevel(level);
    });

    capture.on('stop', () => {
      setIsListening(false);
      if (client.isConnected()) {
        client.commit();
      }
    });

    clientRef.current = client;
    captureRef.current = capture;
    playerRef.current = player;

    // Auto-connect if enabled
    if (autoConnect) {
      setIsConnecting(true);
      client.connect().catch(() => {
        setIsConnecting(false);
      });
    }

    // Cleanup
    return () => {
      capture.stop();
      player.stop();
      client.disconnect();
    };
  }, [wsUrl, token]); // Only recreate on URL/token change

  // Actions
  const connect = useCallback(async () => {
    if (!clientRef.current || isConnected || isConnecting) {
      return;
    }

    setIsConnecting(true);
    setError(null);

    try {
      await clientRef.current.connect();
    } catch (err) {
      setIsConnecting(false);
      throw err;
    }
  }, [isConnected, isConnecting]);

  const disconnect = useCallback(() => {
    captureRef.current?.stop();
    playerRef.current?.stop();
    clientRef.current?.disconnect();
    setIsListening(false);
  }, []);

  const startListening = useCallback(async () => {
    if (!captureRef.current || isListening) {
      return;
    }

    setError(null);
    setTranscription(null);
    setIntent(null);
    setActionResult(null);

    await captureRef.current.start();
    setIsListening(true);
  }, [isListening]);

  const stopListening = useCallback(() => {
    captureRef.current?.stop();
  }, []);

  const sendText = useCallback((text: string) => {
    if (!clientRef.current?.isConnected()) {
      return;
    }

    setError(null);
    setTranscription(text);
    setIntent(null);
    setActionResult(null);

    clientRef.current.sendText(text);

    setHistory((prev) => [
      ...prev,
      { role: 'user', content: text, timestamp: new Date() },
    ]);
  }, []);

  const cancel = useCallback(() => {
    captureRef.current?.stop();
    playerRef.current?.stop();
    clientRef.current?.cancel();
    setIsListening(false);
  }, []);

  const clearHistory = useCallback(() => {
    setHistory([]);
  }, []);

  const stopTTS = useCallback(() => {
    playerRef.current?.stop();
  }, []);

  const setTTSVolume = useCallback((volume: number) => {
    playerRef.current?.setVolume(volume);
  }, []);

  return {
    // Connection state
    isConnected,
    isConnecting,
    sessionId,
    userId,

    // Voice state
    state,
    isListening,
    isProcessing,
    isSpeaking,

    // Audio levels
    audioLevel,

    // Results
    transcription,
    intent,
    actionResult,
    error,

    // Conversation history
    history,

    // Actions
    connect,
    disconnect,
    startListening,
    stopListening,
    sendText,
    cancel,
    clearHistory,

    // TTS controls
    stopTTS,
    setTTSVolume,
  };
}
