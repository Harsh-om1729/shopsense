import { lazy, Suspense } from 'react'
import { Route, Routes } from 'react-router'

import { Layout } from './components/Layout'
import { Loading } from './components/Status'
import { Freight } from './pages/Freight'
import { Overview } from './pages/Overview'
import { Reviews } from './pages/Reviews'
import { Sellers } from './pages/Sellers'

// The chart library is large and only this page needs it, so it loads on demand.
const Forecasts = lazy(() =>
  import('./pages/Forecasts').then((module) => ({ default: module.Forecasts })),
)

function NotFound() {
  return (
    <>
      <h1>Page not found</h1>
      <p>Use the menu to choose a page.</p>
    </>
  )
}

export function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Overview />} />
        <Route path="reviews" element={<Reviews />} />
        <Route path="sellers" element={<Sellers />} />
        <Route path="freight" element={<Freight />} />
        <Route
          path="forecasts"
          element={
            <Suspense fallback={<Loading />}>
              <Forecasts />
            </Suspense>
          }
        />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  )
}
