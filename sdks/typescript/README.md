# tldw Voice Assistant TypeScript SDK

TypeScript/JavaScript SDK for the tldw Voice Assistant WebSocket API. Works in browsers, Node.js, Electron, and React Native.

## Installation

```bash
npm install @tldw/voice-assistant
# or
yarn add @tldw/voice-assistant
# or
pnpm add @tldw/voice-assistant
```

For Node.js environments, you'll also need the `ws` package:

```bash
npm install ws
```

## Quick Start

### Basic Text Commands

```typescript
import { VoiceAssistantClient } from '@tldw/voice-assistant';

const client = new VoiceAssistantClient({
  wsUrl: 'ws://localhost:8000/api/v1/voice/assistant',
  token: 'your-api-key',
});

client.onTranscription((result) => {
  console.log(`Transcription: ${result.text}`);
});

client.onActionResult((result) => {
  console.log(`Response: ${result.responseText}`);
});

client.onError((error) => {
  console.error(`Error: ${error.error}`);
});

await client.connect();
await client.sendText('search for machine learning');
```

### Browser with Microphone

```typescript
import {
  VoiceAssistantClient,
  AudioCapture,
  AudioPlayer,
  VoiceActivityDetector,
} from '@tldw/voice-assistant';

// Initialize client
const client = new VoiceAssistantClient({
  wsUrl: 'ws://localhost:8000/api/v1/voice/assistant',
  token: 'your-api-key',
  sttModel: 'parakeet',
  ttsProvider: 'kokoro',
  ttsVoice: 'af_heart',
});

// Audio player for TTS responses
const player = new AudioPlayer();

// Voice activity detection
const vad = new VoiceActivityDetector({
  threshold: 0.01,
  onSpeechStart: () => console.log('Listening...'),
  onSpeechEnd: () => {
    console.log('Processing...');
    client.commit();
  },
});

// Event handlers
client.onStateChange((state, prev) => {
  console.log(`State: ${prev} -> ${state}`);
});

client.onTranscription((result) => {
  if (result.isFinal) {
    console.log(`You said: ${result.text}`);
  }
});

client.onActionResult((result) => {
  console.log(`Assistant: ${result.responseText}`);
});

client.onTtsChunk((chunk) => player.queueChunk(chunk));
client.onTtsEnd(() => player.finalize());

// Microphone capture
const capture = new AudioCapture({
  sampleRate: 16000,
  onChunk: (data) => {
    vad.process(data);
    if (vad.isSpeaking) {
      client.sendAudio(data);
    }
  },
});

// Connect and start
async function start() {
  await client.connect();
  console.log('Connected!');

  // Note: Must be triggered by user interaction (button click)
  await capture.start();
  console.log('Listening for voice commands...');
}

// Stop
function stop() {
  capture.stop();
  player.close();
  client.disconnect();
}
```

### React Example

```tsx
import { useState, useEffect, useCallback } from 'react';
import {
  VoiceAssistantClient,
  AudioCapture,
  AudioPlayer,
  VoiceActivityDetector,
  VoiceAssistantState,
} from '@tldw/voice-assistant';

function VoiceAssistant() {
  const [client, setClient] = useState<VoiceAssistantClient | null>(null);
  const [capture, setCapture] = useState<AudioCapture | null>(null);
  const [state, setState] = useState<VoiceAssistantState>(VoiceAssistantState.IDLE);
  const [transcript, setTranscript] = useState('');
  const [response, setResponse] = useState('');

  useEffect(() => {
    const newClient = new VoiceAssistantClient({
      wsUrl: import.meta.env.VITE_VOICE_WS_URL,
      token: import.meta.env.VITE_API_TOKEN,
    });

    const player = new AudioPlayer();

    newClient.onStateChange(setState);
    newClient.onTranscription((r) => r.isFinal && setTranscript(r.text));
    newClient.onActionResult((r) => setResponse(r.responseText));
    newClient.onTtsChunk((c) => player.queueChunk(c));
    newClient.onTtsEnd(() => player.finalize());

    setClient(newClient);

    return () => {
      newClient.disconnect();
      player.close();
    };
  }, []);

  const startListening = useCallback(async () => {
    if (!client) return;

    await client.connect();

    const vad = new VoiceActivityDetector({
      onSpeechEnd: () => client.commit(),
    });

    const newCapture = new AudioCapture({
      sampleRate: 16000,
      onChunk: (data) => {
        vad.process(data);
        if (vad.isSpeaking) {
          client.sendAudio(data);
        }
      },
    });

    await newCapture.start();
    setCapture(newCapture);
  }, [client]);

  const stopListening = useCallback(() => {
    capture?.stop();
    setCapture(null);
  }, [capture]);

  return (
    <div>
      <div>State: {state}</div>
      <div>You said: {transcript}</div>
      <div>Assistant: {response}</div>
      <button onClick={capture ? stopListening : startListening}>
        {capture ? 'Stop' : 'Start'} Listening
      </button>
    </div>
  );
}
```

## API Reference

### VoiceAssistantClient

Main WebSocket client for communicating with the voice assistant.

#### Constructor Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `wsUrl` | `string` | *required* | WebSocket URL |
| `token` | `string` | *required* | JWT or API key |
| `sttModel` | `string` | `'parakeet'` | STT model |
| `sttLanguage` | `string` | `''` | Language code |
| `ttsProvider` | `string` | `'kokoro'` | TTS provider |
| `ttsVoice` | `string` | `'af_heart'` | TTS voice |
| `ttsFormat` | `AudioFormat` | `'mp3'` | TTS format |
| `sampleRate` | `number` | `16000` | Audio sample rate |
| `sessionId` | `string` | `''` | Resume session |
| `autoReconnect` | `boolean` | `true` | Auto-reconnect |
| `maxReconnectAttempts` | `number` | `5` | Max reconnect tries |
| `reconnectDelay` | `number` | `1.0` | Initial delay (s) |
| `debug` | `boolean` | `false` | Debug logging |

#### Methods

| Method | Description |
|--------|-------------|
| `connect()` | Connect to the server |
| `disconnect()` | Disconnect |
| `sendAudio(data)` | Send audio chunk |
| `commit()` | Signal end of utterance |
| `cancel()` | Cancel current operation |
| `sendText(text)` | Send text command |
| `subscribeToWorkflow(runId)` | Subscribe to workflow |
| `cancelWorkflow(runId)` | Cancel workflow |

#### Events

| Event | Callback Signature |
|-------|-------------------|
| `onConnected` | `() => void` |
| `onDisconnected` | `(reason: string) => void` |
| `onTranscription` | `(result: TranscriptionResult) => void` |
| `onIntent` | `(result: IntentResult) => void` |
| `onActionResult` | `(result: ActionResult) => void` |
| `onTtsChunk` | `(chunk: TTSChunk) => void` |
| `onTtsEnd` | `() => void` |
| `onStateChange` | `(state, prev?) => void` |
| `onError` | `(error: VoiceError) => void` |
| `onWorkflowProgress` | `(progress: WorkflowProgress) => void` |
| `onWorkflowComplete` | `(complete: WorkflowComplete) => void` |

### AudioCapture

Captures audio from the microphone using Web Audio API.

```typescript
const capture = new AudioCapture({
  sampleRate: 16000,      // Hz
  chunkSize: 4096,        // samples per chunk
  channels: 1,            // mono
  noiseSuppression: true,
  echoCancellation: true,
  autoGainControl: true,
  onChunk: (data: Float32Array) => {
    // Handle audio chunk
  },
});

await capture.start();
// ...
capture.stop();
```

### AudioPlayer

Plays TTS audio responses.

```typescript
const player = new AudioPlayer({ volume: 1.0 });

client.onTtsChunk((chunk) => player.queueChunk(chunk));
client.onTtsEnd(() => player.finalize());

// Control volume
player.volume = 0.5;

// Stop playback
player.stop();

// Cleanup
player.close();
```

### VoiceActivityDetector

Simple energy-based VAD for detecting speech.

```typescript
const vad = new VoiceActivityDetector({
  threshold: 0.01,     // Energy threshold
  silenceDelay: 30,    // Frames of silence before end
  speechPadding: 3,    // Frames of speech before start
  onSpeechStart: () => console.log('Speaking...'),
  onSpeechEnd: () => client.commit(),
});

// Process each audio chunk
capture.onChunk = (data) => {
  const hasSpeech = vad.process(data);
  if (vad.isSpeaking) {
    client.sendAudio(data);
  }
};
```

## Types

### Enums

- `VoiceAssistantState`: `IDLE`, `LISTENING`, `PROCESSING`, `SPEAKING`, `AWAITING_CONFIRMATION`, `ERROR`
- `VoiceActionType`: `MCP_TOOL`, `WORKFLOW`, `CUSTOM`, `LLM_CHAT`
- `AudioFormat`: `'mp3'`, `'opus'`, `'wav'`, `'pcm'`

### Result Types

```typescript
interface TranscriptionResult {
  text: string;
  isFinal: boolean;
  confidence?: number;
}

interface IntentResult {
  actionType: VoiceActionType;
  commandName?: string;
  entities: Record<string, unknown>;
  confidence: number;
  requiresConfirmation: boolean;
}

interface ActionResult {
  success: boolean;
  actionType: VoiceActionType;
  responseText: string;
  resultData?: Record<string, unknown>;
  executionTimeMs: number;
}

interface VoiceError {
  error: string;
  code?: string;
  recoverable: boolean;
}
```

## Node.js Usage

For Node.js, ensure the `ws` package is installed:

```typescript
import { VoiceAssistantClient } from '@tldw/voice-assistant';
// WebSocket will be automatically polyfilled from 'ws' package

const client = new VoiceAssistantClient({
  wsUrl: 'ws://localhost:8000/api/v1/voice/assistant',
  token: process.env.TLDW_API_KEY,
});

await client.connect();
await client.sendText('what is the weather?');
```

## React Native

For React Native, you may need to polyfill WebSocket depending on your setup. The SDK uses the standard WebSocket API which is available in React Native.

## License

GPL-2.0
