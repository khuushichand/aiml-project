## Stage 1: Discovery & Design
**Goal**: Identify integration points for a new PocketTTS ONNX provider.
**Success Criteria**: Adapter shape, config keys, and validation updates are scoped with minimal assumptions.
**Tests**: None.
**Status**: Complete

## Stage 2: Core Implementation
**Goal**: Add PocketTTS ONNX adapter and wire it into registry/config/validation.
**Success Criteria**: Provider resolves from model names, config is loadable, and adapter can initialize when deps/models exist.
**Tests**: Unit tests for adapter mapping/capabilities (no external model).
**Status**: Complete

## Stage 3: Docs & Validation
**Goal**: Update TTS docs/config examples to include PocketTTS ONNX setup.
**Success Criteria**: Config YAML and README mention PocketTTS provider and key settings.
**Tests**: None.
**Status**: Complete
