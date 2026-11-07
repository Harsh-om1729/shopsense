import type { Schemas } from '../api/client'
import { addDays } from '../format'

/** Return the Sundays after the data ends that the category rule can still forecast. */
export function forecastableWeeks(options: Schemas['ForecastOptions']) {
  const weeks: string[] = []
  for (let week = options.latest_week_end; week > options.data_end_date; week = addDays(week, -7)) {
    weeks.unshift(week)
  }
  return weeks
}
