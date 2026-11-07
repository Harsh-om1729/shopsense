import { useMutation, useQuery } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { api, BRAZIL_STATES, type BrazilState, type Schemas } from '../api/client'
import { ErrorMessage, Loading } from '../components/Status'
import { addDays, daysBetween, formatNumber } from '../format'
import { forecastableWeeks } from './forecastWeeks'

const MAX_DAYS = 28

function DailyForecast({ options }: { options: Schemas['ForecastOptions'] }) {
  const first = addDays(options.data_end_date, 1)
  const [start, setStart] = useState(first)
  const remaining = daysBetween(start, options.latest_daily_date) + 1
  const days = Math.max(1, Math.min(MAX_DAYS, remaining))

  const forecast = useQuery({
    queryKey: ['forecast-orders', start, days],
    queryFn: () => api.forecastOrders(start, days),
    enabled: remaining >= 1,
  })

  return (
    <section className="card" aria-labelledby="daily-title">
      <h2 id="daily-title">Daily orders forecast</h2>
      <p className="muted small">
        Each day is the average of the 28 days that ended four weeks earlier. It can forecast
        up to {options.latest_daily_date}.
      </p>
      <div className="controls">
        <label>
          Start date
          <input
            type="date"
            value={start}
            min={first}
            max={options.latest_daily_date}
            onChange={(event) => event.target.value && setStart(event.target.value)}
          />
        </label>
      </div>

      {forecast.isPending && <Loading />}
      {forecast.isError && <ErrorMessage error={forecast.error} />}
      {forecast.isSuccess && (
        <>
          <div className="chart" role="img" aria-label={`Daily orders forecast from ${start}`}>
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={forecast.data} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
                <CartesianGrid vertical={false} className="chart-grid" />
                <XAxis dataKey="date" tickLine={false} axisLine={false} minTickGap={24} className="chart-axis" />
                <YAxis tickLine={false} axisLine={false} width={44} className="chart-axis" />
                <Tooltip
                  formatter={(value) => [formatNumber(Number(value), 'whole'), 'Predicted orders']}
                  contentStyle={{ background: 'var(--surface-2)', border: '1px solid var(--border)' }}
                  itemStyle={{ color: 'var(--text)' }}
                  labelStyle={{ color: 'var(--text-2)' }}
                  cursor={{ stroke: 'var(--text-2)', strokeDasharray: '3 3' }}
                />
                <Line
                  type="monotone"
                  dataKey="predicted_orders"
                  className="chart-line"
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 4 }}
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <details>
            <summary>Show values</summary>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th scope="col">Date</th>
                    <th scope="col" className="number">Predicted orders</th>
                  </tr>
                </thead>
                <tbody>
                  {forecast.data.map((row) => (
                    <tr key={row.date}>
                      <td>{row.date}</td>
                      <td className="number">{formatNumber(row.predicted_orders, 'whole')}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        </>
      )}
    </section>
  )
}

function CategoryForecast({ options }: { options: Schemas['ForecastOptions'] }) {
  const weeks = forecastableWeeks(options)
  const [category, setCategory] = useState(options.categories[0] ?? '')
  const [week, setWeek] = useState(weeks[0] ?? options.latest_week_end)

  const forecast = useQuery({
    queryKey: ['forecast-category', week, category],
    queryFn: () => api.forecastCategory(week, category),
    enabled: category !== '',
  })

  return (
    <section className="card" aria-labelledby="category-title">
      <h2 id="category-title">Category demand</h2>
      <p className="muted small">Items sold in a week, for the 10 largest categories.</p>
      <div className="controls">
        <label>
          Category
          <select value={category} onChange={(event) => setCategory(event.target.value)}>
            {options.categories.map((name) => (
              <option key={name} value={name}>
                {name.replaceAll('_', ' ')}
              </option>
            ))}
          </select>
        </label>
        <label>
          Week ending
          <select value={week} onChange={(event) => setWeek(event.target.value)}>
            {weeks.map((sunday) => (
              <option key={sunday}>{sunday}</option>
            ))}
          </select>
        </label>
      </div>
      {forecast.isPending && <Loading />}
      {forecast.isError && <ErrorMessage error={forecast.error} />}
      {forecast.isSuccess && (
        <p className="result-value">
          {formatNumber(forecast.data.predicted_items, 'whole')} <span className="muted small">items</span>
        </p>
      )}
    </section>
  )
}

function DeliveryEstimate() {
  const [state, setState] = useState<BrazilState>('SP')
  const estimate = useMutation({ mutationFn: api.deliveryTime })

  function submit(event: FormEvent) {
    event.preventDefault()
    estimate.mutate(state)
  }

  return (
    <section className="card" aria-labelledby="delivery-title">
      <h2 id="delivery-title">Delivery time</h2>
      <p className="muted small">The median delivery time for customers in a state.</p>
      <form className="controls" onSubmit={submit}>
        <label>
          Customer state
          <select value={state} onChange={(event) => setState(event.target.value as BrazilState)}>
            {BRAZIL_STATES.map((name) => (
              <option key={name}>{name}</option>
            ))}
          </select>
        </label>
        <button type="submit" disabled={estimate.isPending}>
          Estimate
        </button>
      </form>
      {estimate.isError && <ErrorMessage error={estimate.error} />}
      {estimate.isSuccess && (
        <>
          <p className="result-value">
            {formatNumber(estimate.data.predicted_days, 'decimal')}{' '}
            <span className="muted small">days</span>
          </p>
          <p className="muted small">{estimate.data.note}</p>
        </>
      )}
    </section>
  )
}

export function Forecasts() {
  const options = useQuery({ queryKey: ['forecast-options'], queryFn: api.forecastOptions })

  return (
    <>
      <h1>Forecasts</h1>
      <p className="lead">
        These use simple rules, because on held-back data the trained models didn't clearly beat
        them.
      </p>
      {options.isPending && <Loading />}
      {options.isError && <ErrorMessage error={options.error} />}
      {options.isSuccess && (
        <div className="stack">
          <DailyForecast options={options.data} />
          <div className="two-columns">
            <CategoryForecast options={options.data} />
            <DeliveryEstimate />
          </div>
        </div>
      )}
    </>
  )
}
