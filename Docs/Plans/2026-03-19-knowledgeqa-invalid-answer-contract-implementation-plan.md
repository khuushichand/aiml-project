# KnowledgeQA Invalid Answer Contract Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Prevent `/knowledge` from rendering placeholder answers such as `<template>`, preserve retrieved sources, and surface an explicit invalid-answer recovery state without persisting bogus conversation artifacts.

**Architecture:** Add a narrow backend answer-contract helper that sanitizes `generation_prompt`, classifies generated answers, and annotates standard and streaming RAG responses with explicit validity metadata. Mirror that contract in frontend request normalization and Knowledge QA state so invalid answers never render, streamed placeholder prefixes stay hidden, and fresh invalid searches do not create durable turns or history items.

**Tech Stack:** FastAPI, Pydantic, unified RAG pipeline, React, TypeScript, Vitest, Playwright, pytest, Bandit

---

## Stage 1: Backend Answer Contract
**Goal:** Introduce a shared backend validator for placeholder outputs and prompt sanitization.
**Success Criteria:** Backend has one sentinel-based normalization path for standard and streaming searches; focused unit tests cover valid prose, whitespace-only output, `<template>`, and placeholder `generation_prompt`.
**Tests:** `python -m pytest tldw_Server_API/tests/RAG_NEW/unit/test_rag_answer_contract.py -v`
**Status:** Not Started

### Task 1: Add backend answer-contract helper

**Files:**
- Create: `tldw_Server_API/app/core/RAG/rag_service/answer_contract.py`
- Create: `tldw_Server_API/tests/RAG_NEW/unit/test_rag_answer_contract.py`

**Step 1: Write the failing test**

```python
from tldw_Server_API.app.core.RAG.rag_service.answer_contract import (
    classify_generated_answer,
    sanitize_generation_prompt,
)


def test_classify_generated_answer_rejects_template_placeholder():
    verdict = classify_generated_answer("<template>", generation_attempted=True)

    assert verdict.normalized_answer is None
    assert verdict.answer_status == "invalid"
    assert verdict.answer_rejection_reason == "placeholder_output"
    assert verdict.generation_attempted is True


def test_sanitize_generation_prompt_drops_template_placeholder():
    sanitized, reason = sanitize_generation_prompt("<template>")

    assert sanitized is None
    assert reason == "invalid_generation_prompt"


def test_classify_generated_answer_keeps_readable_abstention():
    verdict = classify_generated_answer(
        "I don’t have sufficient grounded evidence to answer confidently.",
        generation_attempted=True,
    )

    assert verdict.normalized_answer == "I don’t have sufficient grounded evidence to answer confidently."
    assert verdict.answer_status == "valid"
    assert verdict.answer_rejection_reason is None
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/RAG_NEW/unit/test_rag_answer_contract.py -v`

Expected: FAIL with `ModuleNotFoundError` or missing symbol assertions for the new helper.

**Step 3: Write minimal implementation**

```python
from dataclasses import dataclass
from typing import Optional


_PLACEHOLDER_SENTINELS = {"<template>"}


@dataclass(frozen=True)
class AnswerContractVerdict:
    normalized_answer: Optional[str]
    answer_status: str
    answer_rejection_reason: Optional[str]
    generation_attempted: bool


def _normalize_text(value: object) -> Optional[str]:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def sanitize_generation_prompt(value: object) -> tuple[Optional[str], Optional[str]]:
    text = _normalize_text(value)
    if text is None:
        return None, None
    if text.lower() in _PLACEHOLDER_SENTINELS:
        return None, "invalid_generation_prompt"
    return text, None


def classify_generated_answer(
    value: object,
    *,
    generation_attempted: bool,
) -> AnswerContractVerdict:
    text = _normalize_text(value)
    if text is None:
        return AnswerContractVerdict(None, "none", None, generation_attempted)
    if text.lower() in _PLACEHOLDER_SENTINELS:
        return AnswerContractVerdict(None, "invalid", "placeholder_output", generation_attempted)
    return AnswerContractVerdict(text, "valid", None, generation_attempted)
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/RAG_NEW/unit/test_rag_answer_contract.py -v`

Expected: PASS for the three focused contract tests.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/RAG/rag_service/answer_contract.py tldw_Server_API/tests/RAG_NEW/unit/test_rag_answer_contract.py
git commit -m "test: cover rag invalid answer contract"
```

### Task 2: Normalize standard `/rag/search` responses through the contract

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/rag_unified.py`
- Modify: `tldw_Server_API/tests/RAG_NEW/unit/test_rag_unified_response_mapping.py`

**Step 1: Write the failing test**

```python
def test_convert_result_to_response_rejects_template_answer_and_sets_metadata():
    result = UnifiedSearchResult(
        documents=[],
        query="placeholder answer",
        generated_answer="<template>",
        metadata={},
    )

    converted = rag_ep.convert_result_to_response(result)

    assert converted.generated_answer is None
    assert converted.metadata["generation_attempted"] is True
    assert converted.metadata["answer_status"] == "invalid"
    assert converted.metadata["answer_rejection_reason"] == "placeholder_output"
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/RAG_NEW/unit/test_rag_unified_response_mapping.py -v`

Expected: FAIL because `convert_result_to_response()` currently returns `generated_answer="<template>"` and does not attach answer metadata.

**Step 3: Write minimal implementation**

```python
from tldw_Server_API.app.core.RAG.rag_service.answer_contract import (
    classify_generated_answer,
)


def convert_result_to_response(result: UnifiedSearchResult) -> UnifiedRAGResponse:
    verdict = classify_generated_answer(
        result.generated_answer,
        generation_attempted=result.generated_answer is not None,
    )
    metadata = dict(result.metadata or {})
    metadata["generation_attempted"] = verdict.generation_attempted
    metadata["answer_status"] = verdict.answer_status
    metadata["answer_rejection_reason"] = verdict.answer_rejection_reason
    return UnifiedRAGResponse(
        documents=documents,
        query=result.query,
        expanded_queries=result.expanded_queries,
        metadata=metadata,
        timings=result.timings,
        citations=result.citations,
        academic_citations=metadata.get("academic_citations", []),
        chunk_citations=metadata.get("chunk_citations", []),
        feedback_id=result.feedback_id,
        generated_answer=verdict.normalized_answer,
        cache_hit=result.cache_hit,
        errors=result.errors,
        security_report=result.security_report,
        total_time=result.total_time,
    )
```

Use `generation_attempted=True` whenever generation was enabled and reached response mapping, even if the final normalized answer becomes `None`.

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/RAG_NEW/unit/test_rag_unified_response_mapping.py -v`

Expected: PASS with existing mapping tests still green and the new invalid-answer mapping assertion passing.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/rag_unified.py tldw_Server_API/tests/RAG_NEW/unit/test_rag_unified_response_mapping.py
git commit -m "feat: normalize invalid rag search answers"
```

## Stage 2: Streaming Contract And Backend Prompt Guard
**Goal:** Make streaming emit an explicit terminal answer-status event and drop placeholder `generation_prompt` values before generation starts.
**Success Criteria:** `/api/v1/rag/search/stream` ends with a `type="final"` event, `<template>` never becomes a valid streamed answer, and placeholder `generation_prompt` is omitted from generation config.
**Tests:** `python -m pytest tldw_Server_API/tests/RAG_NEW/integration/test_rag_stream_parity.py -k "final or prompt" -v`
**Status:** Not Started

### Task 3: Sanitize `generation_prompt` before standard and streaming generation

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/rag_unified.py`
- Modify: `tldw_Server_API/tests/RAG_NEW/integration/test_rag_stream_parity.py`

**Step 1: Write the failing test**

```python
def test_rag_streaming_omits_placeholder_generation_prompt(
    monkeypatch: pytest.MonkeyPatch,
    client_with_stream_overrides: TestClient,
) -> None:
    captured = {"generation_config": None}

    async def fake_generate_streaming_response(context: Any, **kwargs: Any) -> Any:
        captured["generation_config"] = context.config.get("generation")
        async def _gen():
            yield "safe answer"
        context.stream_generator = _gen()
        context.metadata = {}
        return context

    monkeypatch.setattr(rag_ep, "generate_streaming_response", fake_generate_streaming_response)

    with client_with_stream_overrides.stream(
        "POST",
        "/api/v1/rag/search/stream",
        json={"query": "prompt guard", "enable_generation": True, "generation_prompt": "<template>"},
    ) as resp:
        assert resp.status_code == 200
        list(resp.iter_lines())

    assert "prompt_template" not in captured["generation_config"]
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/RAG_NEW/integration/test_rag_stream_parity.py -k prompt -v`

Expected: FAIL because the current streaming endpoint forwards `<template>` into `generation_config["prompt_template"]`.

**Step 3: Write minimal implementation**

```python
from tldw_Server_API.app.core.RAG.rag_service.answer_contract import sanitize_generation_prompt


payload = _build_effective_request_payload(request)
sanitized_prompt, prompt_rejection_reason = sanitize_generation_prompt(payload.get("generation_prompt"))
if sanitized_prompt is None:
    payload.pop("generation_prompt", None)
else:
    payload["generation_prompt"] = sanitized_prompt
if prompt_rejection_reason:
    payload["_answer_contract_prompt_rejection_reason"] = prompt_rejection_reason
```

Apply the same sanitation path inside `_build_effective_request_payload()` so standard search and streaming both get the guard.

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/RAG_NEW/integration/test_rag_stream_parity.py -k prompt -v`

Expected: PASS with `generation_config` missing `prompt_template` for placeholder input.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/rag_unified.py tldw_Server_API/tests/RAG_NEW/integration/test_rag_stream_parity.py
git commit -m "feat: guard invalid rag generation prompts"
```

### Task 4: Emit a terminal streaming answer-status event

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/rag_unified.py`
- Modify: `tldw_Server_API/tests/RAG_NEW/integration/test_rag_stream_parity.py`

**Step 1: Write the failing test**

```python
def test_rag_streaming_emits_final_invalid_answer_status(
    monkeypatch: pytest.MonkeyPatch,
    client_with_stream_overrides: TestClient,
) -> None:
    async def _fake_generate_streaming_response(context: Any, **kwargs: Any) -> Any:
        async def _gen():
            yield "<template>"
        context.stream_generator = _gen()
        context.metadata = {}
        return context

    monkeypatch.setattr(rag_ep, "generate_streaming_response", _fake_generate_streaming_response)

    events = []
    with client_with_stream_overrides.stream(
        "POST",
        "/api/v1/rag/search/stream",
        json={"query": "invalid final", "enable_generation": True},
    ) as resp:
        for raw in resp.iter_lines():
            if raw:
                events.append(json.loads(raw))

    assert events[-1] == {
        "type": "final",
        "generation_attempted": True,
        "answer_status": "invalid",
        "answer_rejection_reason": "placeholder_output",
        "metadata": {},
    }
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/RAG_NEW/integration/test_rag_stream_parity.py -k final -v`

Expected: FAIL because the current stream ends without a `type="final"` event.

**Step 3: Write minimal implementation**

```python
stream_buffer: list[str] = []
async for chunk in context.stream_generator:
    stream_buffer.append(chunk)
    yield json.dumps({"type": "delta", "text": chunk}) + "\n"

final_text = "".join(stream_buffer)
verdict = classify_generated_answer(final_text, generation_attempted=True)
yield json.dumps(
    {
        "type": "final",
        "generation_attempted": verdict.generation_attempted,
        "answer_status": verdict.answer_status,
        "answer_rejection_reason": verdict.answer_rejection_reason,
        "metadata": {
            "prompt_rejection_reason": prompt_rejection_reason,
        },
    }
) + "\n"
```

Keep `final_claims` for compatibility if needed, but always emit the `final` event last.

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/RAG_NEW/integration/test_rag_stream_parity.py -k final -v`

Expected: PASS with the new terminal event and existing stream parity tests still green.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/rag_unified.py tldw_Server_API/tests/RAG_NEW/integration/test_rag_stream_parity.py
git commit -m "feat: add rag stream final answer status"
```

## Stage 3: Frontend Request, State, And Persistence Guards
**Goal:** Mirror the backend contract in the frontend so invalid answers never render, stream buffers stay hidden for sentinel prefixes, and bogus searches do not create durable Knowledge QA artifacts.
**Success Criteria:** Frontend omits placeholder `generation_prompt`, surfaces invalid-answer recovery copy, keeps retrieval results visible, and suppresses persistence/history for invalid-answer runs.
**Tests:** `bunx vitest run apps/packages/ui/src/services/rag/unified-rag.test.ts apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/AnswerPanel.states.test.tsx apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/KnowledgeQAProvider.streaming.test.tsx apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/KnowledgeQAProvider.persistence.test.tsx`
**Status:** Not Started

### Task 5: Add frontend answer-contract helpers and request normalization

**Files:**
- Create: `apps/packages/ui/src/services/rag/answer-contract.ts`
- Modify: `apps/packages/ui/src/services/rag/unified-rag.ts`
- Modify: `apps/packages/ui/src/services/rag/unified-rag.test.ts`
- Modify: `apps/packages/ui/src/components/Option/KnowledgeQA/types.ts`

**Step 1: Write the failing test**

```ts
import { describe, expect, it } from "vitest"

import { DEFAULT_RAG_SETTINGS, buildRagSearchRequest } from "./unified-rag"

describe("buildRagSearchRequest generation prompt guard", () => {
  it("omits placeholder generation_prompt", () => {
    const req = buildRagSearchRequest({
      ...DEFAULT_RAG_SETTINGS,
      query: "q",
      generation_prompt: "<template>",
    })

    expect((req.options as Record<string, unknown>).generation_prompt).toBeUndefined()
  })
})
```

**Step 2: Run test to verify it fails**

Run: `bunx vitest run apps/packages/ui/src/services/rag/unified-rag.test.ts`

Expected: FAIL because `buildRagSearchRequest()` currently forwards any truthy `generation_prompt`.

**Step 3: Write minimal implementation**

```ts
export const PLACEHOLDER_SENTINELS = new Set(["<template>"])

export function normalizeKnowledgeGenerationPrompt(value: string | null): string | null {
  const text = typeof value === "string" ? value.trim() : ""
  if (!text) return null
  return PLACEHOLDER_SENTINELS.has(text.toLowerCase()) ? null : text
}

export function shouldHideStreamingAnswerBuffer(value: string): boolean {
  const text = value.trim().toLowerCase()
  return [...PLACEHOLDER_SENTINELS].some((sentinel) => sentinel.startsWith(text))
}
```

Use `normalizeKnowledgeGenerationPrompt()` in `buildRagSearchRequest()` and extend `SearchRuntimeDetails` with:

```ts
generationAttempted: boolean
answerStatus: "valid" | "invalid" | "none"
answerRejectionReason: string | null
```

**Step 4: Run test to verify it passes**

Run: `bunx vitest run apps/packages/ui/src/services/rag/unified-rag.test.ts`

Expected: PASS for the existing `rag_profile` assertions and the new placeholder prompt guard.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/services/rag/answer-contract.ts apps/packages/ui/src/services/rag/unified-rag.ts apps/packages/ui/src/services/rag/unified-rag.test.ts apps/packages/ui/src/components/Option/KnowledgeQA/types.ts
git commit -m "feat: add frontend knowledge answer contract helpers"
```

### Task 6: Apply the contract in `KnowledgeQAProvider` and suppress invalid persistence

**Files:**
- Modify: `apps/packages/ui/src/components/Option/KnowledgeQA/KnowledgeQAProvider.tsx`
- Modify: `apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/KnowledgeQAProvider.streaming.test.tsx`
- Modify: `apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/KnowledgeQAProvider.persistence.test.tsx`

**Step 1: Write the failing tests**

```tsx
it("keeps streamed template output hidden until final invalid status", async () => {
  ragSearchStreamMock.mockImplementation(async function* () {
    yield { type: "contexts", contexts: [{ id: "doc-1", title: "Doc One", score: 0.92 }] }
    yield { type: "delta", text: "<temp" }
    yield { type: "delta", text: "late>" }
    yield {
      type: "final",
      generation_attempted: true,
      answer_status: "invalid",
      answer_rejection_reason: "placeholder_output",
      metadata: {},
    }
  })

  render(
    <KnowledgeQAProvider>
      <ContextProbe />
    </KnowledgeQAProvider>
  )
  await waitFor(() => expect(latestContext).not.toBeNull())
  await act(async () => {
    await latestContext!.selectThread("local-stream-invalid")
  })
  act(() => {
    latestContext!.setQuery("stream invalid answer")
  })
  await act(async () => {
    await latestContext!.search()
  })

  expect(latestContext!.answer).toBeNull()
  expect(latestContext!.searchDetails?.answerStatus).toBe("invalid")
})

it("does not persist messages or history for invalid answers", async () => {
  ragSearchMock.mockResolvedValue({
    results: [{ id: "doc-1", metadata: { title: "Doc 1" } }],
    answer: "<template>",
    metadata: {
      generation_attempted: true,
      answer_status: "invalid",
      answer_rejection_reason: "placeholder_output",
    },
  })

  render(
    <KnowledgeQAProvider>
      <ContextProbe />
    </KnowledgeQAProvider>
  )
  await waitFor(() => expect(latestContext).not.toBeNull())
  act(() => {
    latestContext!.setQuery("fresh invalid answer")
  })
  await act(async () => {
    await latestContext!.search()
  })

  expect(addChatMessageMock).not.toHaveBeenCalled()
  expect(deleteChatMock).toHaveBeenCalledTimes(1)
  expect(latestContext!.messages).toEqual([])
  expect(latestContext!.searchHistory).toEqual([])
})
```

**Step 2: Run tests to verify they fail**

Run: `bunx vitest run apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/KnowledgeQAProvider.streaming.test.tsx apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/KnowledgeQAProvider.persistence.test.tsx`

Expected: FAIL because the provider currently renders streamed deltas immediately and persists thread/user state before answer validity is known.

**Step 3: Write minimal implementation**

```tsx
const normalized = normalizeKnowledgeAnswerResponse(response)
const isInvalidAnswer = normalized.answerStatus === "invalid"

if (eventType === "delta") {
  streamAnswer += deltaText
  const hidden = shouldHideStreamingAnswerBuffer(streamAnswer)
  dispatch({
    type: "SET_PARTIAL_RESULTS",
    payload: {
      results: streamResults,
      answer: hidden ? null : normalizedAnswerText(streamAnswer),
      citations: hidden ? [] : parseCitations(normalizedAnswerText(streamAnswer) ?? "", streamResults),
    },
  })
}

if (eventType === "final") {
  finalAnswerStatus = event.answer_status ?? "none"
  finalAnswerReason = event.answer_rejection_reason ?? null
}

if (!isInvalidAnswer) {
  const persistedUser = threadId
    ? await persistChatMessage(threadId, "user", trimmedQuery, null)
    : null
  if (threadId) {
    dispatch({
      type: "ADD_MESSAGE",
      payload: {
        id: persistedUser?.id || crypto.randomUUID(),
        conversationId: threadId,
        role: "user",
        content: trimmedQuery,
        timestamp: persistedUser?.timestamp || new Date().toISOString(),
      },
    })
  }
  if (answer && threadId) {
    const persistedAssistant = await persistChatMessage(
      threadId,
      "assistant",
      answer,
      persistedUser?.id ?? null,
    )
    dispatch({
      type: "ADD_MESSAGE",
      payload: {
        id: persistedAssistant?.id || crypto.randomUUID(),
        conversationId: threadId,
        role: "assistant",
        content: answer,
        timestamp: persistedAssistant?.timestamp || new Date().toISOString(),
        ragContext,
      },
    })
  }
} else if (createdThreadForSearch && threadId && !isLocalThreadId(threadId)) {
  await tldwClient.deleteChat(threadId)
  dispatch({ type: "REMOVE_THREAD", payload: threadId })
  dispatch({ type: "SET_THREAD_ID", payload: null })
}
```

Implementation notes:
- Stop using `normalizeAnswerText()` as the only answer validator; route all answer extraction through the new frontend contract helper.
- Buffer streaming text separately from visible answer state.
- Add a reducer action such as `REMOVE_THREAD` so an empty thread created for an invalid fresh search can be removed cleanly.
- Delay durable `user`/`assistant` persistence until after answer classification, rather than rolling back persisted messages later.
- Skip `ADD_HISTORY_ITEM` when `answerStatus === "invalid"`.

**Step 4: Run tests to verify they pass**

Run: `bunx vitest run apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/KnowledgeQAProvider.streaming.test.tsx apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/KnowledgeQAProvider.persistence.test.tsx`

Expected: PASS with invalid streamed answers hidden and invalid-answer searches producing no durable thread/history artifacts.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Option/KnowledgeQA/KnowledgeQAProvider.tsx apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/KnowledgeQAProvider.streaming.test.tsx apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/KnowledgeQAProvider.persistence.test.tsx
git commit -m "feat: suppress invalid knowledge qa persistence"
```

### Task 7: Render a dedicated invalid-answer recovery state in `AnswerPanel`

**Files:**
- Modify: `apps/packages/ui/src/components/Option/KnowledgeQA/AnswerPanel.tsx`
- Modify: `apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/AnswerPanel.states.test.tsx`

**Step 1: Write the failing test**

```tsx
it("shows invalid-answer recovery copy when sources exist but answer was rejected", () => {
  state.results = [{ id: "r1", metadata: { title: "Doc 1" } }]
  state.searchDetails = {
    expandedQueries: [],
    rerankingEnabled: true,
    rerankingStrategy: "flashrank",
    averageRelevance: 0.91,
    webFallbackEnabled: false,
    webFallbackTriggered: false,
    webFallbackEngine: null,
    tokensUsed: null,
    estimatedCostUsd: null,
    feedbackId: null,
    whyTheseSources: null,
    faithfulnessScore: null,
    faithfulnessTotalClaims: null,
    faithfulnessSupportedClaims: null,
    faithfulnessUnsupportedClaims: null,
    verificationRate: null,
    verificationCoverage: null,
    verificationTotalClaims: null,
    verificationVerifiedClaims: null,
    verificationReportAvailable: false,
    retrievalLatencyMs: null,
    documentsConsidered: null,
    chunksConsidered: null,
    documentsReturned: 1,
    candidatesConsidered: null,
    candidatesReturned: 1,
    candidatesRejected: null,
    alsoConsidered: [],
    generationAttempted: true,
    answerStatus: "invalid",
    answerRejectionReason: "placeholder_output",
  }

  render(<AnswerPanel />)

  expect(
    screen.getByText("Sources were found, but answer generation returned invalid output.")
  ).toBeInTheDocument()
  expect(screen.queryByText("Enable answer generation in settings")).not.toBeInTheDocument()
  expect(screen.queryByText("AI Answer")).not.toBeInTheDocument()
})
```

**Step 2: Run test to verify it fails**

Run: `bunx vitest run apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/AnswerPanel.states.test.tsx`

Expected: FAIL because the panel currently always shows the “Enable in Settings” guidance whenever `answer` is missing and sources exist.

**Step 3: Write minimal implementation**

```tsx
if (!normalizedAnswer && results.length > 0) {
  if (searchDetails?.answerStatus === "invalid") {
    return (
      <div className={cn("p-6 rounded-xl bg-muted/30 border border-border", className)}>
        <p>Sources were found, but answer generation returned invalid output.</p>
        <p>Retry the search or review custom generation settings.</p>
      </div>
    )
  }

  return (
    <div className={cn("p-6 rounded-xl bg-muted/30 border border-border", className)}>
      <p>
        Found {results.length} relevant source{results.length !== 1 ? "s" : ""}.
        Enable answer generation in settings to get a synthesized response.
      </p>
      <button
        type="button"
        onClick={() => setSettingsPanelOpen(true)}
        className="mt-2 inline-flex items-center rounded-md border border-primary/30 bg-primary/10 px-2 py-1 text-xs font-medium text-primary hover:bg-primary/15 transition-colors"
      >
        Enable in Settings
      </button>
    </div>
  )
}
```

**Step 4: Run test to verify it passes**

Run: `bunx vitest run apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/AnswerPanel.states.test.tsx`

Expected: PASS with the new invalid-answer branch and existing no-answer guidance preserved for generation-disabled searches.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Option/KnowledgeQA/AnswerPanel.tsx apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/AnswerPanel.states.test.tsx
git commit -m "feat: show invalid answer recovery state"
```

## Stage 4: End-To-End Coverage And Verification
**Goal:** Prove the user-facing `/knowledge` contract end to end and run final safety checks on touched backend code.
**Success Criteria:** Stubbed E2E flows confirm `<template>` never appears, sources remain visible, invalid-answer recovery copy shows, and targeted backend/frontend tests plus Bandit pass.
**Tests:** Playwright workflow, targeted pytest, targeted Vitest, Bandit on touched backend scope.
**Status:** Not Started

### Task 8: Add deterministic `/knowledge` E2E coverage for invalid standard and streaming answers

**Files:**
- Modify: `apps/tldw-frontend/e2e/workflows/knowledge-qa.spec.ts`

**Step 1: Write the failing tests**

```ts
test("hides placeholder answers from non-stream responses", async ({ authedPage, diagnostics }) => {
  await authedPage.route("**/api/v1/rag/search/stream", async (route) => {
    await route.fulfill({ status: 200, contentType: "text/plain", body: "" })
  })
  await authedPage.route("**/api/v1/rag/search", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        results: [{ id: "doc-1", content: "Evidence", metadata: { title: "Doc 1" }, score: 0.91 }],
        answer: "<template>",
        metadata: {
          generation_attempted: true,
          answer_status: "invalid",
          answer_rejection_reason: "placeholder_output",
        },
      }),
    })
  })

  await qaPage.goto()
  await qaPage.waitForReady()
  await qaPage.search("placeholder check")
  await qaPage.waitForResults()

  await expect(authedPage.getByText("<template>")).not.toBeVisible()
  await expect(authedPage.getByText(/Sources were found, but answer generation returned invalid output./i)).toBeVisible()
})
```

Add a second test that fulfills `/api/v1/rag/search/stream` with NDJSON:

```json
{"type":"contexts","contexts":[{"id":"doc-1","title":"Doc 1","score":0.91}]}
{"type":"delta","text":"<template>"}
{"type":"final","generation_attempted":true,"answer_status":"invalid","answer_rejection_reason":"placeholder_output","metadata":{}}
```

**Step 2: Run test to verify it fails**

Run: `bunx playwright test apps/tldw-frontend/e2e/workflows/knowledge-qa.spec.ts --reporter=line`

Expected: FAIL because the current UI renders `<template>` or falls back to the wrong no-answer copy.

**Step 3: Write minimal implementation**

If the recovery state needs a reusable locator, add one of these two minimal test-support changes:

```ts
async hasInvalidAnswerRecoveryState(): Promise<boolean> {
  return this.page
    .getByText(/Sources were found, but answer generation returned invalid output./i)
    .isVisible()
    .catch(() => false)
}
```

or keep the spec self-contained and assert the recovery copy directly with `authedPage.getByText(...)`.

**Step 4: Run test to verify it passes**

Run: `bunx playwright test apps/tldw-frontend/e2e/workflows/knowledge-qa.spec.ts --reporter=line`

Expected: PASS with both invalid standard and invalid streaming cases covered.

**Step 5: Commit**

```bash
git add apps/tldw-frontend/e2e/workflows/knowledge-qa.spec.ts
git commit -m "test: cover knowledge qa invalid answer contract"
```

### Task 9: Final targeted verification and security check

**Files:**
- Verify only; no planned source edits

**Step 1: Run targeted backend tests**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/RAG_NEW/unit/test_rag_answer_contract.py tldw_Server_API/tests/RAG_NEW/unit/test_rag_unified_response_mapping.py tldw_Server_API/tests/RAG_NEW/integration/test_rag_stream_parity.py -v`

Expected: PASS for backend contract, response mapping, and stream final-event coverage.

**Step 2: Run targeted frontend unit tests**

Run: `bunx vitest run apps/packages/ui/src/services/rag/unified-rag.test.ts apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/AnswerPanel.states.test.tsx apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/KnowledgeQAProvider.streaming.test.tsx apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/KnowledgeQAProvider.persistence.test.tsx`

Expected: PASS for request normalization, provider guardrails, and invalid-answer UI state.

**Step 3: Run Bandit on touched backend scope**

Run: `source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/core/RAG/rag_service/answer_contract.py tldw_Server_API/app/api/v1/endpoints/rag_unified.py -f json -o /tmp/bandit_knowledgeqa_invalid_answer.json`

Expected: JSON report written to `/tmp/bandit_knowledgeqa_invalid_answer.json` with no new actionable findings in touched code.

**Step 4: Run the E2E workflow one more time**

Run: `bunx playwright test apps/tldw-frontend/e2e/workflows/knowledge-qa.spec.ts --reporter=line`

Expected: PASS with no literal `<template>` visible anywhere in the `/knowledge` workflow.

**Step 5: Commit**

```bash
git status --short
git add tldw_Server_API/app/core/RAG/rag_service/answer_contract.py tldw_Server_API/app/api/v1/endpoints/rag_unified.py tldw_Server_API/tests/RAG_NEW/unit/test_rag_answer_contract.py tldw_Server_API/tests/RAG_NEW/unit/test_rag_unified_response_mapping.py tldw_Server_API/tests/RAG_NEW/integration/test_rag_stream_parity.py apps/packages/ui/src/services/rag/answer-contract.ts apps/packages/ui/src/services/rag/unified-rag.ts apps/packages/ui/src/services/rag/unified-rag.test.ts apps/packages/ui/src/components/Option/KnowledgeQA/types.ts apps/packages/ui/src/components/Option/KnowledgeQA/KnowledgeQAProvider.tsx apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/KnowledgeQAProvider.streaming.test.tsx apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/KnowledgeQAProvider.persistence.test.tsx apps/packages/ui/src/components/Option/KnowledgeQA/AnswerPanel.tsx apps/packages/ui/src/components/Option/KnowledgeQA/__tests__/AnswerPanel.states.test.tsx apps/tldw-frontend/e2e/workflows/knowledge-qa.spec.ts
git commit -m "fix: enforce knowledge qa invalid answer contract"
```
