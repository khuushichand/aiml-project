import React from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'

import App from '@web/pages/_app'

const mockRouter = {
  pathname: '/media',
  asPath: '/media',
  push: vi.fn(),
  replace: vi.fn()
}

vi.mock('next/router', () => ({
  useRouter: () => mockRouter
}))

vi.mock('@web/components/AppProviders', () => ({
  AppProviders: ({ children }: { children: React.ReactNode }) => <>{children}</>
}))

vi.mock('@web/extension/components/Layouts/Layout', () => ({
  default: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="option-layout">{children}</div>
  )
}))

const DummyPage = () => <div data-testid="page-content">Page</div>

const renderApp = (pathname: string) => {
  mockRouter.pathname = pathname
  mockRouter.asPath = pathname
  return render(<App Component={DummyPage} pageProps={{}} />)
}

beforeEach(() => {
  mockRouter.push.mockClear()
  mockRouter.replace.mockClear()
})

describe('App layout routing', () => {
  it('wraps non-chat routes with OptionLayout', () => {
    renderApp('/media')
    expect(screen.getByTestId('option-layout')).toBeInTheDocument()
    expect(screen.getByTestId('page-content')).toBeInTheDocument()
  })

  it('skips OptionLayout for /chat', () => {
    renderApp('/chat')
    expect(screen.queryByTestId('option-layout')).toBeNull()
    expect(screen.getByTestId('page-content')).toBeInTheDocument()
  })

  it('skips OptionLayout for /chat subroutes', () => {
    renderApp('/chat/agent')
    expect(screen.queryByTestId('option-layout')).toBeNull()
    expect(screen.getByTestId('page-content')).toBeInTheDocument()
  })
})
