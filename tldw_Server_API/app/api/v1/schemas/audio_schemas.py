# audio_schemas.py
# This module defines the Pydantic schemas for audio-related data models.
#
# Imports
#
# Third-party Libraries
#
# Local Imports
#
#######################################################################################################################
from typing import Literal, Optional, Dict, Any, List

from pydantic import Field, BaseModel


class NormalizationOptions(BaseModel):
    """Options for the normalization system"""

    normalize: bool = Field(
        default=True,
        description="Normalizes input text to make it easier for the model to say",
    )
    unit_normalization: bool = Field(
        default=False, description="Transforms units like 10KB to 10 kilobytes"
    )
    url_normalization: bool = Field(
        default=True,
        description="Changes urls so they can be properly pronounced by kokoro",
    )
    email_normalization: bool = Field(
        default=True,
        description="Changes emails so they can be properly pronouced by kokoro",
    )
    optional_pluralization_normalization: bool = Field(
        default=True,
        description="Replaces (s) with s so some words get pronounced correctly",
    )
    phone_normalization: bool = Field(
        default=True,
        description="Changes phone numbers so they can be properly pronouced by kokoro",
    )


class OpenAISpeechRequest(BaseModel):
    """Request schema for OpenAI-compatible speech endpoint"""

    model: str = Field(
        default="kokoro",
        description="The model to use for generation. Supported models: tts-1, tts-1-hd, kokoro, higgs, chatterbox, vibevoice",
    )
    input: str = Field(..., description="The text to generate audio for")
    voice: str = Field(
        default="af_heart",
        description="The voice to use for generation. Can be a base voice or a combined voice name.",
    )
    response_format: Literal["mp3", "opus", "aac", "flac", "wav", "pcm"] = Field(
        default="mp3",
        description=(
            "The format to return audio in. Supported formats: mp3, opus, aac, flac, wav, pcm. "
            "PCM format returns raw 16-bit samples without headers."
        ),
    )
    download_format: Optional[Literal["mp3", "opus", "aac", "flac", "wav", "pcm"]] = (
        Field(
            default=None,
            description=(
                "Reserved for future use. Currently ignored; the final audio format always matches response_format."
            ),
        )
    )
    speed: float = Field(
        default=1.0,
        ge=0.25,
        le=4.0,
        description="The speed of the generated audio. Select a value from 0.25 to 4.0.",
    )
    stream: bool = Field(
        default=True,  # Default to streaming for OpenAI compatibility
        description="If true (default), audio will be streamed as it's generated. Each chunk will be a complete sentence.",
    )
    return_download_link: bool = Field(
        default=False,
        description="If true, returns a download link in X-Download-Path header after streaming completes",
    )
    lang_code: Optional[str] = Field(
        default=None,
        description="Optional language code to use for text processing. If not provided, will use first letter of voice name.",
    )
    normalization_options: Optional[NormalizationOptions] = Field(
        default=NormalizationOptions(),
        description="Options for the normalization system",
    )
    voice_reference: Optional[str] = Field(
        default=None,
        description="Base64-encoded audio data for voice cloning/reference. Supported by Higgs (3-10s), Chatterbox (5-20s), and VibeVoice models.",
    )
    reference_duration_min: Optional[float] = Field(
        default=None,
        ge=3.0,
        le=60.0,
        description="Minimum duration in seconds for voice reference audio. If provided, will validate reference audio length.",
    )
    extra_params: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Provider-specific parameters passed through to adapters (e.g., stability, clarity, cfg_scale).",
    )


class OpenAITranscriptionRequest(BaseModel):
    """Request schema for OpenAI-compatible transcription endpoint"""

    file: bytes = Field(..., description="The audio file to transcribe")
    model: str = Field(
        default="whisper-1",
        description="ID of the model to use. Options: whisper-1, parakeet, canary, qwen2audio"
    )
    language: Optional[str] = Field(
        default=None,
        description="The language of the input audio. Supplying the input language in ISO-639-1 format will improve accuracy and latency."
    )
    prompt: Optional[str] = Field(
        default=None,
        description="An optional text to guide the model's style or continue a previous audio segment. The prompt should match the audio language."
    )
    response_format: Literal["json", "text", "srt", "verbose_json", "vtt"] = Field(
        default="json",
        description="The format of the transcript output"
    )
    temperature: Optional[float] = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="The sampling temperature, between 0 and 1. Higher values make the output more random."
    )
    timestamp_granularities: Optional[list[Literal["word", "segment"]]] = Field(
        default=["segment"],
        description="The timestamp granularities to populate for this transcription"
    )


class OpenAITranscriptionResponse(BaseModel):
    """Response schema for OpenAI-compatible transcription endpoint"""

    text: str = Field(..., description="The transcribed text")
    language: Optional[str] = Field(None, description="The language of the input audio")
    duration: Optional[float] = Field(None, description="The duration of the input audio in seconds")
    words: Optional[list] = Field(None, description="Word-level timestamps if requested")
    segments: Optional[list] = Field(None, description="Segment-level timestamps if requested")


class OpenAITranslationRequest(BaseModel):
    """Request schema for OpenAI-compatible translation endpoint"""

    file: bytes = Field(..., description="The audio file to translate")
    model: str = Field(
        default="whisper-1",
        description="ID of the model to use. Currently only whisper-1 is available"
    )
    prompt: Optional[str] = Field(
        default=None,
        description="An optional text to guide the model's style or continue a previous audio segment"
    )
    response_format: Literal["json", "text", "srt", "verbose_json", "vtt"] = Field(
        default="json",
        description="The format of the transcript output"
    )
    temperature: Optional[float] = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="The sampling temperature"
    )

#
# End of audio_schemas.py
#######################################################################################################################
class TranscriptUtterance(BaseModel):
    """Single utterance entry for transcript segmentation."""

    composite: str = Field(..., description="Utterance text or composite text")
    start: Optional[float] = Field(None, description="Start time in seconds")
    end: Optional[float] = Field(None, description="End time in seconds")
    speaker: Optional[str] = Field(None, description="Speaker label")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Arbitrary extra metadata")


class TranscriptSegmentInfo(BaseModel):
    indices: List[int]
    start_index: int
    end_index: int
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    speakers: List[str] = []
    text: str


class TranscriptSegmentationRequest(BaseModel):
    """Request schema for transcript tree segmentation."""

    entries: List[TranscriptUtterance] = Field(..., description="Transcript utterances")
    K: int = Field(6, ge=1, description="Maximum number of segments")
    min_segment_size: int = Field(5, ge=1, description="Minimum items per segment")
    lambda_balance: float = Field(0.01, ge=0.0, description="Balance penalty coefficient")
    utterance_expansion_width: int = Field(2, ge=0, description="Number of previous utterances to join per block")
    min_improvement_ratio: float = Field(0.0, ge=0.0, description="Stop splitting if relative improvement is below this threshold (0-1)")
    embeddings_provider: Optional[str] = Field(None, description="Embedding provider (if using built-in service)")
    embeddings_model: Optional[str] = Field(None, description="Embedding model (if using built-in service)")


class TranscriptSegmentationResponse(BaseModel):
    """Response schema with transitions vector and segment details."""

    transitions: List[int]
    transition_indices: List[int] = []
    segments: List[TranscriptSegmentInfo]


#######################################################################################################################
#
# Speech-to-Speech Chat (STT → LLM → TTS) Schemas


class SpeechChatSTTConfig(BaseModel):
    """Configuration options for STT in the speech chat pipeline."""

    provider: Optional[str] = Field(
        default=None,
        description="STT provider key (e.g., 'faster-whisper', 'parakeet', 'canary', 'qwen2audio'). "
                    "If omitted, the server's STT default is used.",
    )
    model: Optional[str] = Field(
        default=None,
        description="Optional STT model identifier. Semantics match existing STT configuration.",
    )
    language: Optional[str] = Field(
        default=None,
        description="Optional language code (ISO-639-1/2) to bias transcription.",
    )
    extra_params: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Provider-specific STT parameters passed through to underlying adapters.",
    )


class SpeechChatLLMConfig(BaseModel):
    """Configuration options for LLM in the speech chat pipeline."""

    api_provider: Optional[str] = Field(
        default=None,
        description="Target LLM provider (e.g., 'openai', 'anthropic'). If omitted, uses the server default.",
    )
    model: Optional[str] = Field(
        default=None,
        description="LLM model identifier. Required for v1; no default is inferred.",
    )
    temperature: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=2.0,
        description="Sampling temperature.",
    )
    max_tokens: Optional[int] = Field(
        default=None,
        ge=1,
        description="Maximum number of tokens to generate.",
    )
    extra_params: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Provider-specific LLM parameters passed through to the orchestrator.",
    )


class SpeechChatTTSConfig(BaseModel):
    """Configuration options for TTS in the speech chat pipeline."""

    provider: Optional[str] = Field(
        default=None,
        description="TTS provider hint (e.g., 'openai', 'kokoro'). If omitted, the TTS service selects a provider.",
    )
    model: Optional[str] = Field(
        default=None,
        description="Optional TTS model identifier. If omitted, the TTS provider's default is used.",
    )
    voice: Optional[str] = Field(
        default=None,
        description="Voice identifier, matching the semantics of the /audio/speech endpoint.",
    )
    response_format: Optional[Literal["mp3", "opus", "aac", "flac", "wav", "pcm"]] = Field(
        default=None,
        description="Desired audio format for the synthesized response. Defaults to 'mp3' if not provided.",
    )
    speed: Optional[float] = Field(
        default=None,
        ge=0.25,
        le=4.0,
        description="Optional speed multiplier for synthesized audio.",
    )
    extra_params: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Provider-specific TTS parameters passed through to adapters.",
    )


class SpeechChatRequest(BaseModel):
    """
    Request body for the non-streaming Speech-to-Speech chat endpoint.

    The client sends a single base64-encoded audio clip representing the user utterance,
    along with optional STT/LLM/TTS configuration.
    """

    session_id: Optional[str] = Field(
        default=None,
        description="Optional chat session identifier. If omitted, a new session is created.",
    )
    input_audio: str = Field(
        ...,
        description="Base64-encoded audio data for the user utterance (no data: URI prefix).",
    )
    input_audio_format: str = Field(
        ...,
        description="Declared audio format for input_audio (e.g., 'wav', 'mp3', 'ogg').",
    )
    stt_config: Optional[SpeechChatSTTConfig] = Field(
        default=None,
        description="Optional STT configuration. Defaults are used when omitted.",
    )
    llm_config: SpeechChatLLMConfig = Field(
        ...,
        description="LLM configuration for generating the assistant reply. Model is required in v1.",
    )
    tts_config: Optional[SpeechChatTTSConfig] = Field(
        default=None,
        description="Optional TTS configuration. Reasonable defaults are used when omitted.",
    )
    store_audio: Optional[bool] = Field(
        default=False,
        description="Optional hint to store raw audio alongside transcripts when enabled server-side.",
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Arbitrary client metadata (trace IDs, UI hints, etc.).",
    )


class SpeechChatTiming(BaseModel):
    """Timing information for each stage of the pipeline in milliseconds."""

    stt_ms: float = Field(..., description="Time spent in STT (milliseconds).")
    llm_ms: float = Field(..., description="Time spent in LLM call (milliseconds).")
    tts_ms: float = Field(..., description="Time spent in TTS synthesis (milliseconds).")


class SpeechChatTokenUsage(BaseModel):
    """Token usage summary derived from the LLM response, when available."""

    prompt_tokens: Optional[int] = Field(
        default=None,
        description="Number of prompt tokens consumed.",
    )
    completion_tokens: Optional[int] = Field(
        default=None,
        description="Number of completion tokens generated.",
    )
    total_tokens: Optional[int] = Field(
        default=None,
        description="Total tokens (prompt + completion).",
    )


class SpeechChatResponse(BaseModel):
    """
    Response body for the non-streaming Speech-to-Speech chat endpoint.

    Returns the resolved session identifier, user transcript, assistant reply text,
    and base64-encoded audio for the reply, along with timing, optional token usage,
    and an optional action_result payload when a downstream action/workflow is executed.
    """

    session_id: str = Field(..., description="Resolved chat session identifier.")
    user_transcript: str = Field(..., description="Full text transcription of the user audio turn.")
    assistant_text: str = Field(..., description="Assistant reply text produced by the LLM.")
    output_audio: str = Field(
        ...,
        description="Base64-encoded audio data for the assistant reply (no data: URI prefix).",
    )
    output_audio_mime_type: str = Field(
        ...,
        description="MIME type corresponding to output_audio (e.g., 'audio/mpeg', 'audio/wav').",
    )
    timing: SpeechChatTiming = Field(
        ...,
        description="Timing information for STT, LLM, and TTS stages.",
    )
    token_usage: Optional[SpeechChatTokenUsage] = Field(
        default=None,
        description="Optional token usage summary from the LLM response.",
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional metadata echo or server-side annotations.",
    )
    action_result: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional action/workflow execution result derived from the transcript.",
    )
