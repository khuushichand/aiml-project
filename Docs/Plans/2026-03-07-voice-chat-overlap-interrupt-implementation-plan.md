# Voice Chat Overlap + Interrupt + Realtime TTS Hardening Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add low-latency overlapped LLM->TTS streaming and explicit interruption support to both voice WebSocket paths while preserving protocol backward compatibility and adding regression tests.

**Architecture:** Keep `audio/chat/stream` and `audio/stream/tts/realtime` as the public APIs, but add additive `interrupt`/`interrupted` protocol events plus connection-scoped turn/session cancellation guards. For overlap, stream LLM deltas into phrase chunks and commit them into a realtime TTS session incrementally so TTS can begin before the full assistant response is complete.

**Tech Stack:** FastAPI WebSockets, asyncio task orchestration/cancellation, existing `RealtimeTTSSession` abstractions, pytest (backend), vitest/react testing (frontend), Loguru metrics/logging.

---

**Execution Rules**

- Apply TDD for every behavior change (`@test-driven-development`).
- Verify with focused test runs before each commit (`@verification-before-completion`).
- Keep commits small and scoped per task.
- Do not change auth/quota contracts unless required by tests.

### Task 1: Add Additive Interrupt Protocol for `/audio/chat/stream` (No Active Turn)

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/audio/audio_streaming.py`
- Test: `tldw_Server_API/tests/Audio/test_ws_audio_chat_stream.py`

**Step 1: Write the failing test**

```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_audio_chat_ws_interrupt_without_active_turn_is_safe(monkeypatch):
    ws = DummyWebSocket([
        {"type": "config", "stt": {}, "llm": {"provider": "stub", "model": "m"}, "tts": {"format": "pcm"}},
        {"type": "interrupt", "reason": "user_stop"},
        {"type": "stop"},
    ])
    await audio.websocket_audio_chat_stream(ws, token=None)
    assert any(m.get("type") == "interrupted" for m in ws.sent_json)
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Audio/test_ws_audio_chat_stream.py::test_audio_chat_ws_interrupt_without_active_turn_is_safe -v`

Expected: FAIL (`interrupted` frame not found).

**Step 3: Write minimal implementation**

```python
# in websocket_audio_chat_stream message loop
elif msg_type == "interrupt":
    if _outer_stream:
        await _outer_stream.send_json({
            "type": "interrupted",
            "turn_id": None,
            "phase": "both",
            "reason": str(data.get("reason") or "client_cancel"),
        })
```

**Step 4: Run test to verify it passes**

Run: same pytest command as Step 2.

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/tests/Audio/test_ws_audio_chat_stream.py tldw_Server_API/app/api/v1/endpoints/audio/audio_streaming.py
git commit -m "test+feat(audio): add additive interrupt frame handling for idle chat stream"
```

### Task 2: Add Phrase Chunker Utility for Overlap

**Files:**
- Create: `tldw_Server_API/app/core/Streaming/phrase_chunker.py`
- Test: `tldw_Server_API/tests/Audio/test_phrase_chunker.py`

**Step 1: Write the failing tests**

```python
from tldw_Server_API.app.core.Streaming.phrase_chunker import PhraseChunker

def test_phrase_chunker_emits_on_sentence_boundary():
    c = PhraseChunker(min_chars=15, max_chars=80)
    out = c.push("Hello world. How")
    assert out == ["Hello world."]
    assert c.flush() == "How"

def test_phrase_chunker_forces_emit_on_max_chars():
    c = PhraseChunker(min_chars=5, max_chars=10)
    out = c.push("abcdefghijklmno")
    assert out
```

**Step 2: Run tests to verify they fail**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Audio/test_phrase_chunker.py -v`

Expected: FAIL (module/class missing).

**Step 3: Write minimal implementation**

```python
class PhraseChunker:
    def __init__(self, min_chars: int = 15, max_chars: int = 80): ...
    def push(self, delta: str) -> list[str]: ...
    def flush(self) -> str: ...
```

Boundary rules:
- sentence punctuation first (`.!?`)
- strong punctuation (`;:`)
- whitespace fallback after `min_chars`
- force split at `max_chars`

**Step 4: Run tests to verify pass**

Run: same pytest command as Step 2.

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Streaming/phrase_chunker.py tldw_Server_API/tests/Audio/test_phrase_chunker.py
git commit -m "feat(audio): add phrase chunker utility for overlapped voice synthesis"
```

### Task 3: Implement Overlapped LLM->TTS in `/audio/chat/stream`

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/audio/audio_streaming.py`
- Modify: `tldw_Server_API/app/core/TTS/tts_service_v2.py` (only if helper surface is needed)
- Test: `tldw_Server_API/tests/Audio/test_ws_audio_chat_stream.py`

**Step 1: Write failing overlap test**

```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_audio_chat_ws_overlap_starts_tts_before_final_llm_message(monkeypatch):
    # arrange: long streamed deltas + fake realtime tts chunks
    # assert: tts_start emitted before final llm_message/assistant_summary
    # assert: ws.sent_bytes contains audio before stream end
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Audio/test_ws_audio_chat_stream.py::test_audio_chat_ws_overlap_starts_tts_before_final_llm_message -v`

Expected: FAIL (ordering assertion fails).

**Step 3: Write minimal overlap implementation**

Add a turn helper that:

```python
chunker = PhraseChunker(...)
handle = await tts_service.open_realtime_session(...)
session = handle.session

# on each LLM delta:
for phrase in chunker.push(delta):
    await session.push_text(phrase)
    await session.commit()

# on stream completion:
tail = chunker.flush().strip()
if tail:
    await session.push_text(tail)
    await session.commit()
await session.finish()
```

Run TTS sender concurrently and keep `llm_delta` behavior unchanged.

**Step 4: Run targeted chat stream tests**

Run:
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Audio/test_ws_audio_chat_stream.py -k "overlap or streams_llm_and_tts" -v`

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/audio/audio_streaming.py tldw_Server_API/tests/Audio/test_ws_audio_chat_stream.py tldw_Server_API/app/core/TTS/tts_service_v2.py
git commit -m "feat(audio): overlap llm delta streaming with realtime tts synthesis"
```

### Task 4: Implement Active-Turn Interrupt Cancellation + Stale Chunk Guard

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/audio/audio_streaming.py`
- Test: `tldw_Server_API/tests/Audio/test_ws_audio_chat_stream.py`

**Step 1: Write failing tests**

```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_audio_chat_ws_interrupt_cancels_inflight_turn(monkeypatch): ...

@pytest.mark.integration
@pytest.mark.asyncio
async def test_audio_chat_ws_drops_stale_audio_after_interrupt(monkeypatch): ...
```

**Step 2: Run tests to verify fail**

Run:
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Audio/test_ws_audio_chat_stream.py -k "interrupt_cancels or stale_audio_after_interrupt" -v`

Expected: FAIL.

**Step 3: Write minimal cancellation implementation**

Add per-connection turn state:

```python
active_turn_id: Optional[str] = None
active_turn_cancelled = False
active_llm_task: Optional[asyncio.Task] = None
active_tts_sender_task: Optional[asyncio.Task] = None
```

On `interrupt`:

```python
active_turn_cancelled = True
if active_llm_task: active_llm_task.cancel()
if active_tts_sender_task: active_tts_sender_task.cancel()
await _outer_stream.send_json({"type": "interrupted", "turn_id": active_turn_id, ...})
```

Guard outbound delta/audio sends by turn id + cancelled flag.

**Step 4: Run tests to verify pass**

Run: same pytest command as Step 2.

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/audio/audio_streaming.py tldw_Server_API/tests/Audio/test_ws_audio_chat_stream.py
git commit -m "feat(audio): add turn interrupt cancellation and stale chunk drop guards"
```

### Task 5: Add `interrupt` Support to `/audio/stream/tts/realtime`

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/audio/audio_streaming.py`
- Modify: `tldw_Server_API/app/core/TTS/realtime_session.py` (optional: explicit cancel API)
- Test: `tldw_Server_API/tests/Audio/test_ws_tts_realtime_endpoint.py`

**Step 1: Write failing tests**

```python
@pytest.mark.unit
@pytest.mark.asyncio
async def test_websocket_tts_realtime_interrupt_cancels_without_close(monkeypatch): ...

@pytest.mark.unit
@pytest.mark.asyncio
async def test_websocket_tts_realtime_accepts_text_after_interrupt(monkeypatch): ...
```

**Step 2: Run tests to verify fail**

Run:
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Audio/test_ws_tts_realtime_endpoint.py -k "interrupt" -v`

Expected: FAIL.

**Step 3: Write minimal implementation**

In realtime loop:

```python
elif msg_type == "interrupt":
    # cancel current synthesis window
    await session.finish()
    if sender_task and not sender_task.done():
        sender_task.cancel()
        await sender_task
    # reopen session with same config so socket remains active
    handle = await tts_service.open_realtime_session(config=config, ...)
    session = handle.session
    sender_task = create_task(_audio_sender())
    await _send_json({"type": "interrupted", "phase": "tts", "reason": ...})
```

**Step 4: Run realtime endpoint tests**

Run:
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Audio/test_ws_tts_realtime_endpoint.py -v`

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/audio/audio_streaming.py tldw_Server_API/app/core/TTS/realtime_session.py tldw_Server_API/tests/Audio/test_ws_tts_realtime_endpoint.py
git commit -m "feat(audio): support interrupt and resume flow for realtime tts websocket"
```

### Task 6: Frontend Voice Hook Interrupt + Interrupted Handling

**Files:**
- Modify: `apps/packages/ui/src/hooks/useVoiceChatStream.tsx`
- Create: `apps/packages/ui/src/hooks/__tests__/useVoiceChatStream.interrupt.test.tsx`

**Step 1: Write failing frontend tests**

```tsx
it("sends interrupt when barge-in user audio resumes during speaking", async () => {
  // mock ws + mic stream callback while state=speaking
  // assert ws.send called with {"type":"interrupt", ...}
})

it("returns to listening when interrupted frame arrives", async () => {
  // assert onStateChange receives listening after interrupted
})
```

**Step 2: Run tests to verify fail**

Run:
- `cd apps/tldw-frontend && bunx vitest run apps/packages/ui/src/hooks/__tests__/useVoiceChatStream.interrupt.test.tsx`

Expected: FAIL.

**Step 3: Write minimal hook changes**

```tsx
// in mic chunk callback
if (voiceChatBargeIn && stateRef.current === "speaking" && wsRef.current?.readyState === WebSocket.OPEN) {
  wsRef.current.send(JSON.stringify({ type: "interrupt", reason: "barge_in" }))
}

// in handleMessage
if (msgType === "interrupted") {
  pendingResumeRef.current = false
  updateState(activeRef.current ? "listening" : "idle")
  return
}
```

**Step 4: Run tests to verify pass**

Run: same vitest command as Step 2.

Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/hooks/useVoiceChatStream.tsx apps/packages/ui/src/hooks/__tests__/useVoiceChatStream.interrupt.test.tsx
git commit -m "feat(ui): send interrupt on barge-in and handle interrupted voice frames"
```

### Task 7: Docs + Full Verification + Security Check

**Files:**
- Modify: `Docs/API/Audio_Chat.md`
- Modify: `Docs/Audio_Streaming_Protocol.md` (if frame catalog lives there)

**Step 1: Add docs for new frames**

Document:
- Client frame `interrupt`
- Server frame `interrupted`
- Backward compatibility behavior
- overlap mode behavior note for `audio/chat/stream`

**Step 2: Run backend focused regression suite**

Run:
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Audio/test_ws_audio_chat_stream.py tldw_Server_API/tests/Audio/test_ws_tts_realtime_endpoint.py -v`

Expected: PASS.

**Step 3: Run frontend focused tests**

Run:
- `cd apps/tldw-frontend && bunx vitest run apps/packages/ui/src/hooks/__tests__/useVoiceChatStream.interrupt.test.tsx apps/packages/ui/src/components/Option/Playground/__tests__/PlaygroundForm.image-refine.integration.test.tsx`

Expected: PASS.

**Step 4: Run Bandit on touched backend scope**

Run:
- `source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/api/v1/endpoints/audio/audio_streaming.py tldw_Server_API/app/core/TTS/realtime_session.py tldw_Server_API/app/core/Streaming/phrase_chunker.py -f json -o /tmp/bandit_voice_overlap_interrupt.json`

Expected: no new high-severity findings in touched code.

**Step 5: Final commit**

```bash
git add Docs/API/Audio_Chat.md Docs/Audio_Streaming_Protocol.md
git commit -m "docs(audio): document interrupt/interrupted frames and overlap behavior"
```

## Final Verification Checklist

1. Overlap test proves `tts_start` can occur before final `llm_message`.
2. Interrupt tests prove no stale audio after cancel.
3. Realtime TTS endpoint can interrupt and continue without socket close.
4. Frontend hook emits `interrupt` on barge-in and transitions cleanly.
5. Bandit report generated and reviewed.

