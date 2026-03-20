# TTS Provider Setup Guide (Runbook Index)

This page intentionally avoids duplicating provider setup details.
It defines where each setup workflow lives so users can choose the right depth.

Scope:
- Use [Getting Started — STT and TTS](./Getting-Started-STT_and_TTS.md) for first successful end-to-end speech requests.
- Use [TTS Providers Getting Started](./TTS_Getting_Started.md) for provider comparison and first successful synthesis.
- Use the canonical runbook below for deep provider setup, tuning, and troubleshooting.

Canonical deep runbook:
- [Docs/STT-TTS/TTS-SETUP-GUIDE.md](../../STT-TTS/TTS-SETUP-GUIDE.md)

## Table of Contents

- [Commercial Providers](#commercial-providers)
- [Local Model Providers](#local-model-providers)
- [Voice Cloning Setup](#voice-cloning-setup)
- [Setup Verification](#setup-verification)
- [Performance Optimization](#performance-optimization)
- [Troubleshooting](#troubleshooting)
- [Resource Requirements Summary](#resource-requirements-summary)
- [Best Practices](#best-practices)

## Commercial Providers

Use the commercial-provider section in the canonical runbook:
- [Commercial Providers](../../STT-TTS/TTS-SETUP-GUIDE.md#commercial-providers)

### OpenAI

- Setup and model notes: [OpenAI](../../STT-TTS/TTS-SETUP-GUIDE.md#openai)

### ElevenLabs

- Setup and verification: [ElevenLabs](../../STT-TTS/TTS-SETUP-GUIDE.md#elevenlabs)

## Local Model Providers

Use the local-provider section in the canonical runbook:
- [Local Model Providers](../../STT-TTS/TTS-SETUP-GUIDE.md#local-model-providers)

### One-Command Installers (Recommended)

- Installer commands and flags: [One-Command Installers](../../STT-TTS/TTS-SETUP-GUIDE.md#one-command-installers-recommended)

### Model Auto-Download Controls

- Auto-download controls and environment flags: [Model Auto-Download Controls](../../STT-TTS/TTS-SETUP-GUIDE.md#model-auto-download-controls)

### Qwen3-TTS Setup

- Full setup and caveats: [Qwen3-TTS Setup](../../STT-TTS/TTS-SETUP-GUIDE.md#qwen3-tts-setup)

### LuxTTS Setup

- Full setup and dependencies: [LuxTTS Setup](../../STT-TTS/TTS-SETUP-GUIDE.md#luxtts-setup)

### Kokoro Setup

- Full setup and phonemizer notes: [Kokoro Setup](../../STT-TTS/TTS-SETUP-GUIDE.md#kokoro-setup)

### PocketTTS ONNX Setup

- Full setup and model requirements: [PocketTTS ONNX Setup](../../STT-TTS/TTS-SETUP-GUIDE.md#pockettts-onnx-setup)

### Higgs Audio V2 Setup

- Full setup and GPU guidance: [Higgs Audio V2 Setup](../../STT-TTS/TTS-SETUP-GUIDE.md#higgs-audio-v2-setup)

### Chatterbox Setup

- Full setup and voice cloning notes: [Chatterbox Setup](../../STT-TTS/TTS-SETUP-GUIDE.md#chatterbox-setup)

### Dia Setup

- Full setup and dialogue-specific notes: [Dia Setup](../../STT-TTS/TTS-SETUP-GUIDE.md#dia-setup)

### VibeVoice Setup (Community Reference)

- Full setup and model choices: [VibeVoice Setup](../../STT-TTS/TTS-SETUP-GUIDE.md#vibevoice-setup-community-reference)

## Voice Cloning Setup

Use the canonical voice-cloning section:
- [Voice Cloning Setup](../../STT-TTS/TTS-SETUP-GUIDE.md#voice-cloning-setup)
- [Preparing Voice Reference Audio](../../STT-TTS/TTS-SETUP-GUIDE.md#preparing-voice-reference-audio)
- [Using Voice Cloning via API](../../STT-TTS/TTS-SETUP-GUIDE.md#using-voice-cloning-via-api)

## Setup Verification

Run verification/smoke tests from:
- [Setup Verification](../../STT-TTS/TTS-SETUP-GUIDE.md#setup-verification)
- [Quick Test for Each Provider](../../STT-TTS/TTS-SETUP-GUIDE.md#quick-test-for-each-provider)

## Performance Optimization

Performance guidance is maintained in:
- [Performance Optimization](../../STT-TTS/TTS-SETUP-GUIDE.md#performance-optimization)
- [GPU Acceleration](../../STT-TTS/TTS-SETUP-GUIDE.md#gpu-acceleration)
- [CPU Optimization](../../STT-TTS/TTS-SETUP-GUIDE.md#cpu-optimization)

## Troubleshooting

Troubleshooting details are maintained in:
- [Troubleshooting](../../STT-TTS/TTS-SETUP-GUIDE.md#troubleshooting)
- [Common Issues](../../STT-TTS/TTS-SETUP-GUIDE.md#common-issues)
- [Health Check](../../STT-TTS/TTS-SETUP-GUIDE.md#health-check)

## Resource Requirements Summary

See:
- [Resource Requirements Summary](../../STT-TTS/TTS-SETUP-GUIDE.md#resource-requirements-summary)

## Best Practices

See:
- [Best Practices](../../STT-TTS/TTS-SETUP-GUIDE.md#best-practices)
