import axios from 'axios';
export interface Voice {
  voice_id: string;
  name: string;
}

export interface Model {
  model_id: string;
  name: string;
}

const BASE_URL = 'https://api.elevenlabs.io/v1';
const DEFAULT_ELEVENLABS_TIMEOUT_MS = 10_000;

type ElevenLabsRequestOptions = {
  timeoutMs?: number;
};

export const getVoices = async (
  apiKey: string,
  options?: ElevenLabsRequestOptions
): Promise<Voice[]> => {
  const response = await axios.get(`${BASE_URL}/voices`, {
    headers: { 'xi-api-key': apiKey },
    timeout: options?.timeoutMs ?? DEFAULT_ELEVENLABS_TIMEOUT_MS
  });
  return response.data.voices;
};

export const getModels = async (
  apiKey: string,
  options?: ElevenLabsRequestOptions
): Promise<Model[]> => {
  const response = await axios.get(`${BASE_URL}/models`, {
    headers: { 'xi-api-key': apiKey },
    timeout: options?.timeoutMs ?? DEFAULT_ELEVENLABS_TIMEOUT_MS
  });
  return response.data;
};

export const generateSpeech = async (
  apiKey: string,
  text: string,
  voiceId: string,
  modelId: string,
  speed?: number
): Promise<ArrayBuffer> => {
  const payload: Record<string, any> = {
    text,
    model_id: modelId
  }

  if (speed != null) {
    payload.voice_settings = { speed }
  }

  const response = await axios.post(
    `${BASE_URL}/text-to-speech/${voiceId}`,
    payload,
    {
      headers: {
        'xi-api-key': apiKey,
        'Content-Type': 'application/json',
      },
      responseType: 'arraybuffer',
    }
  );
  return response.data;
};
