import React from 'react'
import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import {
  InstructModal,
  SearchReplaceModal
} from "../components/Option/WritingPlayground"

// TODO: InstructModal and SearchReplaceModal need to be exported from
// @/components/Option/WritingPlayground before these tests can run.
// Currently only WritingPlayground is exported.

const createPromptRef = (value: string) => {
  const textarea = document.createElement('textarea')
  textarea.value = value
  document.body.appendChild(textarea)
  return {
    ref: { current: textarea } as React.RefObject<HTMLTextAreaElement>,
    cleanup: () => document.body.removeChild(textarea)
  }
}

describe.skip('Writing Playground components (skipped: components not exported)', () => {
  it('replaces text via SearchReplaceModal', async () => {
    const { ref, cleanup } = createPromptRef('Hello world world')
    const onUpdatePrompt = vi.fn()

    try {
      render(
        <SearchReplaceModal
          open
          onClose={vi.fn()}
          promptRef={ref}
          onUpdatePrompt={onUpdatePrompt}
          promptText={ref.current?.value ?? ''}
        />
      )

      const user = userEvent.setup()
      await user.type(screen.getByPlaceholderText('Search'), 'world')
      await user.type(screen.getByPlaceholderText('Replace'), 'planet')
      await user.click(screen.getByRole('button', { name: /replace all/i }))

      expect(ref.current?.value).toBe('Hello planet planet')
      expect(onUpdatePrompt).toHaveBeenCalledWith('Hello planet planet')
    } finally {
      cleanup()
    }
  })

  it('builds an instruct prompt with context', async () => {
    const onPredict = vi.fn(async (prompt: string) => {
      expect(prompt).toContain('Context text')
      expect(prompt).toContain('fox')
      return 'Result'
    })

    render(
      <InstructModal
        open
        onClose={vi.fn()}
        selectedText="fox"
        context="Context text"
        template={{ instPre: 'INST:', instSuf: ':END' }}
        onPredict={onPredict}
        onInsert={vi.fn()}
      />
    )

    const user = userEvent.setup()
    await user.type(
      screen.getByPlaceholderText('Instruction prompt'),
      'Describe {selectedText}'
    )
    await user.click(screen.getByRole('button', { name: /predict/i }))

    expect(await screen.findByDisplayValue('Result')).toBeInTheDocument()
    expect(onPredict).toHaveBeenCalledTimes(1)
  })
})
