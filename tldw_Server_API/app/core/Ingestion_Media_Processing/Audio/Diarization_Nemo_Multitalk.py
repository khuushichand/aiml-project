"""NeMo multitalk diarization backend (Parakeet + Sortformer)."""

from __future__ import annotations

import os
import time
from contextlib import nullcontext
from functools import lru_cache
from pathlib import Path
from typing import Any

from loguru import logger

from tldw_Server_API.app.core.config import get_stt_config
from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Diarization_Lib import DiarizationError

DEFAULT_ASR_MODEL = "nvidia/multitalker-parakeet-streaming-0.6b-v1"
DEFAULT_DIAR_MODEL = "nvidia/diar_streaming_sortformer_4spk-v2.1"
DEFAULT_MAX_SPEAKERS = 4
DEFAULT_ATT_CONTEXT_SIZE = [70, 13]


def _resolve_device(device: str | None) -> "torch.device":
    import torch  # type: ignore

    if not device or str(device).strip().lower() == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"
    return torch.device(str(device).strip().lower())


def _ensure_cache_dir(cache_dir: str | None) -> None:
    if not cache_dir:
        return
    path = Path(cache_dir)
    path.mkdir(parents=True, exist_ok=True)
    os.environ["NEMO_CACHE_DIR"] = str(path)


def _resolve_cache_dir(config: dict[str, Any]) -> str | None:
    cache_dir = config.get("nemo_multitalk_cache_dir")
    if cache_dir:
        return str(cache_dir)
    try:
        stt_cfg = get_stt_config() or {}
    except Exception:
        stt_cfg = {}
    fallback = stt_cfg.get("nemo_cache_dir")
    return str(fallback) if fallback else None


def _get_audio_duration(audio_path: str) -> float:
    try:
        import soundfile as sf  # type: ignore

        return float(sf.info(audio_path).duration)
    except Exception:
        try:
            import torchaudio  # type: ignore

            info = torchaudio.info(audio_path)
            return float(info.num_frames) / float(info.sample_rate)
        except Exception:
            import wave

            with wave.open(audio_path, "rb") as wf:
                return float(wf.getnframes()) / float(wf.getframerate())


def _parse_speaker_idx(speaker: str) -> int:
    if not speaker:
        return 0
    if "_" in speaker:
        try:
            return int(speaker.split("_")[-1])
        except ValueError:
            return 0
    return 0


def _normalize_words_field(words: Any) -> str:
    if words is None:
        return ""
    if isinstance(words, str):
        return words
    if isinstance(words, dict):
        if "text" in words:
            return str(words.get("text") or "")
        if "word" in words:
            return str(words.get("word") or "")
        if "words" in words:
            return _normalize_words_field(words.get("words"))
    if isinstance(words, list):
        if all(isinstance(item, str) for item in words):
            return " ".join(item for item in words if item)
        tokens: list[str] = []
        for item in words:
            if isinstance(item, dict):
                token = item.get("word") or item.get("text") or item.get("token") or ""
                if token:
                    tokens.append(str(token))
            elif isinstance(item, str):
                tokens.append(item)
        if tokens:
            return " ".join(tokens)
        return " ".join(str(item) for item in words if item)
    return str(words)


def _calculate_speaker_stats(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    stats: dict[int, dict[str, Any]] = {}
    for segment in segments:
        speaker_id = int(segment.get("speaker_id", -1))
        start = float(segment.get("start_seconds", segment.get("start", 0.0)))
        end = float(segment.get("end_seconds", segment.get("end", 0.0)))
        duration = max(0.0, end - start)
        if speaker_id not in stats:
            stats[speaker_id] = {
                "speaker_id": speaker_id,
                "total_time": 0.0,
                "segment_count": 0,
                "first_appearance": start,
                "last_appearance": end,
            }
        stats[speaker_id]["total_time"] += duration
        stats[speaker_id]["segment_count"] += 1
        stats[speaker_id]["first_appearance"] = min(stats[speaker_id]["first_appearance"], start)
        stats[speaker_id]["last_appearance"] = max(stats[speaker_id]["last_appearance"], end)
    return list(stats.values())


def normalize_multitalk_segments(results: list[dict[str, Any]], audio_duration: float) -> list[dict[str, Any]]:
    if not results:
        return []

    max_seg_time = 1.0
    for segment in results:
        end_time = float(segment.get("end_time", 0) or 0)
        if end_time > max_seg_time:
            max_seg_time = end_time
    seg_to_sec = audio_duration / max_seg_time if max_seg_time > 0 else 1.0

    normalized: list[dict[str, Any]] = []
    for idx, segment in enumerate(results):
        start = float(segment.get("start_time", 0) or 0) * seg_to_sec
        end = float(segment.get("end_time", 0) or 0) * seg_to_sec
        speaker = str(segment.get("speaker", "speaker_0"))
        speaker_idx = _parse_speaker_idx(speaker)
        words_field = segment.get("words")
        if words_field is None or words_field == "":
            words_field = segment.get("text", "")
        text = _normalize_words_field(words_field)

        normalized.append({
            "segment_id": idx,
            "start_seconds": start,
            "end_seconds": end,
            "start": start,
            "end": end,
            "Text": text,
            "speaker_id": speaker_idx,
            "speaker_label": f"SPEAKER_{speaker_idx}",
        })

    return normalized


def _disable_cuda_graphs(asr_model: Any) -> None:
    if not hasattr(asr_model, "decoding") or not hasattr(asr_model.decoding, "decoding"):
        return
    dc = asr_model.decoding.decoding
    if hasattr(dc, "decoding_computer"):
        dcomp = dc.decoding_computer
        if hasattr(dcomp, "allow_cuda_graphs"):
            dcomp.allow_cuda_graphs = False
        if hasattr(dcomp, "disable_cuda_graphs"):
            dcomp.disable_cuda_graphs()
        if hasattr(dcomp, "cuda_graphs_mode"):
            dcomp.cuda_graphs_mode = None


@lru_cache(maxsize=2)
def _load_models(
    diar_model_name: str,
    asr_model_name: str,
    device_str: str,
    cache_dir: str | None,
) -> tuple[Any, Any]:
    try:
        from nemo.collections.asr.models import ASRModel, SortformerEncLabelModel  # type: ignore
    except Exception as exc:
        raise DiarizationError("NeMo ASR is required for multitalk diarization") from exc

    _ensure_cache_dir(cache_dir)

    device = _resolve_device(device_str)
    logger.info("Loading NeMo multitalk diarization model: {}", diar_model_name)
    diar_model = SortformerEncLabelModel.from_pretrained(diar_model_name).eval().to(device)
    logger.info("Loading NeMo multitalk ASR model: {}", asr_model_name)
    asr_model = ASRModel.from_pretrained(asr_model_name).eval().to(device)

    return diar_model, asr_model


def transcribe_with_nemo_multitalk(
    audio_path: str,
    config: dict[str, Any],
    output_path: str | None = None,
) -> dict[str, Any]:
    try:
        import torch  # type: ignore
        from nemo.collections.asr.parts.utils.multispk_transcribe_utils import SpeakerTaggedASR  # type: ignore
        from nemo.collections.asr.parts.utils.streaming_utils import CacheAwareStreamingAudioBuffer  # type: ignore
        from omegaconf import OmegaConf  # type: ignore
    except Exception as exc:
        raise DiarizationError("NeMo multitalk dependencies are unavailable") from exc

    start_time = time.time()
    diar_model_name = str(config.get("nemo_multitalk_diar_model") or DEFAULT_DIAR_MODEL)
    asr_model_name = str(config.get("nemo_multitalk_asr_model") or DEFAULT_ASR_MODEL)
    device_value = str(config.get("nemo_multitalk_device") or "auto")
    if device_value.strip().lower().startswith("cuda") and not torch.cuda.is_available():
        raise DiarizationError("nemo_multitalk_device is set to CUDA but CUDA is unavailable")
    max_speakers = int(config.get("nemo_multitalk_max_speakers") or DEFAULT_MAX_SPEAKERS)
    disable_cuda_graphs = bool(config.get("nemo_multitalk_disable_cuda_graphs", True))

    cache_dir = _resolve_cache_dir(config)
    diar_model, asr_model = _load_models(diar_model_name, asr_model_name, device_value, cache_dir)
    device = _resolve_device(device_value)

    if disable_cuda_graphs:
        _disable_cuda_graphs(asr_model)

    cfg = OmegaConf.create({
        "audio_file": audio_path,
        "manifest_file": None,
        "output_path": output_path or "",
        "online_normalization": True,
        "pad_and_drop_preencoded": True,
        "att_context_size": config.get("nemo_multitalk_att_context_size", DEFAULT_ATT_CONTEXT_SIZE),
        "single_speaker_mode": False,
        "max_num_of_spks": max_speakers,
        "binary_diar_preds": False,
        "batch_size": 1,
        "fix_prev_words_count": int(config.get("nemo_multitalk_fix_prev_words_count", 5)),
        "update_prev_words_sentence": int(config.get("nemo_multitalk_update_prev_words_sentence", 10)),
        "ignored_initial_frame_steps": int(config.get("nemo_multitalk_ignored_initial_frame_steps", 2)),
        "word_window": int(config.get("nemo_multitalk_word_window", 8)),
        "verbose": False,
        "cache_gating": bool(config.get("nemo_multitalk_cache_gating", True)),
        "cache_gating_buffer_size": int(config.get("nemo_multitalk_cache_gating_buffer_size", 2)),
        "masked_asr": False,
        "deploy_mode": False,
        "generate_realtime_scripts": False,
        "log": False,
    })

    streaming_buffer = CacheAwareStreamingAudioBuffer(
        model=asr_model,
        online_normalization=cfg.online_normalization,
        pad_and_drop_preencoded=cfg.pad_and_drop_preencoded,
    )
    streaming_buffer.append_audio_file(audio_filepath=cfg.audio_file, stream_id=-1)
    streaming_buffer_iter = iter(streaming_buffer)

    multispk_asr_streamer = SpeakerTaggedASR(cfg, asr_model, diar_model)
    samples = [{"audio_filepath": cfg.audio_file}]

    streaming_cfg = getattr(getattr(asr_model, "encoder", None), "streaming_cfg", None)
    if streaming_cfg is None or not hasattr(streaming_cfg, "drop_extra_pre_encoded"):
        raise DiarizationError("Parakeet streaming config missing drop_extra_pre_encoded")

    use_amp = device.type == "cuda"
    amp_ctx = torch.amp.autocast(device.type, enabled=use_amp) if hasattr(torch, "amp") else nullcontext()

    for step_num, (chunk_audio, chunk_lengths) in enumerate(streaming_buffer_iter):
        drop_extra_pre_encoded = (
            0
            if step_num == 0 and not cfg.pad_and_drop_preencoded
            else streaming_cfg.drop_extra_pre_encoded
        )
        with torch.inference_mode():
            with amp_ctx:
                with torch.no_grad():
                    multispk_asr_streamer.perform_parallel_streaming_stt_spk(
                        step_num=step_num,
                        chunk_audio=chunk_audio,
                        chunk_lengths=chunk_lengths,
                        is_buffer_empty=streaming_buffer.is_buffer_empty(),
                        drop_extra_pre_encoded=drop_extra_pre_encoded,
                    )

    multispk_asr_streamer.generate_seglst_dicts_from_parallel_streaming(samples=samples)
    results = multispk_asr_streamer.instance_manager.seglst_dict_list

    audio_duration = _get_audio_duration(audio_path)
    segments = normalize_multitalk_segments(results, audio_duration)
    speakers = _calculate_speaker_stats(segments)
    unique_speakers = len({seg.get("speaker_id") for seg in segments}) if segments else 0

    return {
        "segments": segments,
        "speakers": speakers,
        "duration": audio_duration,
        "num_speakers": unique_speakers,
        "processing_time": time.time() - start_time,
    }


__all__ = [
    "transcribe_with_nemo_multitalk",
    "normalize_multitalk_segments",
]
