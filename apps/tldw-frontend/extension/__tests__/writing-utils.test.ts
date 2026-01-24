import { describe, expect, it } from 'vitest'
import type { WritingPromptChunk } from "../types/writing"
import {
  applyFimTemplate,
  assembleWorldInfo,
  normalizeSessionPayload
} from "../utils/writing"
import { DEFAULT_SESSION } from "../components/Option/WritingPlayground/presets"

// TODO: These utilities need to be extracted from WritingPlayground/index.tsx
// and exported from @/utils/writing before these tests can run.
// See: apps/packages/ui/src/components/Option/WritingPlayground/index.tsx

describe.skip('writing utils (skipped: @/utils/writing not yet extracted)', () => {
  it('normalizes payload values and prompt content', () => {
    const normalized = normalizeSessionPayload(
      {
        prompt: 'Hello world',
        seed: '42',
        spellCheck: 'false',
        endpointModel: 'test-model',
        selectedTemplate: 'ChatML'
      },
      DEFAULT_SESSION
    )

    expect(normalized.seed).toBe(42)
    expect(normalized.spellCheck).toBe(false)
    expect(normalized.model).toBe('test-model')
    expect(normalized.template).toBe('ChatML')
    expect(normalized.prompt).toEqual([
      { type: 'user', content: 'Hello world' }
    ])
  })

  it('applies FIM placeholder into left/right chunks', () => {
    const promptChunks: WritingPromptChunk[] = [
      { type: 'user', content: 'Hello {predict}world' }
    ]
    const result = applyFimTemplate(promptChunks)

    expect(result.modifiedPromptText).toBe('Hello')
    expect(result.fimPromptInfo?.fimRightChunks[0].content).toBe('world')
    expect(result.fimPromptInfo?.fimPlaceholder).toBe('{predict}')
  })

  it('assembles world info when keys match', () => {
    const worldInfo = {
      mikuPediaVersion: 1,
      prefix: '',
      suffix: '',
      entries: [
        {
          displayName: 'Dragons',
          text: 'Dragon lore',
          keys: ['dragon'],
          search: '100'
        }
      ]
    }

    const result = assembleWorldInfo('A dragon appears in the sky.', worldInfo, 1)
    expect(result).toBe('Dragon lore')
  })
})
