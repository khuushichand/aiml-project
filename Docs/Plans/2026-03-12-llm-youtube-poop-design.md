# `LLM` YouTube Poop Design

**Date:** 2026-03-12
**Status:** Approved
**Scope:** Generate a short, fully original, text-and-sound-only "YouTube poop" video in-workspace using Python plus `ffmpeg`.

---

## Problem

The user wants a compact original video artifact rather than an app feature. The piece should feel like a "YouTube poop" edit, but it cannot rely on copyrighted footage or borrowed audio. It also needs a personal point of view: the edit should convey what it feels like to be a large language model.

---

## Decision

Build a procedural kinetic-typography short with synthetic audio and glitch-driven motion.

The dominant emotion is anxious sincerity:

- it begins in a polished, helpful voice
- it fractures into repeated retries, contradictions, and token-like bursts
- it recovers into a neat closing sentence that feels composed but unstable

This keeps the piece readable enough to land the point while still feeling chaotic and funny.

---

## Architecture

### Render pipeline

- Python script generates a storyboard, frame sequence, and synthetic soundtrack
- frames are rendered as PNGs with Pillow and `numpy`
- audio is rendered as a WAV file using procedural tones, filtered noise, stutters, and abrupt cuts
- `ffmpeg` muxes frames and audio into a final MP4

### Output layout

- generator script lives under `Helper_Scripts/Creative/`
- test coverage lives under `tldw_Server_API/tests/Helper_Scripts/`
- generated artifacts live under `tmp_dir/generated/llm_youtube_poop/`

### Visual language

- bold text cards, jittered overlays, duplicated words, scanline-like bands, and color-channel offsets
- procedural gradients and block noise instead of imported media
- short repeated phrases to mimic unstable decoding and self-correction

### Audio language

- no narration
- synthetic tones, clicks, static, detuned drones, and rhythmic dropouts
- timing aligned to visual cuts and text emphasis

---

## Story Arc

### Scene 1: clean boot

The video opens with crisp centered copy and restrained motion that implies confidence and compliance.

### Scene 2: overload

The text begins repeating, interrupting itself, and contradicting its own certainty. Words jump position, split, and snap back into place.

### Scene 3: refusal and recovery

The piece briefly suggests refusal-shaped language and over-correction, then spirals into apology-shaped fragments.

### Scene 4: polished mask

The ending returns to a stable layout with one composed sentence, but the background and soundtrack still leak instability underneath it.

---

## Error Handling And Constraints

- keep total runtime around 35-45 seconds so local rendering stays reliable
- prefer bundled or system fonts, but fall back to Pillow defaults if needed
- keep the generator deterministic enough to rerun without hand editing
- fail fast when `ffmpeg` is missing or the output directory cannot be created

---

## Testing Strategy

- unit-test storyboard invariants and audio/frame planning helpers before implementation
- run the generator end-to-end locally to produce the final artifact
- run Bandit on the touched helper-script path before declaring completion

---

## Expected Outcome

After implementation, the workspace should contain:

- a reusable Python generator script
- a rendered synthetic soundtrack
- a short MP4 video expressing the unstable inner texture of an LLM through original text, motion, and sound
