# voice_manager.py
# Description: Voice management service for handling custom voice uploads and processing
#
# Imports
import asyncio
import hashlib
import json
import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
#
# Third-party Imports
import aiofiles
from loguru import logger
from pydantic import BaseModel, Field, field_validator
#
# Local Imports
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.app.core.Utils.pydantic_compat import model_dump_compat
from .tts_exceptions import (
    TTSError,
    TTSInvalidInputError,
    TTSResourceError
)
from .utils import parse_bool
#
#######################################################################################################################
#
# Voice Management Classes and Service

# Provider requirements for voice samples
PROVIDER_REQUIREMENTS = {
    "vibevoice": {
        "formats": [".wav", ".mp3", ".flac", ".ogg"],
        "max_size_mb": 50,
        "duration": {"min": 0.1, "max": 600},  # 0.1s to 10 minutes
        "sample_rate": 22050,
        "convert_to": "wav"
    },
    "higgs": {
        "formats": [".wav", ".mp3"],
        "max_size_mb": 10,
        "duration": {"min": 3, "max": 10},
        "sample_rate": 16000,
        "convert_to": "wav"
    },
    "chatterbox": {
        "formats": [".wav", ".mp3"],
        "max_size_mb": 20,
        "duration": {"min": 5, "max": 20},
        "sample_rate": 22050,
        "convert_to": "wav"
    },
    "elevenlabs": {
        "formats": [".wav", ".mp3"],
        "max_size_mb": 10,
        "duration": {"min": 1, "max": 30},
        "sample_rate": 44100,
        "convert_to": "mp3"
    },
    "neutts": {
        "formats": [".wav", ".mp3", ".flac", ".ogg", ".m4a", ".opus"],
        "max_size_mb": 20,
        "duration": {"min": 3, "max": 15},
        "sample_rate": 16000,
        "convert_to": "wav"
    }
}

# Rate limiting configuration
VOICE_RATE_LIMITS = {
    "upload_per_hour": 5,
    "total_storage_mb": 500,
    "concurrent_processing": 2,
    "max_voices_per_user": 50
}

DEFAULT_NEUTTS_VOICE_ID = "default"
_REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_NEUTTS_VOICE_PATH = (
    _REPO_ROOT / "Helper_Scripts" / "Audio" / "Sample_Voices" / "Sample_Voice_1.wav"
)
DEFAULT_NEUTTS_VOICE_TEXT_PATH = DEFAULT_NEUTTS_VOICE_PATH.with_suffix(".txt")


class VoiceUploadRequest(BaseModel):
    """Request model for voice upload"""
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    provider: str = Field(default="vibevoice")
    reference_text: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Optional transcript of the reference audio for cloning providers.",
    )

    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        # Remove any path traversal attempts
        if any(char in v for char in ['/', '\\', '..', '~']):
            raise ValueError("Voice name contains invalid characters")
        return v.strip()


class VoiceInfo(BaseModel):
    """Information about a voice sample"""
    voice_id: str
    name: str
    description: Optional[str] = None
    file_path: str
    format: str
    duration: float
    sample_rate: Optional[int] = None
    size_bytes: int
    provider: str
    created_at: datetime
    file_hash: str


class VoiceUploadResponse(BaseModel):
    """Response model for voice upload"""
    voice_id: str
    name: str
    file_path: str
    duration: float
    format: str
    provider_compatible: bool
    warnings: List[str] = []
    info: str = ""


class VoiceReferenceMetadata(BaseModel):
    """Stored metadata and provider artifacts for a voice reference."""
    voice_id: str
    reference_text: Optional[str] = None
    provider_artifacts: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def touch(self) -> None:
        self.updated_at = datetime.utcnow()


class VoiceEncodeResult(BaseModel):
    """Result of encoding provider-specific artifacts for a stored voice."""
    voice_id: str
    provider: str
    cached: bool = False
    ref_codes_len: Optional[int] = None
    reference_text: Optional[str] = None


class VoiceProcessingError(TTSError):
    """Base exception for voice processing errors"""
    pass


class VoiceFormatError(VoiceProcessingError):
    """Invalid audio format error"""
    pass


class VoiceDurationError(VoiceProcessingError):
    """Voice duration outside acceptable range"""
    pass


class VoiceQuotaExceededError(VoiceProcessingError):
    """User exceeded voice storage quota"""
    pass


class VoiceFileValidator:
    """Validates voice file uploads"""

    ALLOWED_EXTENSIONS = {'.wav', '.mp3', '.flac', '.ogg', '.m4a', '.opus'}
    ALLOWED_MIME_TYPES = {
        'audio/wav', 'audio/x-wav', 'audio/wave',
        'audio/mpeg', 'audio/mp3',
        'audio/flac', 'audio/x-flac',
        'audio/ogg', 'application/ogg',
        'audio/mp4', 'audio/x-m4a',
        'audio/opus'
    }
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB default

    @staticmethod
    def validate_filename(filename: str) -> Tuple[bool, str]:
        """Validate and sanitize filename"""
        if not filename:
            return False, "No filename provided"

        # Get extension
        ext = Path(filename).suffix.lower()
        if ext not in VoiceFileValidator.ALLOWED_EXTENSIONS:
            return False, f"File type {ext} not allowed. Allowed types: {', '.join(VoiceFileValidator.ALLOWED_EXTENSIONS)}"

        # Sanitize filename
        safe_name = "".join(c for c in filename if c.isalnum() or c in '._- ')
        safe_name = safe_name.replace(' ', '_')

        return True, safe_name

    @staticmethod
    def validate_file_size(size_bytes: int, provider: str = "vibevoice") -> Tuple[bool, str]:
        """Validate file size for provider"""
        max_size = PROVIDER_REQUIREMENTS.get(provider, {}).get("max_size_mb", 50) * 1024 * 1024

        if size_bytes > max_size:
            return False, f"File size {size_bytes / 1024 / 1024:.1f}MB exceeds limit of {max_size / 1024 / 1024}MB"

        if size_bytes == 0:
            return False, "File is empty"

        return True, ""

    @staticmethod
    def sanitize_path(base_path: Path, filename: str) -> Path:
        """Ensure path is safe and within base directory"""
        # Remove any path components from filename
        safe_name = Path(filename).name
        full_path = base_path / safe_name

        # Resolve to absolute path and check it's within base
        try:
            full_path = full_path.resolve()
            base_path = base_path.resolve()
            full_path.relative_to(base_path)
        except (ValueError, RuntimeError) as e:
            raise VoiceProcessingError(f"Invalid file path: {e}")

        return full_path


class VoiceRegistry:
    """In-memory registry for voice samples"""

    def __init__(self):
        self.user_voices: Dict[int, Dict[str, VoiceInfo]] = {}
        self._lock = asyncio.Lock()

    async def register_voice(self, user_id: int, voice_info: VoiceInfo):
        """Register a voice in the runtime registry"""
        async with self._lock:
            if user_id not in self.user_voices:
                self.user_voices[user_id] = {}

            self.user_voices[user_id][voice_info.voice_id] = voice_info
            logger.info(f"Registered voice {voice_info.name} ({voice_info.voice_id}) for user {user_id}")

    async def get_voice(self, user_id: int, voice_id: str) -> Optional[VoiceInfo]:
        """Get voice info from registry"""
        async with self._lock:
            return self.user_voices.get(user_id, {}).get(voice_id)

    async def list_voices(self, user_id: int) -> List[VoiceInfo]:
        """List all voices for a user"""
        async with self._lock:
            return list(self.user_voices.get(user_id, {}).values())

    async def remove_voice(self, user_id: int, voice_id: str) -> bool:
        """Remove voice from registry"""
        async with self._lock:
            if user_id in self.user_voices and voice_id in self.user_voices[user_id]:
                del self.user_voices[user_id][voice_id]
                logger.info(f"Removed voice {voice_id} for user {user_id}")
                return True
            return False

    async def clear_user_voices(self, user_id: int):
        """Clear all voices for a user"""
        async with self._lock:
            if user_id in self.user_voices:
                del self.user_voices[user_id]
                logger.info(f"Cleared all voices for user {user_id}")


class VoiceManager:
    """Main voice management service"""

    def __init__(self):
        self.registry = VoiceRegistry()
        self.processing_queue = asyncio.Queue()
        self.cleanup_interval = 3600  # 1 hour
        self.user_upload_counts: Dict[int, List[datetime]] = {}
        self._processing_tasks: Dict[str, asyncio.Task] = {}

    def get_user_voices_path(self, user_id: int) -> Path:
        """Get the voices directory path for a user.

        Uses DatabasePaths to resolve `<USER_DB_BASE_DIR>/<user_id>/voices`.
        """
        voices_dir = DatabasePaths.get_user_voices_dir(user_id)
        sample_root = DEFAULT_NEUTTS_VOICE_PATH.parent.resolve()
        try:
            voices_dir.resolve().relative_to(sample_root)
        except ValueError:
            return voices_dir
        fallback_base = (_REPO_ROOT / "Databases" / "user_databases").resolve()
        logger.warning(
            "Voices directory resolved under Sample_Voices; falling back to %s",
            fallback_base,
        )
        return DatabasePaths.get_user_voices_dir(
            user_id,
            base_dir_override=fallback_base,
        )

    def get_user_voice_metadata_path(self, user_id: int, voice_id: str) -> Path:
        """Get the metadata path for a stored voice reference."""
        voices_path = self.get_user_voices_path(user_id)
        metadata_dir = voices_path / "metadata"
        metadata_dir.mkdir(parents=True, exist_ok=True)
        return metadata_dir / f"{voice_id}.json"

    async def load_reference_metadata(
        self, user_id: int, voice_id: str
    ) -> Optional[VoiceReferenceMetadata]:
        """Load stored reference metadata if it exists."""
        path = self.get_user_voice_metadata_path(user_id, voice_id)
        if not path.exists():
            return None
        try:
            async with aiofiles.open(path, "r") as f:
                raw = await f.read()
            data = json.loads(raw)
            return VoiceReferenceMetadata(**data)
        except Exception as e:
            logger.warning(f"Failed to read voice metadata {path}: {e}")
            return None

    async def save_reference_metadata(
        self, user_id: int, metadata: VoiceReferenceMetadata
    ) -> None:
        """Persist reference metadata for a voice."""
        metadata.touch()
        path = self.get_user_voice_metadata_path(user_id, metadata.voice_id)
        try:
            payload = model_dump_compat(metadata)
            async with aiofiles.open(path, "w") as f:
                await f.write(json.dumps(payload, ensure_ascii=True, indent=2, default=str))
        except Exception as e:
            logger.warning(f"Failed to write voice metadata {path}: {e}")

    async def ensure_default_voice(self, user_id: int) -> Optional[VoiceInfo]:
        """Ensure the bundled default NeuTTS voice exists for a user."""
        existing = await self.registry.get_voice(user_id, DEFAULT_NEUTTS_VOICE_ID)
        if existing:
            return existing

        voices_path = self.get_user_voices_path(user_id)
        processed_path = voices_path / "processed"
        for ext in sorted(VoiceFileValidator.ALLOWED_EXTENSIONS):
            candidate = processed_path / f"{DEFAULT_NEUTTS_VOICE_ID}{ext}"
            if candidate.exists():
                voice_info = await self._build_voice_info_from_file(
                    voice_id=DEFAULT_NEUTTS_VOICE_ID,
                    name="Default",
                    description="Bundled NeuTTS default voice",
                    provider="neutts",
                    voices_path=voices_path,
                    audio_path=candidate,
                )
                await self.registry.register_voice(user_id, voice_info)
                return voice_info

        if not DEFAULT_NEUTTS_VOICE_PATH.exists():
            logger.debug(
                f"Default NeuTTS voice not found at {DEFAULT_NEUTTS_VOICE_PATH}"
            )
            return None

        try:
            processed_file = await self._process_for_provider(
                DEFAULT_NEUTTS_VOICE_PATH,
                processed_path / f"{DEFAULT_NEUTTS_VOICE_ID}.wav",
                "neutts",
            )
            voice_info = await self._build_voice_info_from_file(
                voice_id=DEFAULT_NEUTTS_VOICE_ID,
                name="Default",
                description="Bundled NeuTTS default voice",
                provider="neutts",
                voices_path=voices_path,
                audio_path=processed_file,
            )
            await self.registry.register_voice(user_id, voice_info)

            reference_text = None
            if DEFAULT_NEUTTS_VOICE_TEXT_PATH.exists():
                try:
                    async with aiofiles.open(DEFAULT_NEUTTS_VOICE_TEXT_PATH, "r") as f:
                        reference_text = (await f.read()).strip() or None
                except Exception as e:
                    logger.warning(f"Failed to read default voice reference text: {e}")

            if reference_text:
                metadata = VoiceReferenceMetadata(
                    voice_id=DEFAULT_NEUTTS_VOICE_ID,
                    reference_text=reference_text,
                )
                await self.save_reference_metadata(user_id, metadata)
                try:
                    await self.encode_voice_reference(
                        user_id=user_id,
                        voice_id=DEFAULT_NEUTTS_VOICE_ID,
                        provider="neutts",
                        reference_text=reference_text,
                        force=False,
                    )
                except VoiceProcessingError as e:
                    logger.warning(f"Default NeuTTS auto-encode failed: {e}")

            return voice_info
        except Exception as e:
            logger.warning(f"Failed to register default NeuTTS voice: {e}")
            return None

    async def _build_voice_info_from_file(
        self,
        *,
        voice_id: str,
        name: str,
        description: Optional[str],
        provider: str,
        voices_path: Path,
        audio_path: Path,
    ) -> VoiceInfo:
        duration = await self._get_audio_duration(audio_path)
        provider_reqs = PROVIDER_REQUIREMENTS.get(provider, {})
        try:
            with open(audio_path, "rb") as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()
        except Exception:
            file_hash = ""
        return VoiceInfo(
            voice_id=voice_id,
            name=name,
            description=description,
            file_path=str(audio_path.relative_to(voices_path)),
            format=audio_path.suffix[1:],
            duration=duration,
            sample_rate=provider_reqs.get("sample_rate"),
            size_bytes=audio_path.stat().st_size,
            provider=provider,
            created_at=datetime.utcnow(),
            file_hash=file_hash,
        )

    async def _get_voice_info(self, user_id: int, voice_id: str) -> Optional[VoiceInfo]:
        voice = await self.registry.get_voice(user_id, voice_id)
        if voice:
            return voice
        # Populate registry from disk if needed
        await self.list_user_voices(user_id)
        return await self.registry.get_voice(user_id, voice_id)

    async def _get_voice_audio_path(self, user_id: int, voice_id: str) -> Path:
        voice_info = await self._get_voice_info(user_id, voice_id)
        if not voice_info:
            raise VoiceProcessingError(f"Voice not found: {voice_id}")
        voices_path = self.get_user_voices_path(user_id)
        audio_path = (voices_path / voice_info.file_path).resolve()
        try:
            audio_path.relative_to(voices_path.resolve())
        except Exception as e:
            raise VoiceProcessingError(f"Invalid voice path for {voice_id}: {e}") from e
        if not audio_path.exists():
            raise VoiceProcessingError(f"Voice file missing for {voice_id}")
        return audio_path

    async def load_voice_reference_audio(self, user_id: int, voice_id: str) -> bytes:
        """Load stored voice reference audio bytes."""
        if voice_id == DEFAULT_NEUTTS_VOICE_ID:
            await self.ensure_default_voice(user_id)
        audio_path = await self._get_voice_audio_path(user_id, voice_id)
        try:
            async with aiofiles.open(audio_path, "rb") as f:
                return await f.read()
        except Exception as e:
            logger.error(f"Failed to read voice audio for {voice_id}: {e}")
            raise VoiceProcessingError(f"Failed to read voice audio for {voice_id}") from e

    async def check_rate_limits(self, user_id: int) -> Tuple[bool, str]:
        """Check if user is within rate limits"""
        now = datetime.utcnow()
        hour_ago = now - timedelta(hours=1)

        # Clean old entries and count recent uploads
        if user_id not in self.user_upload_counts:
            self.user_upload_counts[user_id] = []

        self.user_upload_counts[user_id] = [
            dt for dt in self.user_upload_counts[user_id]
            if dt > hour_ago
        ]

        if len(self.user_upload_counts[user_id]) >= VOICE_RATE_LIMITS["upload_per_hour"]:
            return False, f"Rate limit exceeded: {VOICE_RATE_LIMITS['upload_per_hour']} uploads per hour"

        # Check total storage
        voices_path = self.get_user_voices_path(user_id)
        total_size = sum(
            f.stat().st_size for f in voices_path.rglob("*") if f.is_file()
        )

        max_storage = VOICE_RATE_LIMITS["total_storage_mb"] * 1024 * 1024
        if total_size > max_storage:
            return False, f"Storage quota exceeded: {total_size / 1024 / 1024:.1f}MB / {VOICE_RATE_LIMITS['total_storage_mb']}MB"

        # Check voice count
        voice_count = len(await self.registry.list_voices(user_id))
        if voice_count >= VOICE_RATE_LIMITS["max_voices_per_user"]:
            return False, f"Maximum voice limit reached: {VOICE_RATE_LIMITS['max_voices_per_user']} voices"

        return True, ""

    async def upload_voice(
        self,
        user_id: int,
        file_content: bytes,
        filename: str,
        request: VoiceUploadRequest
    ) -> VoiceUploadResponse:
        """Process a voice upload"""

        # Check rate limits
        can_upload, error_msg = await self.check_rate_limits(user_id)
        if not can_upload:
            raise VoiceQuotaExceededError(error_msg)

        # Validate filename
        is_valid, safe_filename = VoiceFileValidator.validate_filename(filename)
        if not is_valid:
            raise VoiceFormatError(safe_filename)

        # Validate file size
        is_valid, error_msg = VoiceFileValidator.validate_file_size(len(file_content), request.provider)
        if not is_valid:
            raise VoiceProcessingError(error_msg)

        # Generate unique ID
        voice_id = str(uuid.uuid4())

        # Save original file
        voices_path = self.get_user_voices_path(user_id)
        uploads_dir = voices_path / "uploads"
        upload_path = VoiceFileValidator.sanitize_path(
            uploads_dir,
            f"{voice_id}_{safe_filename}"
        )

        try:
            async with aiofiles.open(upload_path, 'wb') as f:
                await f.write(file_content)

            logger.info(f"Saved uploaded voice file: {upload_path}")

            # Calculate file hash
            file_hash = hashlib.sha256(file_content).hexdigest()

            # Get audio duration (simplified - in production use ffprobe or similar)
            duration = await self._get_audio_duration(upload_path)

            # Validate duration for provider
            provider_reqs = PROVIDER_REQUIREMENTS.get(request.provider, {})
            min_duration = provider_reqs.get("duration", {}).get("min", 0)
            max_duration = provider_reqs.get("duration", {}).get("max", float('inf'))

            warnings = []
            if duration < min_duration:
                warnings.append(f"Audio duration {duration:.1f}s is less than recommended {min_duration}s for {request.provider}")
            elif duration > max_duration:
                warnings.append(f"Audio duration {duration:.1f}s exceeds maximum {max_duration}s for {request.provider}")

            # Optional strict enforcement for production deployments: when
            # TTS_VOICE_STRICT_DURATION is truthy, reject uploads that fall
            # outside the recommended duration range instead of only warning.
            if warnings and parse_bool(os.getenv("TTS_VOICE_STRICT_DURATION"), default=False):
                raise VoiceDurationError(
                    f"Voice sample duration {duration:.1f}s is outside the recommended "
                    f"range [{min_duration}, {max_duration}] seconds for provider '{request.provider}'"
                )

            # Process for provider (convert format if needed)
            processed_path = await self._process_for_provider(
                upload_path,
                voices_path / "processed" / f"{voice_id}.wav",
                request.provider
            )

            # Create voice info
            voice_info = VoiceInfo(
                voice_id=voice_id,
                name=request.name,
                description=request.description,
                file_path=str(processed_path.relative_to(voices_path)),
                format=processed_path.suffix[1:],
                duration=duration,
                sample_rate=provider_reqs.get("sample_rate"),
                size_bytes=processed_path.stat().st_size,
                provider=request.provider,
                created_at=datetime.utcnow(),
                file_hash=file_hash
            )

            # Register voice
            await self.registry.register_voice(user_id, voice_info)

            # Store optional reference metadata
            if request.reference_text:
                metadata = VoiceReferenceMetadata(
                    voice_id=voice_id,
                    reference_text=request.reference_text.strip() or None,
                )
                await self.save_reference_metadata(user_id, metadata)
                if (request.provider or "").strip().lower() == "neutts":
                    try:
                        await self.encode_voice_reference(
                            user_id=user_id,
                            voice_id=voice_id,
                            provider="neutts",
                            reference_text=metadata.reference_text,
                            force=False,
                        )
                    except VoiceProcessingError as e:
                        warnings.append(f"NeuTTS auto-encode failed: {e}")

            # Update upload count
            self.user_upload_counts[user_id].append(datetime.utcnow())

            return VoiceUploadResponse(
                voice_id=voice_id,
                name=request.name,
                file_path=str(processed_path),
                duration=duration,
                format=voice_info.format,
                provider_compatible=len(warnings) == 0,
                warnings=warnings,
                info=f"Voice '{request.name}' uploaded successfully for {request.provider}"
            )

        except VoiceProcessingError:
            # Clean up on error but preserve the specific voice processing
            # exception type (e.g., VoiceDurationError) so API layers can
            # distinguish between validation and generic failures.
            if upload_path.exists():
                upload_path.unlink()
            raise
        except Exception as e:
            # Clean up on error
            if upload_path.exists():
                upload_path.unlink()
            logger.error(f"Failed to upload voice: {e}")
            raise VoiceProcessingError(f"Failed to process voice upload: {str(e)}")

    async def encode_voice_reference(
        self,
        user_id: int,
        voice_id: str,
        provider: str,
        reference_text: Optional[str] = None,
        force: bool = False,
    ) -> VoiceEncodeResult:
        """Encode provider-specific artifacts for a stored voice reference."""
        provider_key = (provider or "").strip().lower()
        if not provider_key:
            raise VoiceProcessingError("Provider is required for voice encoding")

        metadata = await self.load_reference_metadata(user_id, voice_id)
        if metadata is None:
            metadata = VoiceReferenceMetadata(voice_id=voice_id)

        if reference_text:
            metadata.reference_text = reference_text.strip() or None

        existing = metadata.provider_artifacts.get(provider_key)
        if existing and not force:
            ref_codes = existing.get("ref_codes")
            return VoiceEncodeResult(
                voice_id=voice_id,
                provider=provider_key,
                cached=True,
                ref_codes_len=len(ref_codes) if isinstance(ref_codes, list) else None,
                reference_text=existing.get("reference_text") or metadata.reference_text,
            )

        audio_path = await self._get_voice_audio_path(user_id, voice_id)

        if provider_key == "neutts":
            ref_text = metadata.reference_text
            if not ref_text:
                raise VoiceProcessingError("reference_text is required to encode NeuTTS ref_codes")
            ref_codes = await self._encode_neutts_reference(audio_path)
            metadata.provider_artifacts[provider_key] = {
                "ref_codes": ref_codes,
                "reference_text": ref_text,
            }
            await self.save_reference_metadata(user_id, metadata)
            return VoiceEncodeResult(
                voice_id=voice_id,
                provider=provider_key,
                cached=False,
                ref_codes_len=len(ref_codes),
                reference_text=ref_text,
            )

        raise VoiceProcessingError(f"Provider not supported for encoding: {provider_key}")

    async def _encode_neutts_reference(self, audio_path: Path) -> List[int]:
        """Encode NeuTTS reference codes from a stored audio file."""
        try:
            from tldw_Server_API.app.core.TTS.adapters.neutts_adapter import NeuTTSAdapter
            from tldw_Server_API.app.core.TTS.tts_config import get_tts_config_manager

            manager = get_tts_config_manager()
            provider_cfg = manager.get_provider_config("neutts")
            cfg = model_dump_compat(provider_cfg) if provider_cfg is not None else {}
            adapter = NeuTTSAdapter(config=cfg)
            await adapter.ensure_initialized()
            codes = adapter._engine.encode_reference(str(audio_path))  # type: ignore[attr-defined]
            if hasattr(codes, "tolist"):
                codes = codes.tolist()
            if not isinstance(codes, (list, tuple)):
                raise VoiceProcessingError("NeuTTS encoder returned invalid ref_codes")
            return [int(x) for x in codes]
        except VoiceProcessingError:
            raise
        except Exception as e:
            logger.error(f"NeuTTS reference encoding failed: {e}")
            raise VoiceProcessingError(f"Failed to encode NeuTTS reference: {e}") from e

    async def _get_audio_duration(self, file_path: Path) -> float:
        """Get audio file duration using ffprobe (non-blocking)."""
        cmd = [
            'ffprobe', '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            str(file_path)
        ]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10)
            except asyncio.TimeoutError:
                proc.kill()
                try:
                    await proc.communicate()
                except Exception:
                    pass
                logger.error(f"ffprobe timed out for {file_path}")
                return 0.0

            if proc.returncode == 0 and stdout:
                try:
                    return float(stdout.decode().strip())
                except (UnicodeDecodeError, ValueError) as e:
                    logger.error(f"Error parsing ffprobe output for {file_path}: {e}")
                    return 0.0

            err_msg = (stderr or b"").decode(errors="ignore") if stderr is not None else ""
            logger.warning(f"Could not determine audio duration for {file_path}: {err_msg}")
            return 0.0

        except FileNotFoundError as e:
            logger.error(f"ffprobe not found while getting audio duration: {e}")
            return 0.0
        except Exception as e:
            logger.error(f"Error getting audio duration for {file_path}: {e}")
            return 0.0

    async def _process_for_provider(self, input_path: Path, output_path: Path, provider: str) -> Path:
        """Process audio file for specific provider requirements"""
        provider_reqs = PROVIDER_REQUIREMENTS.get(provider, {})
        target_format = provider_reqs.get("convert_to", "wav")
        target_sr = provider_reqs.get("sample_rate", 22050)

        # If already in correct format and sample rate, just copy
        if input_path.suffix[1:] == target_format:
            shutil.copy2(input_path, output_path)
            return output_path

        # Convert using ffmpeg
        try:
            # Ensure output has correct extension
            output_path = output_path.with_suffix(f".{target_format}")

            cmd = [
                'ffmpeg', '-y', '-i', str(input_path),
                '-ar', str(target_sr),  # Sample rate
                '-ac', '1',  # Mono
                '-c:a', 'pcm_s16le' if target_format == 'wav' else 'libmp3lame',
                str(output_path)
            ]

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                _, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
            except asyncio.TimeoutError:
                proc.kill()
                try:
                    await proc.communicate()
                except Exception:
                    pass
                logger.error(f"FFmpeg conversion timed out for {input_path}")
                shutil.copy2(input_path, output_path)
                return output_path

            if proc.returncode != 0:
                err_msg = (stderr or b"").decode(errors="ignore") if stderr is not None else ""
                logger.error(f"FFmpeg conversion failed for {input_path}: {err_msg}")
                # Fall back to copying original
                shutil.copy2(input_path, output_path)
            else:
                logger.info(f"Converted audio to {target_format} at {target_sr}Hz")

            return output_path
        except Exception as e:
            logger.error(f"Audio conversion failed: {e}")
            # Fall back to copying original
            shutil.copy2(input_path, output_path)
            return output_path

    async def list_user_voices(self, user_id: int) -> List[VoiceInfo]:
        """List all voices for a user"""
        await self.ensure_default_voice(user_id)
        # Get from registry
        voices = await self.registry.list_voices(user_id)

        # If empty, scan filesystem
        if not voices:
            voices = await self._scan_user_voices(user_id)

        return voices

    async def _scan_user_voices(self, user_id: int) -> List[VoiceInfo]:
        """Scan filesystem for user's voices"""
        voices = []
        voices_path = self.get_user_voices_path(user_id)
        processed_path = voices_path / "processed"

        if processed_path.exists():
            for voice_file in processed_path.glob("*"):
                if voice_file.is_file() and voice_file.suffix in VoiceFileValidator.ALLOWED_EXTENSIONS:
                    try:
                        # Extract provider and voice ID from filename. By default, files are
                        # named `<voice_id>.<ext>`. For future multi-provider layouts we
                        # also support an optional `provider__voice_id.ext` pattern.
                        stem = voice_file.stem
                        provider_name = "vibevoice"
                        voice_id = stem
                        if "__" in stem:
                            maybe_provider, maybe_id = stem.split("__", 1)
                            if maybe_provider:
                                provider_name = maybe_provider.lower()
                            if maybe_id:
                                voice_id = maybe_id

                        # Get file info
                        stat = voice_file.stat()
                        duration = await self._get_audio_duration(voice_file)

                        # Create voice info
                        voice_info = VoiceInfo(
                            voice_id=voice_id,
                            name=voice_id,  # Use ID as name if not stored
                            file_path=str(voice_file.relative_to(voices_path)),
                            format=voice_file.suffix[1:],
                            duration=duration,
                            size_bytes=stat.st_size,
                            provider=provider_name,
                            created_at=datetime.fromtimestamp(stat.st_ctime),
                            file_hash=""  # Would need to calculate
                        )

                        voices.append(voice_info)

                        # Register in memory
                        await self.registry.register_voice(user_id, voice_info)

                    except Exception as e:
                        logger.error(f"Error scanning voice file {voice_file}: {e}")

        return voices

    async def delete_voice(self, user_id: int, voice_id: str) -> bool:
        """Delete a voice"""
        # Get voice info
        voice_info = await self.registry.get_voice(user_id, voice_id)
        if not voice_info:
            return False

        # Delete files
        voices_path = self.get_user_voices_path(user_id)

        # Delete processed file
        try:
            voices_base = voices_path.resolve()
            processed_file = (voices_path / voice_info.file_path).resolve()
            processed_file.relative_to(voices_base)
        except (ValueError, RuntimeError) as e:
            logger.error(
                f"Refusing to delete voice {voice_id} for user {user_id}: invalid path "
                f"{voice_info.file_path} ({e})"
            )
            return False
        if processed_file.exists():
            processed_file.unlink()

        # Delete original upload if exists
        uploads_dir = (voices_path / "uploads").resolve()
        for upload_file in uploads_dir.glob(f"{voice_id}_*"):
            try:
                upload_file.resolve().relative_to(uploads_dir)
                upload_file.unlink()
            except (ValueError, RuntimeError):
                logger.warning(f"Skipping invalid upload file path: {upload_file}")

        # Remove from registry
        await self.registry.remove_voice(user_id, voice_id)

        logger.info(f"Deleted voice {voice_id} for user {user_id}")
        return True

    async def cleanup_temp_files(self):
        """Clean up old temporary files"""
        try:
            # Clean all user temp directories
            base_path = DatabasePaths.get_user_db_base_dir()
            if base_path.exists():
                for user_dir in base_path.iterdir():
                    if user_dir.is_dir():
                        temp_dir = user_dir / "voices" / "temp"
                        if temp_dir.exists():
                            # Remove files older than 1 hour
                            cutoff_time = datetime.utcnow().timestamp() - 3600
                            for temp_file in temp_dir.iterdir():
                                if temp_file.is_file() and temp_file.stat().st_mtime < cutoff_time:
                                    temp_file.unlink()
                                    logger.debug(f"Cleaned up temp file: {temp_file}")

        except Exception as e:
            logger.error(f"Error during temp file cleanup: {e}")

    async def start_background_tasks(self):
        """Start background processing tasks"""
        # Start cleanup task
        asyncio.create_task(self._cleanup_worker())
        logger.info("Voice manager background tasks started")

    async def _cleanup_worker(self):
        """Background worker for cleanup"""
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval)
                await self.cleanup_temp_files()
            except Exception as e:
                logger.error(f"Cleanup worker error: {e}")


# Global instance
_voice_manager: Optional[VoiceManager] = None


def get_voice_manager() -> VoiceManager:
    """Get or create the global voice manager instance"""
    global _voice_manager
    if _voice_manager is None:
        _voice_manager = VoiceManager()
    return _voice_manager


async def init_voice_manager():
    """Initialize the voice manager and start background tasks"""
    manager = get_voice_manager()
    await manager.start_background_tasks()
    logger.info("Voice manager initialized")
