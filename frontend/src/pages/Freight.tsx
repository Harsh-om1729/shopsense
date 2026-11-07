import { useMutation } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'

import { api, BRAZIL_STATES, type BrazilState } from '../api/client'
import { ErrorMessage, Notice } from '../components/Status'
import { formatNumber } from '../format'
import { buildFreightRequest, type FormState, INITIAL, type LocationMode } from './freightRequest'

function StateSelect(props: {
  label: string
  value: BrazilState
  onChange: (value: BrazilState) => void
}) {
  return (
    <label>
      {props.label}
      <select
        value={props.value}
        onChange={(event) => props.onChange(event.target.value as BrazilState)}
      >
        {BRAZIL_STATES.map((state) => (
          <option key={state}>{state}</option>
        ))}
      </select>
    </label>
  )
}

function NumberField(props: {
  label: string
  value: string
  onChange: (value: string) => void
  required?: boolean
  min?: number
  max?: number
  step?: string
}) {
  return (
    <label>
      {props.label}
      <input
        type="number"
        inputMode="decimal"
        value={props.value}
        required={props.required}
        min={props.min}
        max={props.max}
        step={props.step ?? 'any'}
        onChange={(event) => props.onChange(event.target.value)}
      />
    </label>
  )
}

export function Freight() {
  const [form, setForm] = useState(INITIAL)
  const [mode, setMode] = useState<LocationMode>('zip')
  const estimate = useMutation({ mutationFn: api.freight })

  function update<K extends keyof FormState>(key: K) {
    return (value: FormState[K]) => setForm((current) => ({ ...current, [key]: value }))
  }

  function submit(event: FormEvent) {
    event.preventDefault()
    estimate.mutate(buildFreightRequest(form, mode))
  }

  return (
    <>
      <h1>Freight estimator</h1>
      <p className="lead">Estimate the freight for one product on a route, before listing it.</p>
      <Notice>
        Weight and dimensions are required. Without them, estimates were unreliable, because the
        model almost never saw a product missing them.
      </Notice>

      <form className="card form" onSubmit={submit}>
        <fieldset>
          <legend>Route</legend>
          <div className="field-row">
            <StateSelect
              label="Customer state"
              value={form.customer_state}
              onChange={update('customer_state')}
            />
            <StateSelect
              label="Seller state"
              value={form.seller_state}
              onChange={update('seller_state')}
            />
          </div>
          <div className="segmented" role="radiogroup" aria-label="Location type">
            {(['zip', 'coordinates'] as const).map((option) => (
              <label key={option} className="checkbox">
                <input
                  type="radio"
                  name="location"
                  checked={mode === option}
                  onChange={() => setMode(option)}
                />
                {option === 'zip' ? 'Zip prefixes' : 'Coordinates'}
              </label>
            ))}
          </div>
          {mode === 'zip' ? (
            <div className="field-row">
              <NumberField
                label="Customer zip prefix"
                value={form.customer_zip}
                onChange={update('customer_zip')}
                min={0}
                max={99999}
                step="1"
              />
              <NumberField
                label="Seller zip prefix"
                value={form.seller_zip}
                onChange={update('seller_zip')}
                min={0}
                max={99999}
                step="1"
              />
            </div>
          ) : (
            <div className="field-row">
              <NumberField label="Customer latitude" value={form.customer_lat} onChange={update('customer_lat')} min={-34} max={6} />
              <NumberField label="Customer longitude" value={form.customer_lng} onChange={update('customer_lng')} min={-74} max={-34} />
              <NumberField label="Seller latitude" value={form.seller_lat} onChange={update('seller_lat')} min={-34} max={6} />
              <NumberField label="Seller longitude" value={form.seller_lng} onChange={update('seller_lng')} min={-74} max={-34} />
            </div>
          )}
          <p className="muted small">Optional, but the estimate is rougher without a distance.</p>
        </fieldset>

        <fieldset>
          <legend>Product</legend>
          <div className="field-row">
            <NumberField label="Weight (g)" value={form.weight} onChange={update('weight')} required min={1} />
            <NumberField label="Length (cm)" value={form.length} onChange={update('length')} required min={1} />
            <NumberField label="Height (cm)" value={form.height} onChange={update('height')} required min={1} />
            <NumberField label="Width (cm)" value={form.width} onChange={update('width')} required min={1} />
          </div>
          <div className="field-row">
            <NumberField label="Price" value={form.price} onChange={update('price')} required min={0.01} />
            <NumberField label="Quantity" value={form.quantity} onChange={update('quantity')} required min={1} step="1" />
            <label>
              Category (optional)
              <input
                value={form.category}
                placeholder="e.g. toys"
                onChange={(event) => update('category')(event.target.value)}
              />
            </label>
          </div>
        </fieldset>

        <button type="submit" disabled={estimate.isPending}>
          {estimate.isPending ? 'Estimating…' : 'Estimate freight'}
        </button>
      </form>

      {estimate.isError && <ErrorMessage error={estimate.error} />}
      {estimate.isSuccess && (
        <section className="card result" aria-live="polite">
          <p className="muted small">Estimated freight per item</p>
          <p className="result-value">{formatNumber(estimate.data.predicted_freight)}</p>
          {!estimate.data.distance_known && (
            <div className="notice notice-warning" role="status">
              <strong>Distance unknown.</strong> No location was found for this route, so this
              estimate is rougher.
            </div>
          )}
        </section>
      )}
    </>
  )
}
