/**
 * Calls the ShopSense API. Types come from src/api/schema.d.ts, which is
 * generated from the API itself, so a changed field fails the build.
 */
import type { components } from './schema'

export type Schemas = components['schemas']
export type BrazilState = Schemas['DeliveryRequest']['customer_state']
export type FreightRequest = Schemas['FreightRequest']

// In development, Vite forwards /api to FastAPI. A deployed site sets VITE_API_BASE.
const API_BASE: string = import.meta.env.VITE_API_BASE ?? '/api'

export const BRAZIL_STATES = [
  'AC', 'AL', 'AM', 'AP', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 'MG', 'MS', 'MT', 'PA',
  'PB', 'PE', 'PI', 'PR', 'RJ', 'RN', 'RO', 'RR', 'RS', 'SC', 'SE', 'SP', 'TO',
] as const satisfies readonly BrazilState[]

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

/** Return the API's own explanation, so the page shows the real reason. */
export function errorMessage(body: unknown, status: number): string {
  const detail = (body as { detail?: unknown } | null)?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => (item as { msg?: unknown }).msg)
      .filter((message): message is string => typeof message === 'string')
      .map((message) => message.replace(/^Value error, /, ''))
    if (messages.length > 0) return messages.join(' ')
  }
  return `The request failed with status ${status}.`
}

export const NOT_REACHABLE =
  "Can't reach the ShopSense API. Start it with: uv run uvicorn api.main:app --reload"
export const NOT_SHOPSENSE =
  "Got a web page instead of ShopSense data, so another program may be using the API's port. " +
  'Run the ShopSense API on another port, such as 8010, and start the site with ' +
  'SHOPSENSE_API_URL=http://127.0.0.1:8010 npm run dev'

/** Read a JSON body, or return undefined if the reply isn't JSON. */
async function readJson(response: Response): Promise<unknown> {
  const type = response.headers.get('content-type') ?? ''
  if (!type.includes('application/json')) return undefined
  return response.json().catch(() => undefined)
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    // Skip the browser cache, so a stale reply from another app is never reused.
    response = await fetch(`${API_BASE}${path}`, { ...init, cache: 'no-store' })
  } catch {
    throw new ApiError(0, NOT_REACHABLE)
  }
  const body = await readJson(response)
  if (body === undefined) {
    // A success without JSON means something other than ShopSense answered.
    // Treating it as data would crash the page, so it becomes a clear error.
    throw new ApiError(response.status, response.ok ? NOT_SHOPSENSE : NOT_REACHABLE)
  }
  if (!response.ok) throw new ApiError(response.status, errorMessage(body, response.status))
  return body as T
}

function post<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export const api = {
  health: () => request<Schemas['Health']>('/health'),
  models: () => request<Schemas['ModelInfo'][]>('/models'),
  reviewQueue: (limit: number) =>
    request<Schemas['ReviewQueue']>(`/reviews/queue?limit=${limit}`),
  sellersAtRisk: (limit: number, alertsOnly: boolean) =>
    request<Schemas['SellerRiskList']>(
      `/sellers/at-risk?limit=${limit}&alerts_only=${alertsOnly}`,
    ),
  forecastOptions: () => request<Schemas['ForecastOptions']>('/forecast/options'),
  forecastOrders: (start: string, days: number) =>
    request<Schemas['DailyForecast'][]>(
      `/forecast/orders?start=${encodeURIComponent(start)}&days=${days}`,
    ),
  forecastCategory: (weekEnd: string, category: string) =>
    request<Schemas['CategoryForecast']>(
      `/forecast/category?week_end=${encodeURIComponent(weekEnd)}&category=${encodeURIComponent(category)}`,
    ),
  deliveryTime: (customerState: BrazilState) =>
    post<Schemas['DeliveryResponse']>('/predict/delivery-time', {
      customer_state: customerState,
    }),
  freight: (body: FreightRequest) => post<Schemas['FreightResponse']>('/predict/freight', body),
}
