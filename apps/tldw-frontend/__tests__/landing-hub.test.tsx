import React from 'react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route, useLocation } from 'react-router-dom'

const storageState = new Map<string, unknown>()

const setStorageValue = (key: string, value: unknown) => {
  storageState.set(key, value)
}

const resetStorage = () => {
  storageState.clear()
}

vi.mock('@plasmohq/storage/hook', async () => {
  const React = await import('react')
  return {
    useStorage: <T,>(key: string, defaultValue: T) => {
      const [value, setValue] = React.useState<T>(
        storageState.has(key) ? (storageState.get(key) as T) : defaultValue
      )
      React.useEffect(() => {
        storageState.set(key, value)
      }, [key, value])
      return [value, setValue, { isLoading: false }] as const
    }
  }
})

const setShowLanding = vi.fn()

vi.mock('@/store/workflows', () => ({
  useWorkflowsStore: (selector: (state: { setShowLanding: () => void }) => unknown) =>
    selector({ setShowLanding })
}))

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (_key: string, fallback?: string) => fallback ?? _key
  })
}))

import { LandingHub } from '@/components/Option/LandingHub'
import { SKIP_LANDING_HUB_KEY } from '@/utils/storage-migrations'

const LocationDisplay = () => {
  const location = useLocation()
  return <div data-testid="location">{location.pathname}</div>
}

const renderLanding = () => {
  return render(
    <MemoryRouter initialEntries={["/"]}>
      <LocationDisplay />
      <Routes>
        <Route path="/" element={<LandingHub />} />
        <Route path="/chat" element={<div>Chat</div>} />
        <Route path="/workspace-playground" element={<div>Workspace</div>} />
        <Route path="/media-multi" element={<div>Media Multi</div>} />
      </Routes>
    </MemoryRouter>
  )
}

beforeEach(() => {
  resetStorage()
  setShowLanding.mockClear()
  if (!window.matchMedia) {
    window.matchMedia = ((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn()
    })) as typeof window.matchMedia
  }
})

describe('LandingHub', () => {
  it('triggers workflow landing when clicking the workflow card', async () => {
    const user = userEvent.setup()
    renderLanding()

    await user.click(
      screen.getByRole('button', { name: /get started with a workflow/i })
    )

    expect(setShowLanding).toHaveBeenCalledWith(true)
  })

  it('navigates to workspace playground when clicking Do Research', async () => {
    const user = userEvent.setup()
    renderLanding()

    await user.click(screen.getByRole('button', { name: /do research/i }))

    await waitFor(() => {
      expect(screen.getByTestId('location')).toHaveTextContent('/workspace-playground')
    })
  })

  it('navigates to media multi when clicking Perform Analysis', async () => {
    const user = userEvent.setup()
    renderLanding()

    await user.click(screen.getByRole('button', { name: /perform analysis/i }))

    await waitFor(() => {
      expect(screen.getByTestId('location')).toHaveTextContent('/media-multi')
    })
  })

  it('navigates to chat when clicking Start Chatting', async () => {
    const user = userEvent.setup()
    renderLanding()

    await user.click(screen.getByRole('button', { name: /start chatting/i }))

    await waitFor(() => {
      expect(screen.getByTestId('location')).toHaveTextContent('/chat')
    })
  })

  it('redirects to chat when skip preference is set', async () => {
    setStorageValue(SKIP_LANDING_HUB_KEY, true)
    renderLanding()

    await waitFor(() => {
      expect(screen.getByTestId('location')).toHaveTextContent('/chat')
    })
  })

  it('navigates to chat when selecting the skip checkbox', async () => {
    const user = userEvent.setup()
    renderLanding()

    await user.click(
      screen.getByRole('checkbox', {
        name: /don't show this again - go straight to chat/i
      })
    )

    await waitFor(() => {
      expect(screen.getByTestId('location')).toHaveTextContent('/chat')
    })
  })
})
