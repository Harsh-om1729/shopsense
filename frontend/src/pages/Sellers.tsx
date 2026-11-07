import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { api } from '../api/client'
import { Badge, ErrorMessage, Loading, Notice, ScoreNote, TrainingDataNote } from '../components/Status'
import { formatNumber, formatScore, shortId } from '../format'

const LIMITS = [20, 50, 100]

export function Sellers() {
  const [limit, setLimit] = useState(20)
  const [alertsOnly, setAlertsOnly] = useState(true)
  const sellers = useQuery({
    queryKey: ['sellers', limit, alertsOnly],
    queryFn: () => api.sellersAtRisk(limit, alertsOnly),
  })

  return (
    <>
      <h1>Sellers at risk</h1>
      <p className="lead">Active sellers likely to make no sale in the next 60 days.</p>
      <TrainingDataNote />
      <Notice>
        <strong>Check revenue and recency too.</strong> On the holdout, simply sorting by days
        since the last sale caught more at-risk revenue than the model did.
      </Notice>

      <div className="controls">
        <label>
          Show
          <select value={limit} onChange={(event) => setLimit(Number(event.target.value))}>
            {LIMITS.map((value) => (
              <option key={value} value={value}>
                {value} sellers
              </option>
            ))}
          </select>
        </label>
        <label className="checkbox">
          <input
            type="checkbox"
            checked={alertsOnly}
            onChange={(event) => setAlertsOnly(event.target.checked)}
          />
          Alerts only
        </label>
      </div>

      {sellers.isPending && <Loading />}
      {sellers.isError && <ErrorMessage error={sellers.error} />}
      {sellers.isSuccess && (
        <>
          <p className="muted">
            Snapshot from {sellers.data.snapshot_date}:{' '}
            {formatNumber(sellers.data.alerts_in_snapshot, 'whole')} alerts among{' '}
            {formatNumber(sellers.data.sellers_in_snapshot, 'whole')} active sellers.
          </p>
          <ScoreNote />
          <div className="table-wrap">
            <table>
              <caption className="visually-hidden">Sellers ranked by inactivity risk</caption>
              <thead>
                <tr>
                  <th scope="col">Seller</th>
                  <th scope="col">State</th>
                  <th scope="col" className="number">Score</th>
                  <th scope="col">Alert</th>
                  <th scope="col" className="number">Days since last sale</th>
                  <th scope="col" className="number">Revenue, last 90 days</th>
                </tr>
              </thead>
              <tbody>
                {sellers.data.sellers.map((seller) => (
                  <tr key={seller.seller_id}>
                    <td>
                      <code title={seller.seller_id}>{shortId(seller.seller_id)}</code>
                    </td>
                    <td>{seller.seller_state ?? 'Not known'}</td>
                    <td className="number">{formatScore(seller.risk_score)}</td>
                    <td>{seller.is_alert ? <Badge tone="warning">Alert</Badge> : 'No'}</td>
                    <td className="number">{formatNumber(seller.days_since_last_sale, 'whole')}</td>
                    <td className="number">{formatNumber(seller.revenue_90d)}</td>
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
