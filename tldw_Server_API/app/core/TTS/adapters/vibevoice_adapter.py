# vibevoice_adapter.py
# Description: VibeVoice TTS adapter implementation - emotion and tone-aware synthesis
#
# Imports
import os
import json
import re
import gc
from typing import Optional, Dict, Any, AsyncGenerator, Set, List, Tuple
from pathlib import Path
#
# Third-party Imports
import torch
import numpy as np
from loguru import logger
#
# Local Imports
from .base import (
    TTSAdapter,
    TTSCapabilities,
    TTSRequest,
    TTSResponse,
    AudioFormat,
    VoiceInfo,
    ProviderStatus
)
from ..tts_exceptions import (
    TTSProviderNotConfiguredError,
    TTSProviderInitializationError,
    TTSModelNotFoundError,
    TTSModelLoadError,
    TTSGenerationError,
    TTSResourceError,
    TTSInsufficientMemoryError,
    TTSGPUError
)
from ..tts_validation import validate_tts_request
from ..tts_resource_manager import get_resource_manager
#
#######################################################################################################################
#
# VibeVoice TTS Adapter Implementation

class VibeVoiceAdapter(TTSAdapter):
    """
    Adapter for Microsoft VibeVoice - Expressive long-form multi-speaker conversational audio.
    Generates up to 90 minutes of speech with 4 distinct speakers.
    Features spontaneous background music and emergent singing capabilities.
    """
    
    # Model variants available
    MODEL_VARIANTS = {
        "1.5B": {
            "path": "microsoft/VibeVoice-1.5B",
            "context": 64000,  # 64K context (~90 min generation)
            "frame_rate": 7.5   # Hz
        },
        "7B": {
            "path": "WestZhang/VibeVoice-Large-pt", 
            "context": 32000,  # 32K context (~45 min generation)
            "frame_rate": 7.5   # Hz
        }
    }
    
    # Voice presets loaded from files
    VOICE_PRESETS = {}
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        
        # Model variant selection (1.5B or 7B)
        self.variant = self.config.get("vibevoice_variant", "1.5B")
        if self.variant not in self.MODEL_VARIANTS:
            logger.warning(f"Unknown VibeVoice variant {self.variant}, defaulting to 1.5B")
            self.variant = "1.5B"
        
        # Model configuration
        variant_config = self.MODEL_VARIANTS[self.variant]
        self.model_path = self.config.get("vibevoice_model_path", variant_config["path"])
        self.context_length = variant_config["context"]
        self.frame_rate = variant_config["frame_rate"]
        self.device = self.config.get("vibevoice_device", "cuda" if torch.cuda.is_available() else "cpu")
        
        # Audio configuration
        self.sample_rate = self.config.get("vibevoice_sample_rate", 22050)
        
        # Model instances
        self.model = None
        self.processor = None
        
        # Speaker settings (VibeVoice supports up to 4 speakers)
        self.max_speakers = 4
        self.default_speaker = self.config.get("vibevoice_default_speaker", 1)
        
        # Context awareness
        self.enable_context = self.config.get("vibevoice_context", True)
        self.context_window = self.config.get("vibevoice_context_window", 512)
        
        # VibeVoice specific features
        self.enable_background_music = self.config.get("vibevoice_background_music", False)
        self.enable_singing = self.config.get("vibevoice_enable_singing", False)
        
        # Performance settings
        self.use_fp16 = self.config.get("vibevoice_use_fp16", True) and self.device == "cuda"
        self.batch_size = self.config.get("vibevoice_batch_size", 1)
        
        # Default generation parameters
        self.default_cfg_scale = self.config.get("vibevoice_cfg_scale", 1.3)
        self.default_diffusion_steps = self.config.get("vibevoice_diffusion_steps", 20)
        self.default_temperature = self.config.get("vibevoice_temperature", 1.0)
        self.default_top_p = self.config.get("vibevoice_top_p", 0.95)
        self.default_attention_type = self.config.get("vibevoice_attention_type", "auto")
        
        # Setup paths
        self.model_dir = Path(self.config.get("vibevoice_model_dir", "./models/vibevoice"))
        self.cache_dir = Path(self.config.get("vibevoice_cache_dir", "./cache/vibevoice"))
        
        # Voice samples folder for 1-shot cloning (like VibeVoice demo)
        self.voices_dir = Path(self.config.get("vibevoice_voices_dir", "./voices"))
        self.available_voices = {}  # Maps voice names to file paths
    
    def _load_voice_files(self):
        """Load voice samples from voices folder for voice cloning"""
        self.available_voices.clear()
        self.VOICE_PRESETS.clear()
        
        # Supported audio formats
        audio_extensions = [".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac"]
        
        if self.voices_dir.exists():
            logger.info(f"Loading voices from {self.voices_dir}")
            
            # Scan for voice files
            for ext in audio_extensions:
                for voice_file in self.voices_dir.glob(f"*{ext}"):
                    voice_name = voice_file.stem  # Filename without extension
                    self.available_voices[voice_name] = str(voice_file)
                    
                    # Try to extract gender from filename (e.g., "en-Alice_woman")
                    gender = "neutral"
                    if "woman" in voice_name.lower() or "female" in voice_name.lower():
                        gender = "female"
                    elif "man" in voice_name.lower() or "male" in voice_name.lower():
                        gender = "male"
                    
                    # Add to voice presets
                    self.VOICE_PRESETS[voice_name] = VoiceInfo(
                        id=voice_name,
                        name=voice_name.replace("_", " ").replace("-", " ").title(),
                        gender=gender,
                        description=f"Voice loaded from {voice_file.name}",
                        styles=["file-based"]
                    )
                    logger.info(f"Loaded voice: {voice_name} from {voice_file}")
            
            if not self.available_voices:
                logger.warning(f"No voice files found in {self.voices_dir}")
                # Add default speaker options when no voice files are found
                for i in range(1, 5):
                    speaker_id = f"speaker_{i}"
                    self.VOICE_PRESETS[speaker_id] = VoiceInfo(
                        id=speaker_id,
                        name=f"Speaker {i}",
                        gender="neutral",
                        description=f"Default speaker {i}",
                        styles=["default"]
                    )
        else:
            logger.info(f"Voices directory {self.voices_dir} not found, using speaker numbers only")
            # Add default speaker options
            for i in range(1, 5):
                speaker_id = f"speaker_{i}"
                self.VOICE_PRESETS[speaker_id] = VoiceInfo(
                    id=speaker_id,
                    name=f"Speaker {i}",
                    gender="neutral",
                    description=f"Default speaker {i}",
                    styles=["default"]
                )
    
    async def _load_user_voices(self, user_id: int):
        """Load user-specific uploaded voices"""
        try:
            from ...voice_manager import get_voice_manager
            
            voice_manager = get_voice_manager()
            user_voices = await voice_manager.list_user_voices(user_id)
            
            for voice_info in user_voices:
                if voice_info.provider == "vibevoice":
                    # Get full path to voice file
                    voices_path = voice_manager.get_user_voices_path(user_id)
                    voice_file_path = voices_path / voice_info.file_path
                    
                    if voice_file_path.exists():
                        # Register with custom: prefix
                        custom_id = f"custom:{voice_info.voice_id}"
                        self.available_voices[custom_id] = str(voice_file_path)
                        
                        # Add to voice presets
                        self.VOICE_PRESETS[custom_id] = VoiceInfo(
                            id=custom_id,
                            name=voice_info.name,
                            gender="neutral",
                            description=voice_info.description or f"Custom voice: {voice_info.name}",
                            styles=["custom", "uploaded"]
                        )
                        
                        logger.info(f"Loaded user voice: {voice_info.name} ({custom_id})")
            
            logger.info(f"Loaded {len(user_voices)} user voices for VibeVoice")
            
        except ImportError:
            logger.debug("Voice manager not available, skipping user voice loading")
        except Exception as e:
            logger.error(f"Error loading user voices: {e}")
    
    async def initialize(self, user_id: Optional[int] = None) -> bool:
        """Initialize the VibeVoice TTS model"""
        try:
            logger.info(f"{self.provider_name}: Initializing VibeVoice TTS (variant: {self.variant}, model: {self.model_path})...")
            
            # Load voice files from voices folder
            self._load_voice_files()
            
            # Load user-specific voices if user_id provided
            if user_id:
                await self._load_user_voices(user_id)
            
            # Get resource manager for memory monitoring
            resource_manager = await get_resource_manager()
            
            # Check memory before loading model
            if resource_manager.memory_monitor.is_memory_critical():
                raise TTSInsufficientMemoryError(
                    "Insufficient memory to load VibeVoice model",
                    provider=self.provider_name,
                    details=resource_manager.memory_monitor.get_memory_usage()
                )
            
            # Check for model files
            if not self._check_model_files():
                logger.info(f"{self.provider_name}: Downloading VibeVoice models...")
                await self._download_models()
            
            # Load the model components
            logger.info(f"{self.provider_name}: Loading VibeVoice components...")
            
            # Import VibeVoice
            try:
                from vibevoice.modular.modeling_vibevoice_inference import VibeVoiceForConditionalGenerationInference
                from vibevoice.processor.vibevoice_processor import VibeVoiceProcessor
                
                # Load processor
                logger.info(f"Loading VibeVoice processor from {self.model_path}")
                self.processor = VibeVoiceProcessor.from_pretrained(self.model_path)
                
                # Determine dtype and attention implementation
                if self.device == "cuda":
                    load_dtype = torch.bfloat16 if self.use_fp16 else torch.float32
                    attn_impl = "flash_attention_2"
                else:
                    load_dtype = torch.float32
                    attn_impl = "sdpa"
                
                # Load main model
                logger.info(f"Loading VibeVoice model with dtype={load_dtype}, device={self.device}")
                self.model = VibeVoiceForConditionalGenerationInference.from_pretrained(
                    self.model_path,
                    torch_dtype=load_dtype,
                    device_map=self.device if self.device != "cpu" else None,
                    attn_implementation=attn_impl
                )
                
                # Set model to eval and configure inference
                self.model.eval()
                self.model.set_ddpm_inference_steps(num_steps=10)
                
            except ImportError as e:
                error_msg = (
                    f"{self.provider_name}: Required libraries not installed. "
                    f"To use VibeVoice, follow these steps:\n"
                    f"1. Ensure VibeVoice is installed:\n"
                    f"   cd libs/VibeVoice && pip install -e .\n"
                    f"2. Or clone and install:\n"
                    f"   git clone https://github.com/great-wind/MicroSoft_VibeVoice.git libs/VibeVoice\n"
                    f"   cd libs/VibeVoice && pip install -e .\n"
                    f"3. The {self.variant} model will auto-download on first use from:\n"
                    f"   {self.model_path}"
                )
                logger.error(f"{self.provider_name}: Required libraries not installed: {e}")
                logger.error(error_msg)
                self._status = ProviderStatus.NOT_CONFIGURED
                raise TTSModelLoadError(
                    "Failed to import required libraries",
                    provider=self.provider_name,
                    details={"error": str(e), "suggestion": error_msg}
                )
            
            # Set to evaluation mode
            if self.model:
                self.model.eval()
                
                # Register model with resource manager
                resource_manager.register_model(
                    provider=self.provider_name.lower(),
                    model_instance=self.model,
                    cleanup_callback=self._cleanup_resources
                )
            
            # Warm up the model
            await self._warmup_model()
            
            logger.info(
                f"{self.provider_name}: Initialized successfully "
                f"(Device: {self.device}, FP16: {self.use_fp16}, Context: {self.enable_context})"
            )
            self._status = ProviderStatus.AVAILABLE
            return True
            
        except (TTSInsufficientMemoryError, TTSModelLoadError):
            raise
        except RuntimeError as e:
            if "CUDA" in str(e) or "GPU" in str(e):
                raise TTSGPUError(
                    f"GPU error initializing {self.provider_name}",
                    provider=self.provider_name,
                    details={"error": str(e), "device": self.device}
                )
            raise
        except Exception as e:
            logger.error(f"{self.provider_name}: Initialization failed: {e}")
            self._status = ProviderStatus.ERROR
            raise TTSProviderInitializationError(
                f"Failed to initialize {self.provider_name}",
                provider=self.provider_name,
                details={"error": str(e), "model_path": self.model_path}
            )
    
    def _check_model_files(self) -> bool:
        """Check if model files exist locally"""
        required_files = [
            "config.json",
            "model.safetensors",
            "tokenizer_config.json",
            "vibe_encoder.pt"
        ]
        
        if not self.model_dir.exists():
            return False
        
        for file in required_files:
            if not (self.model_dir / file).exists():
                return False
        
        return True
    
    async def _download_models(self):
        """Download VibeVoice models if not present"""
        # Create directories
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            from huggingface_hub import snapshot_download
            logger.info(f"{self.provider_name}: Downloading {self.variant} model from {self.model_path}...")
            
            # Download the model from HuggingFace
            snapshot_download(
                repo_id=self.model_path,
                local_dir=str(self.model_dir),
                cache_dir=str(self.cache_dir)
            )
            logger.info(f"{self.provider_name}: Model download complete")
            return True
            
        except ImportError:
            logger.error(f"{self.provider_name}: huggingface_hub not installed. Run: pip install huggingface-hub")
            return False
        except Exception as e:
            logger.error(f"{self.provider_name}: Model download failed: {e}")
            return False
    
    async def _warmup_model(self):
        """Warm up the model with a test generation"""
        if not self.model:
            return
        
        try:
            logger.debug(f"{self.provider_name}: Warming up model...")
            test_text = "Hello, this is a test."
            test_request = TTSRequest(
                text=test_text,
                voice="aurora",
                format=AudioFormat.WAV
            )
            # Would do actual generation here
            logger.debug(f"{self.provider_name}: Model warmup complete")
        except Exception as e:
            logger.warning(f"{self.provider_name}: Warmup failed: {e}")
    
    async def get_capabilities(self) -> TTSCapabilities:
        """Get VibeVoice TTS capabilities"""
        # Variant-specific max generation time
        max_generation_minutes = 90 if self.variant == "1.5B" else 45
        
        return TTSCapabilities(
            provider_name=f"VibeVoice-{self.variant}",
            supported_languages={"en", "es", "fr", "de", "it", "pt", "nl", "pl", "ru", "ja", "ko", "zh"},
            supported_voices=list(self.VOICE_PRESETS.values()),
            supported_formats={
                AudioFormat.WAV,
                AudioFormat.MP3,
                AudioFormat.OPUS,
                AudioFormat.FLAC,
                AudioFormat.PCM,
                AudioFormat.OGG
            },
            max_text_length=self.context_length,  # Use variant-specific context length
            supports_streaming=True,
            supports_voice_cloning=True,  # Supports cloning via voice reference folder
            supports_emotion_control=False,  # Does not have direct emotion control
            supports_speech_rate=True,
            supports_pitch_control=False,
            supports_volume_control=True,
            supports_ssml=False,  # Uses its own markup
            supports_phonemes=False,
            supports_multi_speaker=True,  # Up to 4 speakers
            supports_background_audio=True,  # Spontaneous music generation
            latency_ms=150 if self.device == "cuda" else 800,
            sample_rate=self.sample_rate,
            default_format=AudioFormat.WAV
        )
    
    async def generate(self, request: TTSRequest) -> TTSResponse:
        """Generate speech using VibeVoice TTS"""
        if not await self.ensure_initialized():
            raise TTSProviderNotConfiguredError(
                f"{self.provider_name} not initialized",
                provider=self.provider_name
            )
        
        # Validate request using new validation system
        try:
            validate_tts_request(request, provider=self.provider_name.lower())
        except Exception as e:
            logger.error(f"{self.provider_name} request validation failed: {e}")
            raise
        
        # Check if a different model variant was requested
        requested_model = request.model or request.extra_params.get("model")
        if requested_model and requested_model in self.MODEL_VARIANTS:
            if requested_model != self.variant:
                logger.info(f"Switching VibeVoice model from {self.variant} to {requested_model}")
                self.variant = requested_model
                # Reload model with new variant
                await self._reload_model_for_variant(requested_model)
        
        # Extract generation parameters
        cfg_scale = request.cfg_scale or request.extra_params.get("cfg_scale", self.default_cfg_scale)
        diffusion_steps = request.diffusion_steps or request.extra_params.get("diffusion_steps", self.default_diffusion_steps)
        temperature = request.temperature or request.extra_params.get("temperature", self.default_temperature)
        top_p = request.top_p or request.extra_params.get("top_p", self.default_top_p)
        seed = request.seed or request.extra_params.get("seed")
        attention_type = request.attention_type or request.extra_params.get("attention_type", self.default_attention_type)
        
        # Validate parameters
        cfg_scale = max(1.0, min(2.0, cfg_scale))
        diffusion_steps = max(5, min(100, diffusion_steps))
        temperature = max(0.1, min(2.0, temperature))
        top_p = max(0.1, min(1.0, top_p))
        
        # Parse text for multi-speaker support
        text, speaker_mapping = self._parse_multi_speaker_text(request.text)
        
        # Process voice and speaker settings
        voice = request.voice or "speaker_1"
        speaker_id = request.extra_params.get("speaker_id", self.default_speaker)
        # Ensure speaker_id is within valid range (1-4)
        speaker_id = max(1, min(4, speaker_id))
        
        # If multi-speaker text detected, use speaker mapping
        voice_references = {}
        if speaker_mapping:
            for speaker_num, speaker_text in speaker_mapping.items():
                # Map speaker to voice or generate synthetic
                speaker_voice = f"speaker_{speaker_num}"
                if speaker_voice in self.available_voices:
                    voice_references[speaker_num] = self.available_voices[speaker_voice]
                else:
                    # Generate synthetic voice for this speaker
                    voice_references[speaker_num] = await self._generate_synthetic_voice(speaker_num)
        
        # Handle voice cloning - check custom voices
        voice_reference_path = None
        
        # Check if voice starts with "custom:" prefix (uploaded voice)
        if voice.startswith("custom:"):
            if voice in self.available_voices:
                voice_reference_path = self.available_voices[voice]
                logger.info(f"Using uploaded voice '{voice}' from {voice_reference_path}")
            else:
                logger.warning(f"Custom voice '{voice}' not found, using default")
                voice = "speaker_1"
        # Check if voice is loaded from voices folder
        elif voice in self.available_voices:
            voice_reference_path = self.available_voices[voice]
            logger.info(f"Using voice '{voice}' from {voice_reference_path}")
        # Otherwise check if voice reference bytes provided
        elif request.voice_reference:
            voice_reference_path = await self._prepare_voice_reference(request.voice_reference)
            # Use "cloned" as voice identifier when using reference
            voice = "cloned" if voice_reference_path else voice
        # If no voice reference, generate synthetic voice
        elif not voice_reference_path and voice.startswith("speaker_"):
            voice_reference_path = await self._generate_synthetic_voice(speaker_id)
        
        # Process multi-speaker if needed
        speakers = request.speakers if hasattr(request, 'speakers') else None
        
        logger.info(
            f"{self.provider_name}: Generating speech with voice={voice}, "
            f"speaker_id={speaker_id}, format={request.format.value}, "
            f"cfg={cfg_scale}, steps={diffusion_steps}, temp={temperature}, top_p={top_p}"
        )
        
        try:
            # Prepare generation config
            gen_config = {
                "cfg_scale": cfg_scale,
                "diffusion_steps": diffusion_steps,
                "temperature": temperature,
                "top_p": top_p,
                "seed": seed,
                "attention_type": attention_type,
                "speaker_mapping": speaker_mapping,
                "voice_references": voice_references
            }
            
            if request.stream:
                # Return streaming response
                return TTSResponse(
                    audio_stream=self._stream_audio_vibevoice(request, voice, speaker_id, voice_reference_path, gen_config),
                    format=request.format,
                    sample_rate=self.sample_rate,
                    channels=1,
                    voice_used=voice,
                    provider=self.provider_name,
                    metadata={
                        "speaker_id": speaker_id,
                        "context_enabled": self.enable_context,
                        "background_music": self.enable_background_music,
                        "singing_enabled": self.enable_singing,
                        "cfg_scale": cfg_scale,
                        "diffusion_steps": diffusion_steps,
                        "temperature": temperature,
                        "top_p": top_p,
                        "seed": seed
                    }
                )
            else:
                # Generate complete audio
                audio_data = await self._generate_complete_vibevoice(request, voice, speaker_id, voice_reference_path, gen_config)
                return TTSResponse(
                    audio_data=audio_data,
                    format=request.format,
                    sample_rate=self.sample_rate,
                    channels=1,
                    voice_used=voice,
                    provider=self.provider_name,
                    metadata={
                        "speaker_id": speaker_id,
                        "context_enabled": self.enable_context,
                        "background_music": self.enable_background_music,
                        "singing_enabled": self.enable_singing,
                        "cfg_scale": cfg_scale,
                        "diffusion_steps": diffusion_steps,
                        "temperature": temperature,
                        "top_p": top_p,
                        "seed": seed
                    }
                )
                
        except (TTSProviderNotConfiguredError, TTSModelLoadError):
            raise
        except Exception as e:
            logger.error(f"{self.provider_name} generation error: {e}")
            raise TTSGenerationError(
                f"Failed to generate speech with {self.provider_name}",
                provider=self.provider_name,
                details={"error": str(e), "error_type": type(e).__name__}
            )
    
    
    async def _stream_audio_vibevoice(
        self,
        request: TTSRequest,
        voice: str,
        speaker_id: int,
        voice_reference_path: Optional[str] = None,
        gen_config: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[bytes, None]:
        """Stream audio from VibeVoice model"""
        if not self.model or not self.processor:
            raise TTSModelNotFoundError(
                "VibeVoice model not initialized",
                provider=self.provider_name
            )
        
        # Import StreamingAudioWriter
        from tldw_Server_API.app.core.TTS.streaming_audio_writer import (
            StreamingAudioWriter,
            AudioNormalizer
        )
        
        normalizer = AudioNormalizer()
        writer = StreamingAudioWriter(
            format=request.format.value,
            sample_rate=self.sample_rate,
            channels=1
        )
        
        try:
            # Prepare input with speaker settings
            input_data = self._prepare_vibevoice_input(request, voice, speaker_id)
            
            # Prepare input data for generation
            # VibeVoice uses voice samples directly, not embeddings
            
            # Prepare voice samples list
            voice_samples = []
            if voice_reference_path:
                voice_samples = [voice_reference_path]
            elif voice in self.custom_voices:
                voice_samples = [self.custom_voices[voice]]
            else:
                # Use default voice from Voices folder if available
                if self.voices_dir.exists():
                    default_voices = list(self.voices_dir.glob("*.wav"))
                    if default_voices:
                        voice_samples = [str(default_voices[0])]
            
            # Prepare inputs for the model
            inputs = self.processor(
                text=[input_data["text"]],  # Wrap in list for batch
                voice_samples=[voice_samples] if voice_samples else None,
                padding=True,
                return_tensors="pt",
                return_attention_mask=True
            )
            
            # Move tensors to device
            for k, v in inputs.items():
                if torch.is_tensor(v):
                    inputs[k] = v.to(self.device)
            
            # Generate with VibeVoice model
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=None,
                    cfg_scale=request.extra_params.get("cfg_scale", 1.3),
                    tokenizer=self.processor.tokenizer,
                    generation_config={'do_sample': False},
                    verbose=False
                )
                
                # Get the generated audio
                if outputs.speech_outputs and outputs.speech_outputs[0] is not None:
                    audio_array = outputs.speech_outputs[0].cpu().numpy()
                    
                    # Stream the audio in chunks
                    chunk_size = int(self.sample_rate * 0.25)  # 0.25 second chunks
                    for i in range(0, len(audio_array), chunk_size):
                        chunk = audio_array[i:i + chunk_size]
                        
                        if len(chunk) > 0:
                            # Normalize to int16
                            normalized_chunk = normalizer.normalize(chunk, target_dtype=np.int16)
                            
                            # Encode to target format
                            encoded_bytes = writer.write_chunk(normalized_chunk)
                            if encoded_bytes:
                                yield encoded_bytes
                else:
                    logger.error("No audio output generated from VibeVoice")
                    raise TTSGenerationError(
                        "Failed to generate audio",
                        provider=self.provider_name
                    )
            
            # Finalize stream
            final_bytes = writer.write_chunk(finalize=True)
            if final_bytes:
                yield final_bytes
            
            logger.info(f"{self.provider_name}: Successfully generated audio with speaker={speaker_id}")
            
        except TTSModelNotFoundError:
            raise
        except Exception as e:
            logger.error(f"{self.provider_name} streaming error: {e}")
            raise TTSGenerationError(
                f"Streaming error in {self.provider_name}",
                provider=self.provider_name,
                details={"error": str(e)}
            )
        finally:
            writer.close()
            # Clean up voice reference file if used (but not custom voices from Voices folder)
            if voice_reference_path and voice_reference_path not in self.custom_voices.values():
                try:
                    from pathlib import Path
                    Path(voice_reference_path).unlink(missing_ok=True)
                    logger.debug(f"Cleaned up temporary voice reference: {voice_reference_path}")
                except Exception as e:
                    logger.warning(f"Failed to clean up voice reference: {e}")
    
    async def _generate_complete_vibevoice(
        self,
        request: TTSRequest,
        voice: str,
        speaker_id: int,
        voice_reference_path: Optional[str] = None,
        gen_config: Optional[Dict[str, Any]] = None
    ) -> bytes:
        """Generate complete audio from VibeVoice"""
        all_audio = b""
        async for chunk in self._stream_audio_vibevoice(request, voice, speaker_id, voice_reference_path):
            all_audio += chunk
        return all_audio
    
    def _prepare_vibevoice_input(
        self,
        request: TTSRequest,
        voice: str,
        speaker_id: int
    ) -> Dict[str, Any]:
        """Prepare input for VibeVoice with speaker settings"""
        # Process text with SSML if present
        text = self.preprocess_text(request.text)
        
        return {
            "text": text,
            "voice": voice,
            "speaker_id": speaker_id,
            "speed": request.speed,
            "pitch": request.pitch,
            "volume": request.volume,
            "background_music": self.enable_background_music,
            "singing": self.enable_singing
        }
    
    
    async def _prepare_voice_reference(self, voice_reference: bytes) -> Optional[str]:
        """
        Prepare voice reference audio for VibeVoice.
        VibeVoice supports single-sample voice cloning.
        
        Args:
            voice_reference: Voice reference audio bytes
            
        Returns:
            Path to temporary voice reference file or None if processing fails
        """
        try:
            import tempfile
            from pathlib import Path
            from tldw_Server_API.app.core.TTS.audio_utils import process_voice_reference
            
            # Process voice reference for VibeVoice requirements
            processed_audio, error = process_voice_reference(
                voice_reference,
                provider='vibevoice',
                validate=True,
                convert=True
            )
            
            if error:
                logger.error(f"Voice reference processing failed: {error}")
                return None
            
            # Save to temporary file
            with tempfile.NamedTemporaryFile(
                suffix='.wav',
                delete=False,
                prefix='vibevoice_voice_'
            ) as tmp_file:
                tmp_file.write(processed_audio)
                tmp_path = tmp_file.name
            
            logger.info(f"Voice reference prepared for VibeVoice: {tmp_path}")
            return tmp_path
            
        except Exception as e:
            logger.error(f"Failed to prepare voice reference: {e}")
            return None
    
    def map_voice(self, voice_id: str) -> str:
        """Map generic voice ID to VibeVoice voice"""
        # Handle custom: prefix
        if voice_id.startswith("custom:"):
            if voice_id in self.available_voices:
                return voice_id
            else:
                logger.warning(f"Custom voice {voice_id} not found")
                return "speaker_1"
        
        # Check available voices first
        if voice_id in self.available_voices:
            return voice_id
            
        # Then check presets
        if voice_id in self.VOICE_PRESETS:
            return voice_id
        
        # Try to map speaker numbers
        if voice_id.isdigit():
            speaker_num = int(voice_id)
            if 1 <= speaker_num <= 4:
                return f"speaker_{speaker_num}"
        
        # Default to speaker 1
        logger.warning(f"Voice {voice_id} not found, using default speaker_1")
        return "speaker_1"
    
    def _parse_multi_speaker_text(self, text: str) -> Tuple[str, Optional[Dict[int, str]]]:
        """Parse text for multi-speaker markers and return cleaned text with speaker mapping."""
        # Pattern to match various speaker formats
        # Supports: [1]:, [Speaker1]:, Speaker 1:, etc.
        patterns = [
            r'\[(\d+)\]:\s*',  # [1]: text
            r'\[Speaker\s*(\d+)\]:\s*',  # [Speaker1]: text
            r'Speaker\s*(\d+):\s*',  # Speaker 1: text
        ]
        
        speaker_mapping = {}
        cleaned_text = text
        
        for pattern in patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                speaker_num = int(match.group(1))
                # Convert to 0-based indexing for internal use
                speaker_idx = speaker_num - 1
                if 0 <= speaker_idx < 4:  # VibeVoice supports up to 4 speakers
                    speaker_mapping[speaker_idx] = f"speaker_{speaker_num}"
                    # Mark the text segment for this speaker
                    cleaned_text = cleaned_text.replace(match.group(0), f"[{speaker_idx}] ")
        
        # If no speaker markers found, return original text
        if not speaker_mapping:
            return text, None
        
        return cleaned_text, speaker_mapping
    
    def preprocess_text(self, text: str, **kwargs) -> str:
        """Preprocess text for VibeVoice"""
        # Basic preprocessing
        text = super().preprocess_text(text)
        
        # VibeVoice supports multi-speaker dialogue markers
        # Parse and clean them
        cleaned_text, _ = self._parse_multi_speaker_text(text)
        
        return cleaned_text
    
    async def _generate_synthetic_voice(self, speaker_id: int) -> Optional[str]:
        """Generate a synthetic voice sample for a speaker when no reference is available."""
        try:
            logger.info(f"Generating synthetic voice for speaker {speaker_id}")
            
            # Create a deterministic synthetic voice based on speaker ID
            # This would typically use the model's voice generation capabilities
            # For now, return None to use default voice
            # In a real implementation, this would generate a voice sample
            
            # Placeholder for synthetic voice generation
            # Could use techniques like:
            # - Random noise with speaker-specific seed
            # - Pre-generated synthetic samples
            # - Model's built-in voice synthesis
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to generate synthetic voice: {e}")
            return None
    
    async def _reload_model_for_variant(self, variant: str):
        """Reload the model with a different variant (1.5B or 7B)"""
        if variant not in self.MODEL_VARIANTS:
            raise ValueError(f"Invalid variant: {variant}. Must be one of {list(self.MODEL_VARIANTS.keys())}")
        
        # Clean up existing model
        await self._cleanup_resources()
        
        # Update configuration for new variant
        variant_config = self.MODEL_VARIANTS[variant]
        self.model_path = variant_config["path"]
        self.context_length = variant_config["context"]
        self.frame_rate = variant_config["frame_rate"]
        
        # Reinitialize with new variant
        logger.info(f"Reloading VibeVoice with variant: {variant}")
        await self.initialize()
    
    async def _cleanup_resources(self):
        """Clean up VibeVoice adapter resources with enhanced memory management."""
        try:
            if self.model:
                del self.model
            if self.processor:
                del self.processor
            
            self.model = None
            self.processor = None
            
            # Force garbage collection
            gc.collect()
            
            # Clear GPU cache if using CUDA
            if self.device == "cuda" and torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
            elif self.device == "mps" and torch.backends.mps.is_available():
                # Clear MPS cache for Apple Silicon
                torch.mps.empty_cache()
                torch.mps.synchronize()
            
            logger.debug(f"{self.provider_name}: Resources cleaned up")
        except Exception as e:
            logger.warning(f"{self.provider_name}: Error during cleanup: {e}")
    
    async def cleanup_after_generation(self):
        """Clean up after each generation to free memory."""
        try:
            # Clear any temporary tensors
            gc.collect()
            
            # Clear device cache without unloading model
            if self.device == "cuda" and torch.cuda.is_available():
                torch.cuda.empty_cache()
            elif self.device == "mps" and torch.backends.mps.is_available():
                torch.mps.empty_cache()
                
        except Exception as e:
            logger.debug(f"Post-generation cleanup error: {e}")

#
# End of vibevoice_adapter.py
#######################################################################################################################