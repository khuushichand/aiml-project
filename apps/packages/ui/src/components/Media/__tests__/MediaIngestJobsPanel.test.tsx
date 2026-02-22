import React from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MediaIngestJobsPanel } from '../MediaIngestJobsPanel'

const mocks = vi.hoisted(() => ({
  listMediaIngestJobs: vi.fn()
}))

const storageState = vi.hoisted(() => ({
  values: new Map<string, unknown>()
}))

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (
      key: string,
      fallbackOrOptions?: string | { defaultValue?: string; [k: string]: unknown }
    ) => {
      if (typeof fallbackOrOptions === 'string') return fallbackOrOptions
      return fallbackOrOptions?.defaultValue || key
    }
  })
}))

vi.mock('@plasmohq/storage/hook', async () => {
  const React = await import('react')
  return {
    useStorage: (key: string, initialValue: unknown) => {
      if (!storageState.values.has(key)) {
        storageState.values.set(key, initialValue)
      }
      const [value, setValue] = React.useState(storageState.values.get(key))
      const updateValue = (next: unknown | ((prev: unknown) => unknown)) => {
        setValue((prev) => {
          const resolved = typeof next === 'function' ? (next as (p: unknown) => unknown)(prev) : next
          storageState.values.set(key, resolved)
          return resolved
        })
      }
      return [value, updateValue] as const
    }
  }
})

vi.mock('@/services/tldw/TldwApiClient', () => ({
  tldwClient: {
    listMediaIngestJobs: mocks.listMediaIngestJobs
  }
}))

describe('MediaIngestJobsPanel', () => {
  beforeEach(() => {
    storageState.values.clear()
    storageState.values.set('media:ingest:panelCollapsed', false)
    storageState.values.set('media:ingest:lastBatchId', 'batch-123')
    storageState.values.set('media:ingest:autoRefresh', false)
    mocks.listMediaIngestJobs.mockReset()
  })

  it('loads and renders ingest job rows for the active batch', async () => {
    mocks.listMediaIngestJobs.mockResolvedValue({
      jobs: [
        {
          id: 17,
          status: 'running',
          source: 'https://example.com/doc',
          source_kind: 'url',
          progress_percent: 42,
          progress_message: 'Extracting content'
        }
      ]
    })

    render(<MediaIngestJobsPanel />)

    await waitFor(() =>
      expect(mocks.listMediaIngestJobs).toHaveBeenCalledWith({
        batch_id: 'batch-123',
        limit: 50
      })
    )

    expect(screen.getByTestId('media-ingest-job-row-17')).toBeInTheDocument()
    expect(screen.getByTestId('media-ingest-job-status-17')).toHaveTextContent('running')
    expect(screen.getByText('42% • Extracting content')).toBeInTheDocument()
  })

  it('applies a new batch id and shows an empty-state message when no jobs are returned', async () => {
    storageState.values.set('media:ingest:lastBatchId', '')
    mocks.listMediaIngestJobs.mockResolvedValue({ jobs: [] })

    render(<MediaIngestJobsPanel />)

    expect(screen.getByTestId('media-ingest-jobs-empty-batch')).toBeInTheDocument()

    fireEvent.change(screen.getByTestId('media-ingest-batch-input'), {
      target: { value: 'new-batch' }
    })
    fireEvent.click(screen.getByTestId('media-ingest-batch-apply'))

    await waitFor(() =>
      expect(mocks.listMediaIngestJobs).toHaveBeenCalledWith({
        batch_id: 'new-batch',
        limit: 50
      })
    )

    expect(screen.getByTestId('media-ingest-jobs-empty')).toBeInTheDocument()
  })

  it('shows an inline error and retries successfully', async () => {
    mocks.listMediaIngestJobs.mockRejectedValueOnce(new Error('boom'))
    mocks.listMediaIngestJobs.mockResolvedValueOnce({
      jobs: [
        {
          id: 23,
          status: 'completed',
          source: 'report.pdf',
          source_kind: 'file'
        }
      ]
    })

    render(<MediaIngestJobsPanel />)

    expect(await screen.findByTestId('media-ingest-jobs-error')).toBeInTheDocument()
    fireEvent.click(screen.getByTestId('media-ingest-jobs-retry'))

    await waitFor(() => {
      expect(mocks.listMediaIngestJobs).toHaveBeenCalledTimes(2)
    })
    expect(await screen.findByTestId('media-ingest-job-row-23')).toBeInTheDocument()
  })
})
