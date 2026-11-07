import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { App } from './App'
import { ApiError, errorMessage, NOT_REACHABLE, NOT_SHOPSENSE } from './api/client'
import { ErrorBoundary } from './components/ErrorBoundary'
import { addDays, daysBetween } from './format'
import { forecastableWeeks } from './pages/forecastWeeks'
import { buildFreightRequest } from './pages/freightRequest'
import { mockApi, renderPage } from './test/render'

const HEALTH = { status: 'ok', database_ready: true, loaded: ['freight_cost'], unavailable: {} }
const MODELS = [
  {
    name: 'freight_cost',
    problem: '7. Freight cost estimate',
    status: 'active',
    kind: 'regression',
    version: '1.0.0',
    verdict: 'Ready',
    note: 'Freight rose during the holdout.',
  },
  {
    name: 'late_delivery_risk',
    problem: '1. Late delivery risk',
    status: 'held',
    kind: null,
    version: '1.0.0',
    verdict: 'Ready for ranking only',
    note: 'Its ranking did not work.',
  },
]
const OPTIONS = {
  data_end_date: '2018-08-21',
  latest_daily_date: '2018-09-18',
  latest_week_end: '2018-09-16',
  categories: ['bed_bath_table', 'toys'],
}

describe('errorMessage', () => {
  it('uses the API reason', () => {
    expect(errorMessage({ detail: 'late_delivery_risk is held' }, 503)).toBe(
      'late_delivery_risk is held',
    )
  })

  it('joins validation messages without their prefix', () => {
    const body = { detail: [{ msg: 'Value error, Send customer coordinates or a zip prefix, not both.' }] }
    expect(errorMessage(body, 422)).toBe('Send customer coordinates or a zip prefix, not both.')
  })

  it('falls back to the status', () => {
    expect(errorMessage(null, 500)).toBe('The request failed with status 500.')
  })
})

describe('date helpers', () => {
  it('adds days across a month end', () => {
    expect(addDays('2018-08-31', 1)).toBe('2018-09-01')
  })

  it('counts days between dates', () => {
    expect(daysBetween('2018-08-22', '2018-09-18')).toBe(27)
  })

  it('lists only Sundays the category rule can forecast', () => {
    expect(forecastableWeeks(OPTIONS)).toEqual([
      '2018-08-26',
      '2018-09-02',
      '2018-09-09',
      '2018-09-16',
    ])
  })
})

describe('Overview', () => {
  it('shows each verdict, and the held model as held with its reason', async () => {
    mockApi({ '/health': { body: HEALTH }, '/models': { body: MODELS } })
    renderPage(<App />)

    const held = (await screen.findByText('Late delivery risk')).closest('li')
    expect(held).not.toBeNull()
    expect(within(held as HTMLElement).getByText('Held')).toBeInTheDocument()
    expect(within(held as HTMLElement).getByText('Its ranking did not work.')).toBeInTheDocument()
    expect(screen.getByText('Ready')).toBeInTheDocument()
  })

  it('shows the API error instead of an empty page', async () => {
    mockApi({
      '/health': { body: HEALTH },
      '/models': { status: 503, body: { detail: 'The database is not loaded.' } },
    })
    renderPage(<App />)

    expect(await screen.findByRole('alert')).toHaveTextContent('The database is not loaded.')
  })

  it('always shows that the data is historical', async () => {
    mockApi({ '/health': { body: HEALTH }, '/models': { body: MODELS } })
    renderPage(<App />)
    expect(screen.getByText(/historical Olist orders from 2017 to 2018/)).toBeInTheDocument()
  })
})

describe('Review queue', () => {
  it('labels scores as training data and not probabilities', async () => {
    mockApi({
      '/reviews/queue': {
        body: {
          window_start: '2018-08-24',
          window_end: '2018-08-31',
          orders_in_window: 1311,
          scored_on_training_data: true,
          orders: [
            {
              rank: 1,
              order_id: '6d0940a8f5fba47562bb14cd97dfd6da',
              risk_score: 0.758,
              is_overdue: true,
              customer_state: 'RS',
              seller_id: 'c004e5ea15737026cecaee0447e00b75',
            },
          ],
        },
      },
    })
    renderPage(<App />, '/reviews')

    expect(await screen.findByText('6d0940a8')).toBeInTheDocument()
    expect(screen.getByText('Scored on training data.')).toBeInTheDocument()
    expect(screen.getByText(/aren't probabilities/)).toBeInTheDocument()
    expect(screen.getByText('0.76')).toBeInTheDocument()
  })
})

describe('Freight estimator', () => {
  it('requires weight and every dimension', async () => {
    mockApi({})
    renderPage(<App />, '/freight')

    for (const name of ['Weight (g)', 'Length (cm)', 'Height (cm)', 'Width (cm)', 'Price']) {
      expect(screen.getByLabelText(name)).toBeRequired()
    }
  })

  it('sends zips, not coordinates, and warns when distance is unknown', async () => {
    const user = userEvent.setup()
    let sent: Record<string, unknown> = {}
    mockApi({
      '/predict/freight': (init) => {
        sent = JSON.parse(String(init?.body))
        return { body: { predicted_freight: 27.31, distance_known: false } }
      },
    })
    renderPage(<App />, '/freight')

    await user.type(screen.getByLabelText('Customer zip prefix'), '99999')
    for (const [name, value] of [
      ['Weight (g)', '500'],
      ['Length (cm)', '20'],
      ['Height (cm)', '10'],
      ['Width (cm)', '15'],
      ['Price', '80'],
    ]) {
      await user.type(screen.getByLabelText(name), value)
    }
    await user.click(screen.getByRole('button', { name: 'Estimate freight' }))

    expect(await screen.findByText('27.31')).toBeInTheDocument()
    expect(screen.getByText('Distance unknown.')).toBeInTheDocument()
    expect(sent.customer_zip_prefix).toBe(99999)
    expect(sent).not.toHaveProperty('customer_lat')
  })

  it('builds blank optional fields as null', () => {
    const request = buildFreightRequest(
      {
        customer_state: 'SP',
        seller_state: 'RJ',
        customer_zip: '',
        seller_zip: '20040',
        customer_lat: '',
        customer_lng: '',
        seller_lat: '',
        seller_lng: '',
        weight: '500',
        length: '20',
        height: '10',
        width: '15',
        price: '80',
        quantity: '1',
        category: ' ',
      },
      'zip',
    )
    expect(request.customer_zip_prefix).toBeNull()
    expect(request.seller_zip_prefix).toBe(20040)
    expect(request.category).toBeNull()
  })
})

describe('Forecasts', () => {
  it('starts after the data ends and shows a rule error', async () => {
    const fetchMock = mockApi({
      '/forecast/options': { body: OPTIONS },
      '/forecast/orders': { status: 422, body: { error: 'invalid_input', detail: 'Out of range.' } },
      '/forecast/category': {
        body: { week_end: '2018-08-26', category: 'bed_bath_table', predicted_items: 120 },
      },
    })
    renderPage(<App />, '/forecasts')

    expect(await screen.findByText('Out of range.')).toBeInTheDocument()
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith('/api/forecast/orders?start=2018-08-22&days=28', {
        cache: 'no-store',
      }),
    )
    expect(await screen.findByText('120')).toBeInTheDocument()
  })
})

describe('ApiError', () => {
  it('keeps the status', () => {
    expect(new ApiError(503, 'held').status).toBe(503)
  })
})

describe('wrong or missing API', () => {
  it('explains a web page returned instead of data, instead of crashing', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response('<!doctype html><title>Another app</title>', {
        status: 200,
        headers: { 'Content-Type': 'text/html' },
      })),
    )
    renderPage(<App />)

    const alerts = await screen.findAllByRole('alert')
    expect(alerts[0]).toHaveTextContent(NOT_SHOPSENSE)
    expect(screen.getByRole('heading', { name: 'Overview' })).toBeInTheDocument()
  })

  it('explains an API that is not running', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => Promise.reject(new TypeError('Failed to fetch'))))
    renderPage(<App />)

    const alerts = await screen.findAllByRole('alert')
    expect(alerts[0]).toHaveTextContent(NOT_REACHABLE)
  })

  it('explains a proxy error without JSON', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('', { status: 502 })))
    renderPage(<App />)

    const alerts = await screen.findAllByRole('alert')
    expect(alerts[0]).toHaveTextContent(NOT_REACHABLE)
  })
})

describe('ErrorBoundary', () => {
  it('shows a message instead of a blank page when a page crashes', () => {
    const quiet = vi.spyOn(console, 'error').mockImplementation(() => {})
    function Broken(): never {
      throw new Error('Something broke')
    }
    renderPage(
      <ErrorBoundary>
        <Broken />
      </ErrorBoundary>,
    )

    expect(screen.getByRole('alert')).toHaveTextContent('Something broke')
    expect(screen.getByRole('button', { name: 'Reload' })).toBeInTheDocument()
    quiet.mockRestore()
  })
})
