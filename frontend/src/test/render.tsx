import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import type { ReactElement } from 'react'
import { MemoryRouter } from 'react-router'
import { vi } from 'vitest'

type Reply = { status?: number; body: unknown }

/** Fake the API. Each key is the start of a path, and its reply is returned as JSON. */
export function mockApi(routes: Record<string, Reply | ((init?: RequestInit) => Reply)>) {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    const path = url.replace(/^\/api/, '')
    const match = Object.keys(routes)
      .sort((a, b) => b.length - a.length)
      .find((prefix) => path.startsWith(prefix))
    if (!match) throw new Error(`No mock for ${path}`)
    const route = routes[match]
    const reply = typeof route === 'function' ? route(init) : route
    return new Response(JSON.stringify(reply.body), {
      status: reply.status ?? 200,
      headers: { 'Content-Type': 'application/json' },
    })
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

export function renderPage(page: ReactElement, path = '/') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>{page}</MemoryRouter>
    </QueryClientProvider>,
  )
}
