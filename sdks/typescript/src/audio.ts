/**
 * Browser audio utilities for voice assistant.
 *
 * Provides microphone capture and audio playback using Web Audio API.
 */

import type { AudioFormat, TTSChunk } from './types';

/**
 * Options for AudioCapture.
 */
export interface AudioCaptureOptions {
  /** Sample rate in Hz. Default: 16000 */
  sampleRate?: number;
  /** Chunk size in samples. Default: 4096 */
  chunkSize?: number;
  /** Audio channels. Default: 1 (mono) */
  channels?: number;
  /** Enable noise suppression if available. Default: true */
  noiseSuppression?: boolean;
  /** Enable echo cancellation if available. Default: true */
  echoCancellation?: boolean;
  /** Enable auto gain control if available. Default: true */
  autoGainControl?: boolean;
}

/**
 * Callback for audio data chunks.
 */
export type AudioChunkCallback = (data: Float32Array) => void;

/**
 * Audio capture from microphone using Web Audio API.
 *
 * @example
 * ```typescript
 * const capture = new AudioCapture({
 *   sampleRate: 16000,
 *   onChunk: (data) => {
 *     client.sendAudio(data);
 *   },
 * });
 *
 * await capture.start();
 * // ... when done
 * capture.stop();
 * ```
 */
export class AudioCapture {
  private options: Required<AudioCaptureOptions>;
  private onChunk: AudioChunkCallback;
  private stream: MediaStream | null = null;
  private audioContext: AudioContext | null = null;
  private processor: ScriptProcessorNode | AudioWorkletNode | null = null;
  private source: MediaStreamAudioSourceNode | null = null;
  private isCapturing = false;

  constructor(options: AudioCaptureOptions & { onChunk: AudioChunkCallback }) {
    this.options = {
      sampleRate: options.sampleRate ?? 16000,
      chunkSize: options.chunkSize ?? 4096,
      channels: options.channels ?? 1,
      noiseSuppression: options.noiseSuppression ?? true,
      echoCancellation: options.echoCancellation ?? true,
      autoGainControl: options.autoGainControl ?? true,
    };
    this.onChunk = options.onChunk;
  }

  /** Check if currently capturing audio. */
  get capturing(): boolean {
    return this.isCapturing;
  }

  /** Start capturing audio from the microphone. */
  async start(): Promise<void> {
    if (this.isCapturing) {
      return;
    }

    // Request microphone access
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        sampleRate: this.options.sampleRate,
        channelCount: this.options.channels,
        noiseSuppression: this.options.noiseSuppression,
        echoCancellation: this.options.echoCancellation,
        autoGainControl: this.options.autoGainControl,
      },
    });

    // Create audio context
    this.audioContext = new AudioContext({
      sampleRate: this.options.sampleRate,
    });

    // Create source from stream
    this.source = this.audioContext.createMediaStreamSource(this.stream);

    // Use ScriptProcessorNode (deprecated but widely supported)
    // TODO: Switch to AudioWorkletNode when widely supported
    this.processor = this.audioContext.createScriptProcessor(
      this.options.chunkSize,
      this.options.channels,
      this.options.channels
    );

    this.processor.onaudioprocess = (event: AudioProcessingEvent) => {
      if (this.isCapturing) {
        const inputData = event.inputBuffer.getChannelData(0);
        // Clone the data since the buffer will be reused
        const chunk = new Float32Array(inputData);
        this.onChunk(chunk);
      }
    };

    // Connect the audio graph
    this.source.connect(this.processor);
    this.processor.connect(this.audioContext.destination);

    this.isCapturing = true;
  }

  /** Stop capturing audio. */
  stop(): void {
    this.isCapturing = false;

    if (this.processor) {
      this.processor.disconnect();
      this.processor = null;
    }

    if (this.source) {
      this.source.disconnect();
      this.source = null;
    }

    if (this.audioContext) {
      this.audioContext.close();
      this.audioContext = null;
    }

    if (this.stream) {
      this.stream.getTracks().forEach((track) => track.stop());
      this.stream = null;
    }
  }
}

/**
 * Options for AudioPlayer.
 */
export interface AudioPlayerOptions {
  /** Initial volume (0.0 to 1.0). Default: 1.0 */
  volume?: number;
}

/**
 * Audio player for TTS output using Web Audio API.
 *
 * @example
 * ```typescript
 * const player = new AudioPlayer();
 *
 * client.onTtsChunk((chunk) => {
 *   player.queueChunk(chunk);
 * });
 *
 * client.onTtsEnd(() => {
 *   player.finalize();
 * });
 * ```
 */
export class AudioPlayer {
  private audioContext: AudioContext | null = null;
  private gainNode: GainNode | null = null;
  private chunks: ArrayBuffer[] = [];
  private _volume: number;
  private isPlaying = false;
  private currentSource: AudioBufferSourceNode | null = null;

  constructor(options: AudioPlayerOptions = {}) {
    this._volume = options.volume ?? 1.0;
  }

  /** Get/set volume (0.0 to 1.0). */
  get volume(): number {
    return this._volume;
  }

  set volume(value: number) {
    this._volume = Math.max(0, Math.min(1, value));
    if (this.gainNode) {
      this.gainNode.gain.value = this._volume;
    }
  }

  /** Check if currently playing audio. */
  get playing(): boolean {
    return this.isPlaying;
  }

  /** Initialize the audio context (must be called after user interaction). */
  async init(): Promise<void> {
    if (this.audioContext) {
      return;
    }

    this.audioContext = new AudioContext();
    this.gainNode = this.audioContext.createGain();
    this.gainNode.gain.value = this._volume;
    this.gainNode.connect(this.audioContext.destination);
  }

  /**
   * Queue a TTS audio chunk for playback.
   * @param chunk - TTS chunk from the voice assistant
   */
  queueChunk(chunk: TTSChunk): void {
    this.chunks.push(chunk.data);
  }

  /**
   * Finalize and play all queued chunks.
   * Call this when TTS_END is received.
   */
  async finalize(): Promise<void> {
    if (this.chunks.length === 0) {
      return;
    }

    await this.init();

    // Combine all chunks
    const totalLength = this.chunks.reduce((sum, chunk) => sum + chunk.byteLength, 0);
    const combined = new Uint8Array(totalLength);
    let offset = 0;
    for (const chunk of this.chunks) {
      combined.set(new Uint8Array(chunk), offset);
      offset += chunk.byteLength;
    }
    this.chunks = [];

    // Decode and play
    try {
      const audioBuffer = await this.audioContext!.decodeAudioData(combined.buffer);
      await this.playBuffer(audioBuffer);
    } catch (error) {
      console.error('[AudioPlayer] Failed to decode audio:', error);
    }
  }

  /**
   * Play raw audio data.
   * @param data - Audio data as ArrayBuffer
   */
  async play(data: ArrayBuffer): Promise<void> {
    await this.init();

    try {
      const audioBuffer = await this.audioContext!.decodeAudioData(data);
      await this.playBuffer(audioBuffer);
    } catch (error) {
      console.error('[AudioPlayer] Failed to decode audio:', error);
    }
  }

  /** Stop current playback. */
  stop(): void {
    if (this.currentSource) {
      this.currentSource.stop();
      this.currentSource = null;
    }
    this.isPlaying = false;
    this.chunks = [];
  }

  /** Close the audio player and release resources. */
  close(): void {
    this.stop();
    if (this.audioContext) {
      this.audioContext.close();
      this.audioContext = null;
      this.gainNode = null;
    }
  }

  private async playBuffer(buffer: AudioBuffer): Promise<void> {
    if (!this.audioContext || !this.gainNode) {
      return;
    }

    // Stop any current playback
    if (this.currentSource) {
      this.currentSource.stop();
    }

    const source = this.audioContext.createBufferSource();
    source.buffer = buffer;
    source.connect(this.gainNode);

    this.currentSource = source;
    this.isPlaying = true;

    return new Promise((resolve) => {
      source.onended = () => {
        this.isPlaying = false;
        this.currentSource = null;
        resolve();
      };
      source.start(0);
    });
  }
}

/**
 * Voice Activity Detection (VAD) using simple energy-based detection.
 *
 * @example
 * ```typescript
 * const vad = new VoiceActivityDetector({
 *   onSpeechStart: () => console.log('Speech started'),
 *   onSpeechEnd: () => {
 *     console.log('Speech ended');
 *     client.commit();
 *   },
 * });
 *
 * capture.onChunk = (data) => {
 *   vad.process(data);
 *   if (vad.isSpeaking) {
 *     client.sendAudio(data);
 *   }
 * };
 * ```
 */
export class VoiceActivityDetector {
  private threshold: number;
  private silenceDelay: number;
  private speechPadding: number;
  private onSpeechStart?: () => void;
  private onSpeechEnd?: () => void;

  private _isSpeaking = false;
  private silenceFrames = 0;
  private speechFrames = 0;
  private frameCount = 0;

  constructor(options: {
    /** Energy threshold for speech detection. Default: 0.01 */
    threshold?: number;
    /** Number of silent frames before ending speech. Default: 30 */
    silenceDelay?: number;
    /** Number of speech frames before starting. Default: 3 */
    speechPadding?: number;
    /** Callback when speech starts */
    onSpeechStart?: () => void;
    /** Callback when speech ends */
    onSpeechEnd?: () => void;
  } = {}) {
    this.threshold = options.threshold ?? 0.01;
    this.silenceDelay = options.silenceDelay ?? 30;
    this.speechPadding = options.speechPadding ?? 3;
    this.onSpeechStart = options.onSpeechStart;
    this.onSpeechEnd = options.onSpeechEnd;
  }

  /** Check if currently detecting speech. */
  get isSpeaking(): boolean {
    return this._isSpeaking;
  }

  /**
   * Process an audio chunk and detect voice activity.
   * @param data - Audio samples as Float32Array
   * @returns true if speech was detected in this chunk
   */
  process(data: Float32Array): boolean {
    this.frameCount++;

    // Calculate RMS energy
    let sum = 0;
    for (let i = 0; i < data.length; i++) {
      sum += data[i] * data[i];
    }
    const rms = Math.sqrt(sum / data.length);
    const hasSpeech = rms > this.threshold;

    if (hasSpeech) {
      this.silenceFrames = 0;
      this.speechFrames++;

      if (!this._isSpeaking && this.speechFrames >= this.speechPadding) {
        this._isSpeaking = true;
        this.onSpeechStart?.();
      }
    } else {
      this.speechFrames = 0;

      if (this._isSpeaking) {
        this.silenceFrames++;
        if (this.silenceFrames >= this.silenceDelay) {
          this._isSpeaking = false;
          this.onSpeechEnd?.();
        }
      }
    }

    return hasSpeech;
  }

  /** Reset the detector state. */
  reset(): void {
    this._isSpeaking = false;
    this.silenceFrames = 0;
    this.speechFrames = 0;
    this.frameCount = 0;
  }
}
