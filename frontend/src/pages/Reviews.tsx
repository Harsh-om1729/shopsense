import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { api } from '../api/client'
import { Badge, ErrorMessage, Loading, ScoreNote, TrainingDataNote } from '../components/Status'
import { formatNumber, formatScore, shortId } from '../format'

const LIMITS = [20, 50, 100]

export function Reviews() {
  const [limit, setLimit] = useState(20)
  const queue = useQuery({ queryKey: ['reviews', limit], queryFn: () => api.reviewQueue(limit) })

  return (
    <>
      <h1>Review queue</h1>
      <p className="lead">
        Orders most likely to get a 1 or 2 star review, so support can contact those customers
        first.
      </p>
      <TrainingDataNote />

      <div className="controls">
        <label>
          Show
          <select value={limit} onChange={(event) => setLimit(Number(event.target.value))}>
            {LIMITS.map((value) => (
              <option key={value} value={value}>
                {value} orders
              </option>
            ))}
          </select>
        </label>
      </div>

      {queue.isPending && <Loading />}
      {queue.isError && <ErrorMessage error={queue.error} />}
      {queue.isSuccess && (
        <>
          <p className="muted">
            {formatNumber(queue.data.orders_in_window, 'whole')} orders reached their check-in
            point from {queue.data.window_start} to {queue.data.window_end}.
          </p>
          <ScoreNote />
          <div className="table-wrap">
            <table>
              <caption className="visually-hidden">Orders ranked by low-review risk</caption>
              <thead>
                <tr>
                  <th scope="col">Rank</th>
                  <th scope="col">Order</th>
                  <th scope="col" className="number">Score</th>
                  <th scope="col">Overdue</th>
                  <th scope="col">Customer state</th>
                  <th scope="col">Seller</th>
                </tr>
              </thead>
              <tbody>
                {queue.data.orders.map((order) => (
                  <tr key={order.order_id}>
                    <td>{order.rank}</td>
                    <td>
                      <code title={order.order_id}>{shortId(order.order_id)}</code>
                    </td>
                    <td className="number">{formatScore(order.risk_score)}</td>
                    <td>
                      {order.is_overdue ? <Badge tone="warning">Overdue</Badge> : 'No'}
                    </td>
                    <td>{order.customer_state}</td>
                    <td>
                      <code title={order.seller_id}>{shortId(order.seller_id)}</code>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </>
  )
}
