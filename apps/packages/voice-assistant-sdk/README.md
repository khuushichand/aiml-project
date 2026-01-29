# @tldw/voice-assistant-sdk

Voice Assistant SDK for tldw_server - WebSocket client with audio capture and React hooks.

## Installation

```bash
# Using bun (recommended in monorepo)
bun add @tldw/voice-assistant-sdk

# Or using npm
npm install @tldw/voice-assistant-sdk
```

## Quick Start

### Basic Client Usage

```typescript
import { VoiceAssistantClient } from '@tldw/voice-assistant-sdk';

const client = new VoiceAssistantClient({
  wsUrl: 'ws://localhost:8000/api/v1/voice/assistant',
  token: 'your-api-key-or-jwt',
  debug: true,
});

// Event handlers
client.on('transcription', (data) => {
  console.log('Transcription:', data.text);
});

client.on('actionResult', (data) => {
  console.log('Result:', data.response_text);
});

client.on('error', (data) => {
  console.error('Error:', data.error);
});

// Connect and send a command
await client.connect();
client.sendText('search for machine learning');
```

### React Hook Usage

```tsx
import { useVoiceAssistant } from '@tldw/voice-assistant-sdk/hooks';

function VoiceAssistant() {
  const {
    isConnected,
    isListening,
    transcription,
    actionResult,
    audioLevel,
    connect,
    startListening,
    stopListening,
    sendText,
  } = useVoiceAssistant({
    wsUrl: 'ws://localhost:8000/api/v1/voice/assistant',
    token: 'your-api-key',
    autoConnect: true,
    autoPlayTTS: true,
  });

  return (
    <div>
      <div>Status: {isConnected ? 'Connected' : 'Disconnected'}</div>

      <button onClick={isListening ? stopListening : startListening}>
        {isListening ? '🔴 Stop' : '🎤 Start'}
      </button>

      <div style={{ width: `${audioLevel * 100}%` }} className="level-bar" />

      {transcription && <p>You said: {transcription}</p>}
      {actionResult && <p>Response: {actionResult.response_text}</p>}

      <input
        type="text"
        placeholder="Or type a command..."
        onKeyDown={(e) => {
          if (e.key === 'Enter') {
            sendText(e.currentTarget.value);
            e.currentTarget.value = '';
          }
        }}
      />
    </div>
  );
}
```

### Audio Capture Only

```typescript
import { AudioCapture } from '@tldw/voice-assistant-sdk/audio';

const capture = new AudioCapture({
  sampleRate: 16000,
  echoCancellation: true,
});

capture.on('data', (audioData: Float32Array) => {
  // Process audio data
});

capture.on('level', (level: number) => {
  // Update audio level indicator (0.0 - 1.0)
});

await capture.start();
// ... later
capture.stop();
```

## API Reference

### VoiceAssistantClient

The main WebSocket client for voice assistant communication.

#### Constructor Options

```typescript
interface VoiceAssistantConfig {
  wsUrl: string;              // WebSocket URL
  token: string;              // Auth token (JWT or API key)
  sttModel?: string;          // STT model (default: 'parakeet')
  sttLanguage?: string;       // Language code
  ttsProvider?: string;       // TTS provider (default: 'kokoro')
  ttsVoice?: string;          // TTS voice (default: 'af_heart')
  ttsFormat?: string;         // Audio format (default: 'mp3')
  sampleRate?: number;        // Sample rate (default: 16000)
  sessionId?: string;         // Resume session
  autoReconnect?: boolean;    // Auto-reconnect (default: true)
  maxReconnectAttempts?: number; // Max retries (default: 5)
  debug?: boolean;            // Debug logging (default: false)
}
```

#### Methods

| Method | Description |
|--------|-------------|
| `connect()` | Connect to the WebSocket endpoint |
| `disconnect()` | Disconnect from the server |
| `sendAudio(data)` | Send audio data (Float32Array or base64) |
| `commit()` | Signal end of utterance |
| `cancel()` | Cancel current operation |
| `sendText(text)` | Send text command (bypasses STT) |
| `subscribeToWorkflow(runId)` | Subscribe to workflow progress |
| `cancelWorkflow(runId)` | Cancel a running workflow |

#### Events

| Event | Payload | Description |
|-------|---------|-------------|
| `connected` | - | WebSocket connected |
| `disconnected` | `reason: string` | WebSocket disconnected |
| `authenticated` | `WSAuthOKMessage` | Auth successful |
| `authError` | `error: string` | Auth failed |
| `configured` | `WSConfigAckMessage` | Config acknowledged |
| `stateChange` | `state, previousState` | State changed |
| `transcription` | `WSTranscriptionMessage` | STT result |
| `intent` | `WSIntentMessage` | Parsed intent |
| `actionStart` | `WSActionStartMessage` | Action started |
| `actionResult` | `WSActionResultMessage` | Action completed |
| `ttsChunk` | `WSTTSChunkMessage` | TTS audio chunk |
| `ttsEnd` | `WSTTSEndMessage` | TTS completed |
| `workflowProgress` | `WSWorkflowProgressMessage` | Workflow update |
| `workflowComplete` | `WSWorkflowCompleteMessage` | Workflow done |
| `error` | `WSErrorMessage` | Error occurred |

### useVoiceAssistant Hook

React hook providing complete voice assistant functionality.

#### Return Value

```typescript
interface UseVoiceAssistantReturn {
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
  audioLevel: number;

  // Results
  transcription: string | null;
  intent: WSIntentMessage | null;
  actionResult: WSActionResultMessage | null;
  error: WSErrorMessage | null;

  // History
  history: Array<{ role: 'user' | 'assistant'; content: string; timestamp: Date }>;

  // Actions
  connect: () => Promise<void>;
  disconnect: () => void;
  startListening: () => Promise<void>;
  stopListening: () => void;
  sendText: (text: string) => void;
  cancel: () => void;
  clearHistory: () => void;
  stopTTS: () => void;
  setTTSVolume: (volume: number) => void;
}
```

### AudioCapture

Audio capture from microphone with real-time streaming.

#### Constructor Options

```typescript
interface AudioConfig {
  sampleRate: number;        // Sample rate (default: 16000)
  channelCount: number;      // Channels (default: 1)
  echoCancellation: boolean; // Echo cancellation (default: true)
  noiseSuppression: boolean; // Noise suppression (default: true)
  autoGainControl: boolean;  // Auto gain (default: true)
}
```

#### Events

| Event | Payload | Description |
|-------|---------|-------------|
| `start` | - | Capture started |
| `stop` | - | Capture stopped |
| `data` | `Float32Array` | Audio samples |
| `level` | `number` | Audio level (0-1) |
| `error` | `Error` | Error occurred |

### AudioPlayer

Audio playback for TTS responses with streaming support.

#### Methods

| Method | Description |
|--------|-------------|
| `initialize()` | Initialize the player |
| `addChunk(data, sequence, format)` | Add audio chunk to queue |
| `stop()` | Stop playback and clear queue |
| `setVolume(volume)` | Set volume (0-1) |
| `getVolume()` | Get current volume |

## Wake Word Integration

The SDK is designed to work with wake word engines. Here's an example with Porcupine:

```typescript
import { VoiceAssistantClient, AudioCapture } from '@tldw/voice-assistant-sdk';
import { Porcupine } from '@picovoice/porcupine-web';

// Initialize wake word detection
const porcupine = await Porcupine.create(accessKey, ['hey jarvis']);

// Initialize voice assistant
const client = new VoiceAssistantClient({
  wsUrl: 'ws://localhost:8000/api/v1/voice/assistant',
  token: 'your-token',
});

const capture = new AudioCapture();

// Process audio for wake word
capture.on('data', (audioData) => {
  const keywordIndex = porcupine.process(audioData);
  if (keywordIndex >= 0) {
    // Wake word detected - start streaming to server
    client.connect().then(() => {
      // Continue sending audio
    });
  }
});

await capture.start();
```

## Browser Support

- Chrome 66+
- Firefox 76+
- Safari 14.1+
- Edge 79+

Required APIs:
- `navigator.mediaDevices.getUserMedia`
- `AudioContext` / `AudioWorklet`
- `WebSocket`

## License

MIT
