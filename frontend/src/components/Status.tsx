import type { ReactNode } from 'react'

import { ApiError } from '../api/client'

export function Loading({ label = 'Loading…' }: { label?: string }) {
  return (
    <p className="muted" role="status">
      {label}
    </p>
  )
}

/** Show the API's reason, so a held model explains itself instead of failing silently. */
export function ErrorMessage({ error }: { error: unknown }) {
  const message =
    error instanceof ApiError || error instanceof Error ? error.message : 'Something went wrong.'
  return (
    <div className="notice notice-error" role="alert">
      <strong>Couldn't load this.</strong> {message}
    </div>
  )
}

export function Notice({ children }: { children: ReactNode }) {
  return <div className="notice">{children}</div>
}

type Tone = 'good' | 'warning' | 'critical' | 'neutral'

/** A label with text, so meaning never depends on colour alone. */
export function Badge({ tone, children }: { tone: Tone; children: ReactNode }) {
  return <span className={`badge badge-${tone}`}>{children}</span>
}

export function TrainingDataNote() {
  return (
    <Notice>
      <strong>Scored on training data.</strong> The final models learned from these same rows,
      so the scores look better than they would on new orders. Use them to order work, not to
      judge accuracy.
    </Notice>
  )
}

export function ScoreNote() {
  return (
    <p className="muted small">
      Scores rank rows from most to least at risk. They aren't probabilities, because
      conditions changed over time.
    </p>
  )
}
