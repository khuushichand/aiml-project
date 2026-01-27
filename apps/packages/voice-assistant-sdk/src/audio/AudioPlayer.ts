/**
 * AudioPlayer
 *
 * Audio playback for TTS responses.
 * Handles streaming audio chunks and queue management.
 */

import { EventEmitter } from 'eventemitter3';

export interface AudioPlayerEvents {
  start: () => void;
  end: () => void;
  chunk: (sequence: number) => void;
  error: (error: Error) => void;
}

export class AudioPlayer extends EventEmitter<AudioPlayerEvents> {
  private audioContext: AudioContext | null = null;
  private gainNode: GainNode | null = null;
  private isPlaying = false;
  private audioQueue: { data: ArrayBuffer; sequence: number }[] = [];
  private currentSource: AudioBufferSourceNode | null = null;
  private nextStartTime = 0;
  private volume = 1.0;

  constructor() {
    super();
  }

  /**
   * Initialize the audio player.
   */
  async initialize(): Promise<void> {
    if (this.audioContext) {
      return;
    }

    this.audioContext = new AudioContext();
    this.gainNode = this.audioContext.createGain();
    this.gainNode.gain.value = this.volume;
    this.gainNode.connect(this.audioContext.destination);
  }

  /**
   * Add an audio chunk to the playback queue.
   *
   * @param data - Base64-encoded audio data
   * @param sequence - Chunk sequence number
   * @param format - Audio format (mp3, opus, wav, pcm)
   */
  async addChunk(data: string, sequence: number, format: string): Promise<void> {
    if (!this.audioContext) {
      await this.initialize();
    }

    try {
      // Decode base64
      const binaryString = atob(data);
      const bytes = new Uint8Array(binaryString.length);
      for (let i = 0; i < binaryString.length; i++) {
        bytes[i] = binaryString.charCodeAt(i);
      }

      // Queue the chunk
      this.audioQueue.push({ data: bytes.buffer, sequence });

      // Start playback if not already playing
      if (!this.isPlaying && this.audioQueue.length === 1) {
        this.startPlayback();
      }
    } catch (error) {
      this.emit('error', error instanceof Error ? error : new Error(String(error)));
    }
  }

  /**
   * Stop playback and clear the queue.
   */
  stop(): void {
    this.audioQueue = [];

    if (this.currentSource) {
      try {
        this.currentSource.stop();
      } catch {
        // Ignore - may already be stopped
      }
      this.currentSource = null;
    }

    this.isPlaying = false;
    this.nextStartTime = 0;
  }

  /**
   * Set the playback volume.
   *
   * @param volume - Volume level (0.0 - 1.0)
   */
  setVolume(volume: number): void {
    this.volume = Math.max(0, Math.min(1, volume));

    if (this.gainNode) {
      this.gainNode.gain.value = this.volume;
    }
  }

  /**
   * Get the current volume.
   */
  getVolume(): number {
    return this.volume;
  }

  /**
   * Check if currently playing.
   */
  isActive(): boolean {
    return this.isPlaying;
  }

  /**
   * Get the number of chunks in the queue.
   */
  getQueueLength(): number {
    return this.audioQueue.length;
  }

  // Private methods

  private async startPlayback(): Promise<void> {
    if (!this.audioContext || !this.gainNode) {
      return;
    }

    this.isPlaying = true;
    this.emit('start');
    this.nextStartTime = this.audioContext.currentTime;

    await this.playNextChunk();
  }

  private async playNextChunk(): Promise<void> {
    if (!this.audioContext || !this.gainNode || this.audioQueue.length === 0) {
      this.isPlaying = false;
      this.emit('end');
      return;
    }

    const chunk = this.audioQueue.shift();
    if (!chunk) {
      return;
    }

    try {
      // Decode audio data
      const audioBuffer = await this.audioContext.decodeAudioData(chunk.data.slice(0));

      // Create source node
      const source = this.audioContext.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(this.gainNode);

      // Schedule playback
      const startTime = Math.max(this.audioContext.currentTime, this.nextStartTime);
      source.start(startTime);

      this.currentSource = source;
      this.nextStartTime = startTime + audioBuffer.duration;

      this.emit('chunk', chunk.sequence);

      // Schedule next chunk
      source.onended = () => {
        this.playNextChunk();
      };
    } catch (error) {
      console.error('Failed to decode audio chunk:', error);
      // Try next chunk
      await this.playNextChunk();
    }
  }
}
