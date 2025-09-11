# Audio_Streaming_Unified.py
#########################################
# Unified Real-time Streaming Transcription for All Nemo Models
# This module provides WebSocket-based real-time transcription using all Nemo models
# with support for Parakeet (all variants) and Canary (multilingual).
#
####################
# Function List
#
# 1. BaseStreamingTranscriber - Abstract base class for streaming transcription
# 2. ParakeetStreamingTranscriber - Parakeet-specific implementation  
# 3. CanaryStreamingTranscriber - Canary-specific implementation
# 4. UnifiedStreamingTranscriber - Factory and unified interface
# 5. handle_unified_websocket - Unified WebSocket handler
#
####################

import asyncio
import base64
import json
import time
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field
import numpy as np
import tempfile
from pathlib import Path
from fastapi import WebSocketDisconnect
from loguru import logger

# Import existing implementations
from .Audio_Streaming_Parakeet import (
    ParakeetStreamingTranscriber as OriginalParakeetTranscriber,
    StreamingConfig,
    AudioBuffer
)
from .Audio_Transcription_Nemo import (
    load_canary_model,
    transcribe_with_canary,
    load_parakeet_model,
    transcribe_with_parakeet
)


@dataclass
class UnifiedStreamingConfig(StreamingConfig):
    """Extended configuration for unified streaming."""
    model: str = 'parakeet'  # 'parakeet', 'canary', or 'whisper'
    model_variant: str = 'standard'  # For Parakeet: 'standard', 'onnx', 'mlx'
    language: Optional[str] = None  # Language code for transcription
    auto_detect_language: bool = False  # Auto-detect language
    enable_vad: bool = False  # Voice Activity Detection
    vad_threshold: float = 0.5
    # Whisper-specific options
    whisper_model_size: str = 'distil-large-v3'  # Whisper model size
    beam_size: int = 5  # Beam search size
    vad_filter: bool = False  # Use VAD filter for Whisper
    task: str = 'transcribe'  # 'transcribe' or 'translate'


class BaseStreamingTranscriber(ABC):
    """
    Abstract base class for streaming transcribers.
    
    Defines the common interface for all streaming transcription implementations.
    """
    
    def __init__(self, config: UnifiedStreamingConfig):
        """Initialize base transcriber."""
        self.config = config
        self.buffer = AudioBuffer(
            sample_rate=config.sample_rate,
            max_duration=config.max_buffer_duration
        )
        self.model = None
        self.is_running = False
        self.transcription_history = []
        self.last_partial_time = 0
    
    @abstractmethod
    def initialize(self):
        """Load and initialize the model."""
        pass
    
    @abstractmethod
    async def process_audio_chunk(self, audio_data: bytes) -> Optional[Dict[str, Any]]:
        """Process a chunk of audio data."""
        pass
    
    def get_full_transcript(self) -> str:
        """Get the complete transcript so far."""
        return " ".join(self.transcription_history)
    
    def reset(self):
        """Reset the transcriber state."""
        self.buffer.clear()
        self.transcription_history.clear()
        self.last_partial_time = 0
    
    def cleanup(self):
        """Clean up resources."""
        self.model = None
        self.reset()


class ParakeetStreamingTranscriber(BaseStreamingTranscriber):
    """
    Parakeet-specific streaming transcriber.
    
    Supports all Parakeet variants: standard, ONNX, MLX.
    """
    
    def initialize(self):
        """Load the Parakeet model based on configuration."""
        variant = self.config.model_variant
        logger.info(f"Loading Parakeet model (variant: {variant})")
        
        if variant == 'mlx':
            # MLX model is loaded on-demand in transcribe function
            # First check if MLX dependencies are available
            try:
                from .Audio_Transcription_Parakeet_MLX import transcribe_with_parakeet_mlx
                logger.info("Using Parakeet MLX variant (lazy loading)")
                self.model = "mlx"  # Placeholder to indicate MLX is ready
                return  # Success
            except ImportError as e:
                logger.error(f"Failed to import Parakeet MLX: {e}")
                raise RuntimeError(f"Parakeet MLX dependencies not available. Install with: pip install mlx mlx-lm")
        else:
            # Load standard or ONNX variant (requires Nemo)
            try:
                self.model = load_parakeet_model(variant)
                if self.model is None:
                    raise RuntimeError(f"Failed to load Parakeet {variant} model")
                logger.info(f"Loaded Parakeet {variant} model")
            except ImportError as e:
                if "nemo" in str(e).lower():
                    logger.warning(f"Nemo toolkit not installed, attempting to fallback to MLX variant")
                    # Try to fallback to MLX variant
                    try:
                        from .Audio_Transcription_Parakeet_MLX import transcribe_with_parakeet_mlx
                        logger.info("Falling back to Parakeet MLX variant due to missing Nemo")
                        self.config.model_variant = 'mlx'
                        self.model = "mlx"  # Placeholder to indicate MLX is ready
                        return  # Success with fallback
                    except ImportError:
                        logger.error("MLX fallback failed - MLX dependencies not available")
                        raise RuntimeError(f"Nemo toolkit not installed for {variant} variant and MLX fallback unavailable. "
                                         f"Install Nemo with: pip install nemo_toolkit[asr] "
                                         f"OR install MLX with: pip install mlx mlx-lm")
                raise
    
    async def process_audio_chunk(self, audio_data: bytes) -> Optional[Dict[str, Any]]:
        """
        Process audio chunk with Parakeet.
        
        Args:
            audio_data: Raw audio bytes
            
        Returns:
            Transcription result or None
        """
        # Convert bytes to numpy array
        audio_np = np.frombuffer(audio_data, dtype=np.float32)
        
        # Add to buffer
        self.buffer.add(audio_np)
        
        current_time = time.time()
        buffer_duration = self.buffer.get_duration()
        
        # Check if we should send a partial result
        if (self.config.enable_partial and 
            current_time - self.last_partial_time > self.config.partial_interval and
            buffer_duration > 0.5):
            
            # Get audio for partial transcription
            audio_for_partial = self.buffer.get_audio()
            if audio_for_partial is not None and len(audio_for_partial) > 0:
                # Transcribe partial audio
                if self.config.model_variant == 'mlx':
                    # Use MLX implementation
                    from .Audio_Transcription_Parakeet_MLX import transcribe_with_parakeet_mlx
                    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                        import soundfile as sf
                        sf.write(tmp_file.name, audio_for_partial, self.config.sample_rate)
                        text = transcribe_with_parakeet_mlx(tmp_file.name)
                        Path(tmp_file.name).unlink()
                else:
                    # Use standard/ONNX implementation
                    text = transcribe_with_parakeet(
                        audio_for_partial,
                        self.config.sample_rate,
                        self.config.model_variant
                    )
                
                self.last_partial_time = current_time
                
                if text:
                    return {
                        "type": "partial",
                        "text": text,
                        "timestamp": current_time,
                        "is_final": False,
                        "model": f"parakeet-{self.config.model_variant}"
                    }
        
        # Check if we have enough audio for a final chunk
        if buffer_duration >= self.config.chunk_duration:
            # Get chunk for transcription
            audio_chunk = self.buffer.get_audio(self.config.chunk_duration)
            
            if audio_chunk is not None:
                # Transcribe the chunk
                if self.config.model_variant == 'mlx':
                    from .Audio_Transcription_Parakeet_MLX import transcribe_with_parakeet_mlx
                    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                        import soundfile as sf
                        sf.write(tmp_file.name, audio_chunk, self.config.sample_rate)
                        text = transcribe_with_parakeet_mlx(tmp_file.name)
                        Path(tmp_file.name).unlink()
                else:
                    text = transcribe_with_parakeet(
                        audio_chunk,
                        self.config.sample_rate,
                        self.config.model_variant
                    )
                
                # Consume the buffer, keeping overlap
                self.buffer.consume(
                    self.config.chunk_duration,
                    self.config.overlap_duration
                )
                
                if text:
                    self.transcription_history.append(text)
                    return {
                        "type": "final",
                        "text": text,
                        "timestamp": current_time,
                        "is_final": True,
                        "model": f"parakeet-{self.config.model_variant}"
                    }
        
        return None


class CanaryStreamingTranscriber(BaseStreamingTranscriber):
    """
    Canary-specific streaming transcriber.
    
    Supports multilingual transcription with language detection.
    """
    
    def initialize(self):
        """Load the Canary model."""
        logger.info("Loading Canary multilingual model")
        self.model = load_canary_model()
        if self.model is None:
            raise RuntimeError("Failed to load Canary model")
        logger.info("Loaded Canary model")
        
        # Set default language if not specified
        if not self.config.language:
            self.config.language = 'en'  # Default to English
    
    async def process_audio_chunk(self, audio_data: bytes) -> Optional[Dict[str, Any]]:
        """
        Process audio chunk with Canary.
        
        Args:
            audio_data: Raw audio bytes
            
        Returns:
            Transcription result or None
        """
        # Convert bytes to numpy array
        audio_np = np.frombuffer(audio_data, dtype=np.float32)
        
        # Add to buffer
        self.buffer.add(audio_np)
        
        current_time = time.time()
        buffer_duration = self.buffer.get_duration()
        
        # Check if we should send a partial result
        if (self.config.enable_partial and 
            current_time - self.last_partial_time > self.config.partial_interval and
            buffer_duration > 0.5):
            
            # Get audio for partial transcription
            audio_for_partial = self.buffer.get_audio()
            if audio_for_partial is not None and len(audio_for_partial) > 0:
                # Transcribe partial audio
                text = transcribe_with_canary(
                    audio_for_partial,
                    self.config.sample_rate,
                    self.config.language
                )
                
                self.last_partial_time = current_time
                
                if text:
                    # Detect language if auto-detection is enabled
                    detected_language = self.config.language
                    if self.config.auto_detect_language:
                        # Simple heuristic - could be improved with actual language detection
                        detected_language = self._detect_language(text)
                    
                    return {
                        "type": "partial",
                        "text": text,
                        "timestamp": current_time,
                        "is_final": False,
                        "language": detected_language,
                        "model": "canary-1b"
                    }
        
        # Check if we have enough audio for a final chunk
        if buffer_duration >= self.config.chunk_duration:
            # Get chunk for transcription
            audio_chunk = self.buffer.get_audio(self.config.chunk_duration)
            
            if audio_chunk is not None:
                # Transcribe the chunk
                text = transcribe_with_canary(
                    audio_chunk,
                    self.config.sample_rate,
                    self.config.language
                )
                
                # Consume the buffer, keeping overlap
                self.buffer.consume(
                    self.config.chunk_duration,
                    self.config.overlap_duration
                )
                
                if text:
                    # Detect language if auto-detection is enabled
                    detected_language = self.config.language
                    if self.config.auto_detect_language:
                        detected_language = self._detect_language(text)
                    
                    self.transcription_history.append(text)
                    return {
                        "type": "final",
                        "text": text,
                        "timestamp": current_time,
                        "is_final": True,
                        "language": detected_language,
                        "model": "canary-1b"
                    }
        
        return None
    
    def _detect_language(self, text: str) -> str:
        """
        Simple language detection heuristic.
        
        In production, this should use a proper language detection library.
        """
        # This is a placeholder - in reality, you'd use langdetect or similar
        # For now, just return the configured language
        return self.config.language


class WhisperStreamingTranscriber(BaseStreamingTranscriber):
    """
    Whisper-specific streaming transcriber using faster-whisper.
    
    Optimized for accuracy with configurable model sizes and features.
    """
    
    def initialize(self):
        """Load the Whisper model based on configuration."""
        logger.info(f"WhisperStreamingTranscriber.initialize() called with config: "
                   f"whisper_model_size={self.config.whisper_model_size}, "
                   f"language={self.config.language}, task={self.config.task}")
        
        try:
            # Import Whisper functions from the existing library
            logger.debug("Importing get_whisper_model from Audio_Transcription_Lib")
            from .Audio_Transcription_Lib import get_whisper_model
            logger.debug("Successfully imported get_whisper_model")
            
            # Determine device and compute type
            import torch
            device = 'cuda' if torch.cuda.is_available() else 'cpu'
            
            # Compute type is determined by the device, not a config parameter
            compute_type = 'float16' if device == 'cuda' else 'int8'
            
            logger.info(f"Loading Whisper model: {self.config.whisper_model_size} on {device} with compute_type: {compute_type}")
            
            # Load the model using existing function
            self.model = get_whisper_model(self.config.whisper_model_size, device)
            
            if self.model is None:
                raise RuntimeError(f"Failed to load Whisper model: {self.config.whisper_model_size}")
            
            logger.info(f"Successfully loaded Whisper model: {self.config.whisper_model_size}, model object: {type(self.model)}")
            
            # Set transcription options
            self.transcribe_options = {
                'beam_size': self.config.beam_size,
                'best_of': self.config.beam_size,
                'vad_filter': self.config.vad_filter,
                'task': self.config.task
            }
            
            if self.config.language and not self.config.auto_detect_language:
                self.transcribe_options['language'] = self.config.language
            
            # Whisper works better with longer audio chunks
            self.min_chunk_duration = 1.0  # Minimum 1 second of audio
            self.optimal_chunk_duration = 5.0  # Optimal chunk size for Whisper
            
        except ImportError as e:
            logger.error(f"Failed to import Whisper dependencies: {e}")
            raise RuntimeError("Whisper dependencies not available")
        except Exception as e:
            logger.error(f"Failed to initialize Whisper model: {e}")
            raise
    
    async def process_audio_chunk(self, audio_data: bytes) -> Optional[Dict[str, Any]]:
        """
        Process audio chunk with Whisper.
        
        Args:
            audio_data: Raw audio bytes
            
        Returns:
            Transcription result or None
        """
        # Convert bytes to numpy array
        audio_np = np.frombuffer(audio_data, dtype=np.float32)
        
        # Add to buffer
        self.buffer.add(audio_np)
        
        current_time = time.time()
        buffer_duration = self.buffer.get_duration()
        
        # Check if we should send a partial result
        # Whisper needs more audio for good results, so we wait for more data
        if (self.config.enable_partial and 
            current_time - self.last_partial_time > self.config.partial_interval and
            buffer_duration >= self.min_chunk_duration):
            
            # Get audio for partial transcription
            audio_for_partial = self.buffer.get_audio()
            if audio_for_partial is not None and len(audio_for_partial) > 0:
                # Transcribe partial audio
                text = self._transcribe_audio(audio_for_partial)
                
                self.last_partial_time = current_time
                
                if text:
                    return {
                        "type": "partial",
                        "text": text,
                        "timestamp": current_time,
                        "is_final": False,
                        "model": f"whisper-{self.config.whisper_model_size}"
                    }
        
        # Check if we have enough audio for a final chunk
        # Use optimal chunk duration for better accuracy
        if buffer_duration >= self.optimal_chunk_duration:
            # Get chunk for transcription
            audio_chunk = self.buffer.get_audio(self.optimal_chunk_duration)
            
            if audio_chunk is not None:
                # Transcribe the chunk
                text = self._transcribe_audio(audio_chunk)
                
                # Consume the buffer, keeping overlap for context
                self.buffer.consume(
                    self.optimal_chunk_duration,
                    self.config.overlap_duration
                )
                
                if text:
                    self.transcription_history.append(text)
                    return {
                        "type": "final",
                        "text": text,
                        "timestamp": current_time,
                        "is_final": True,
                        "model": f"whisper-{self.config.whisper_model_size}",
                        "language": self.config.language if self.config.language else "auto"
                    }
        
        return None
    
    def _transcribe_audio(self, audio_np: np.ndarray) -> str:
        """
        Transcribe audio using Whisper model.
        
        Args:
            audio_np: Audio data as numpy array
            
        Returns:
            Transcribed text
        """
        try:
            # Save audio to temporary file (Whisper needs file input)
            import tempfile
            import soundfile as sf
            
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                sf.write(tmp_file.name, audio_np, self.config.sample_rate)
                
                # Transcribe using Whisper
                segments_raw, info = self.model.transcribe(
                    tmp_file.name,
                    **self.transcribe_options
                )
                
                # Collect all text from segments
                text_parts = []
                for segment in segments_raw:
                    text_parts.append(segment.text.strip())
                
                # Clean up temp file
                Path(tmp_file.name).unlink()
                
                # Join all text parts
                text = " ".join(text_parts)
                
                # Log detected language if auto-detecting
                if self.config.auto_detect_language and hasattr(info, 'language'):
                    logger.debug(f"Detected language: {info.language} (confidence: {info.language_probability:.2f})")
                
                return text
                
        except Exception as e:
            logger.error(f"Error during Whisper transcription: {e}")
            return ""


class UnifiedStreamingTranscriber:
    """
    Factory and unified interface for streaming transcribers.
    
    Automatically selects the appropriate transcriber based on configuration.
    """
    
    def __init__(self, config: UnifiedStreamingConfig):
        """Initialize unified transcriber."""
        self.config = config
        self.transcriber = None
        
    def initialize(self):
        """Initialize the appropriate transcriber."""
        model_lower = self.config.model.lower()
        
        if model_lower == 'canary':
            self.transcriber = CanaryStreamingTranscriber(self.config)
        elif model_lower == 'whisper':
            self.transcriber = WhisperStreamingTranscriber(self.config)
        else:  # Default to Parakeet
            self.transcriber = ParakeetStreamingTranscriber(self.config)
        
        self.transcriber.initialize()
        logger.info(f"Initialized {self.config.model} transcriber")
    
    async def process_audio_chunk(self, audio_data: bytes) -> Optional[Dict[str, Any]]:
        """Process audio chunk with selected transcriber."""
        if not self.transcriber:
            raise RuntimeError("Transcriber not initialized")
        return await self.transcriber.process_audio_chunk(audio_data)
    
    def get_full_transcript(self) -> str:
        """Get complete transcript."""
        if not self.transcriber:
            return ""
        return self.transcriber.get_full_transcript()
    
    def reset(self):
        """Reset transcriber state."""
        if self.transcriber:
            self.transcriber.reset()
    
    def cleanup(self):
        """Clean up resources."""
        if self.transcriber:
            self.transcriber.cleanup()
        self.transcriber = None


async def handle_unified_websocket(
    websocket,
    config: Optional[UnifiedStreamingConfig] = None
):
    """
    Handle WebSocket connection for unified real-time transcription.
    
    This handler supports both Parakeet and Canary models with dynamic selection.
    
    Args:
        websocket: WebSocket connection
        config: Initial streaming configuration
    """
    logger.info("=== handle_unified_websocket STARTED ===")
    
    if not config:
        config = UnifiedStreamingConfig()
        logger.info("Created default config")
    else:
        logger.info(f"Received config from caller: model={config.model}, variant={config.model_variant}")
    
    logger.info(f"Initial config: model={config.model}, variant={config.model_variant}")
    transcriber = None  # Initialize transcriber after config is set
    
    try:
        # Always wait for configuration message from client
        config_received = False
        try:
            logger.info("Waiting for configuration message from client...")
            config_message = await asyncio.wait_for(websocket.receive_text(), timeout=15.0)  # Increased timeout
            # Do not log raw payload contents (may include base64 audio); log metadata only
            logger.info(f"Received message (length={len(config_message)})")
            config_data = json.loads(config_message)
            logger.info(f"Parsed config data type: {config_data.get('type')}")
            
            if config_data.get("type") == "config":
                # Update configuration
                old_variant = config.model_variant
                raw_model = config_data.get("model", "parakeet")
                # Allow combined form like "parakeet-mlx" to set variant
                if isinstance(raw_model, str) and '-' in raw_model:
                    base_model, suffix = raw_model.split('-', 1)
                    if base_model.lower() == 'parakeet' and not config_data.get("variant") and not config_data.get("model_variant"):
                        config.model = 'parakeet'
                        config.model_variant = suffix.lower()
                    else:
                        config.model = base_model
                        config.model_variant = config_data.get("variant", config_data.get("model_variant", config.model_variant))
                else:
                    config.model = raw_model
                    config.model_variant = config_data.get("variant", config_data.get("model_variant", config.model_variant))
                config.language = config_data.get("language", "en")
                config.sample_rate = config_data.get("sample_rate", 16000)
                config.auto_detect_language = config_data.get("auto_detect_language", False)
                config.chunk_duration = config_data.get("chunk_duration", 2.0)
                config.enable_partial = config_data.get("enable_partial", True)
                config.enable_vad = config_data.get("enable_vad", False)
                config.vad_threshold = config_data.get("vad_threshold", 0.5)
                
                # Whisper-specific configuration
                if config.model.lower() == "whisper":
                    config.whisper_model_size = config_data.get("whisper_model_size", "distil-large-v3")
                    config.beam_size = config_data.get("beam_size", 5)
                    config.vad_filter = config_data.get("vad_filter", False)
                    config.task = config_data.get("task", "transcribe")
                
                logger.info(f"Config updated: model={config.model}, variant changed from {old_variant} to {config.model_variant}, "
                           f"sample_rate={config.sample_rate}, chunk_duration={config.chunk_duration}")
                config_received = True
                
                # Send acknowledgment
                status_msg = {
                    "type": "status",
                    "state": "configured",
                    "model": config.model
                }
                
                if config.model.lower() == "parakeet":
                    status_msg["variant"] = config.model_variant
                elif config.model.lower() == "canary":
                    status_msg["language"] = config.language
                elif config.model.lower() == "whisper":
                    status_msg["whisper_model"] = config.whisper_model_size
                    status_msg["task"] = config.task
                    status_msg["language"] = config.language if config.language else "auto"
                
                await websocket.send_json(status_msg)
                logger.info(f"Sent config acknowledgment: {status_msg}")
            else:
                # Do not log full payload to avoid dumping base64 audio
                msg_type = config_data.get('type')
                data_len = len(config_data.get('data', '')) if isinstance(config_data.get('data'), str) else 0
                logger.warning(f"Received non-config message type: {msg_type} (payload length ~{data_len})")
        except asyncio.TimeoutError:
            logger.warning(f"Config message timeout after 15s. Using default configuration: model={config.model}, variant={config.model_variant}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse config message as JSON: {e}")
            logger.warning("Using default configuration due to JSON parse error")
        except Exception as e:
            logger.error(f"Unexpected error receiving config message: {e}", exc_info=True)
            logger.warning("Using default configuration due to error")
        
        if not config_received:
            logger.warning(f"No valid config received. Proceeding with: model={config.model}, variant={config.model_variant}")
        
        # Create transcriber with config
        if transcriber is None:
            logger.info(f"Creating UnifiedStreamingTranscriber for model: {config.model}")
            transcriber = UnifiedStreamingTranscriber(config)
        
        try:
            logger.info(f"Initializing transcriber for model: {config.model}")
            logger.info(f"Configuration details: model_variant={config.model_variant}, "
                       f"whisper_model_size={getattr(config, 'whisper_model_size', 'N/A')}, "
                       f"sample_rate={config.sample_rate}, language={config.language}")
            transcriber.initialize()
            logger.info(f"Transcriber initialized successfully for model: {config.model}")
        except Exception as e:
            error_msg = f"Failed to initialize {config.model} model: {str(e)}"
            logger.error(error_msg, exc_info=True)
            
            # Check if fallback to Whisper is enabled in config
            from tldw_Server_API.app.core.config import load_comprehensive_config
            comprehensive_config = load_comprehensive_config()
            
            # ConfigParser returns a ConfigParser object, not a dict
            fallback_enabled = False
            try:
                if comprehensive_config.has_section('STT-Settings'):
                    fallback_value = comprehensive_config.get('STT-Settings', 'streaming_fallback_to_whisper', fallback='false')
                    fallback_enabled = str(fallback_value).lower() == 'true'
                    logger.info(f"Streaming fallback to Whisper enabled: {fallback_enabled}")
            except Exception as config_error:
                logger.warning(f"Could not read streaming_fallback_to_whisper from config: {config_error}")
                # Defer Whisper fallback unless explicitly configured
                fallback_enabled = False
            
            # Try to fall back to Whisper if enabled and not already using Whisper
            if fallback_enabled and config.model.lower() != 'whisper':
                logger.info("Fallback to Whisper is enabled in config. Attempting to fall back...")
                try:
                    original_model = config.model
                    config.model = 'whisper'
                    config.whisper_model_size = 'distil-large-v3'
                    transcriber = UnifiedStreamingTranscriber(config)
                    transcriber.initialize()
                    logger.info("Successfully fell back to Whisper model")
                    
                    # Notify client about fallback
                    await websocket.send_json({
                        "type": "warning",
                        "message": f"{original_model} model unavailable, using Whisper instead",
                        "fallback": True,
                        "original_model": original_model,
                        "active_model": "whisper"
                    })
                except Exception as fallback_error:
                    logger.error(f"Fallback to Whisper also failed: {fallback_error}")
                    # Send error with more details
                    await websocket.send_json({
                        "type": "error",
                        "message": "No transcription models available. Please install required dependencies.",
                        "details": {
                            "original_error": str(e),
                            "fallback_error": str(fallback_error),
                            "suggestion": "Install nemo_toolkit[asr] for Parakeet/Canary or ensure faster-whisper is installed"
                        }
                    })
                    
                    # Close with error code
                    await websocket.close(code=1011, reason="No models available")
                    return
            else:
                # Fallback disabled or already using Whisper
                suggestion = ""
                if config.model.lower() in ['parakeet', 'canary']:
                    suggestion = "Install nemo_toolkit[asr]: pip install nemo_toolkit[asr]"
                elif config.model.lower() == 'whisper':
                    suggestion = "Ensure faster-whisper is installed: pip install faster-whisper"
                
                # Send error with more details
                await websocket.send_json({
                    "type": "error",
                    "message": error_msg,
                    "details": {
                        "model": config.model,
                        "error_type": type(e).__name__,
                        "error_details": str(e),
                        "fallback_enabled": fallback_enabled,
                        "suggestion": suggestion
                    }
                })
                
                # Close with error code
                await websocket.close(code=1011, reason=error_msg[:120])  # 1011 = Internal Error
                return
        
        # Send ready status
        await websocket.send_json({
            "type": "status",
            "state": "ready",
            "model": config.model
        })
        
        # Process messages
        while True:
            try:
                message = await websocket.receive_text()
                data = json.loads(message)
                
                if data.get("type") == "audio":
                    # Decode audio data
                    audio_base64 = data.get("data", "")
                    audio_bytes = base64.b64decode(audio_base64)
                    
                    # Process audio chunk
                    result = await transcriber.process_audio_chunk(audio_bytes)
                    
                    if result:
                        await websocket.send_json(result)
                
                elif data.get("type") == "commit":
                    # Get final transcript
                    full_transcript = transcriber.get_full_transcript()
                    await websocket.send_json({
                        "type": "full_transcript",
                        "text": full_transcript,
                        "timestamp": time.time()
                    })
                
                elif data.get("type") == "reset":
                    # Reset transcriber
                    transcriber.reset()
                    await websocket.send_json({
                        "type": "status",
                        "state": "reset"
                    })
                
                elif data.get("type") == "stop":
                    # Stop transcription
                    break
                    
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON message"
                })
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                await websocket.send_json({
                    "type": "error",
                    "message": f"Processing error: {str(e)}"
                })
    
    except asyncio.TimeoutError:
        await websocket.send_json({
            "type": "error",
            "message": "Configuration timeout"
        })
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected by client")
    except Exception as e:
        logger.error(f"WebSocket handler error: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "message": f"Server error: {str(e)}"
            })
        except:
            pass
    finally:
        # Clean up
        if transcriber:
            transcriber.cleanup()


# Export main components
__all__ = [
    'UnifiedStreamingConfig',
    'BaseStreamingTranscriber',
    'ParakeetStreamingTranscriber',
    'CanaryStreamingTranscriber',
    'WhisperStreamingTranscriber',
    'UnifiedStreamingTranscriber',
    'handle_unified_websocket'
]
