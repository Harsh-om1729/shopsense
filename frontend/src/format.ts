/** Formatting helpers. Values carry no currency, because the data doesn't state one. */

const decimal = new Intl.NumberFormat('en', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
const whole = new Intl.NumberFormat('en', { maximumFractionDigits: 0 })

export function formatNumber(value: number | null | undefined, digits: 'whole' | 'decimal' = 'decimal') {
  if (value === null || value === undefined || Number.isNaN(value)) return 'Not known'
  return (digits === 'whole' ? whole : decimal).format(value)
}

export function formatScore(value: number) {
  return value.toFixed(2)
}

/** Show the start of an ID, since the full hash is long. The full value stays in a tooltip. */
export function shortId(id: string) {
  return id.slice(0, 8)
}

/** Add days to a YYYY-MM-DD date without time zone surprises. */
export function addDays(isoDate: string, days: number) {
  const date = new Date(`${isoDate}T00:00:00Z`)
  date.setUTCDate(date.getUTCDate() + days)
  return date.toISOString().slice(0, 10)
}

export function daysBetween(start: string, end: string) {
  const milliseconds = Date.parse(`${end}T00:00:00Z`) - Date.parse(`${start}T00:00:00Z`)
  return Math.round(milliseconds / 86_400_000)
}
