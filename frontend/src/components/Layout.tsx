import { NavLink, Outlet, useLocation } from 'react-router'

import { ErrorBoundary } from './ErrorBoundary'

const PAGES = [
  { to: '/', label: 'Overview' },
  { to: '/reviews', label: 'Review queue' },
  { to: '/sellers', label: 'Sellers' },
  { to: '/freight', label: 'Freight' },
  { to: '/forecasts', label: 'Forecasts' },
]

export function Layout() {
  const location = useLocation()
  return (
    <div className="app">
      <header className="header">
        <div className="brand">
          <span className="brand-name">ShopSense</span>
          <span className="muted small">Predict problems before they happen.</span>
        </div>
        <nav aria-label="Main">
          <ul className="nav">
            {PAGES.map((page) => (
              <li key={page.to}>
                <NavLink to={page.to} end={page.to === '/'}>
                  {page.label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
      </header>
      <p className="data-banner">
        Built on historical Olist orders from 2017 to 2018, so dates and results describe that
        period.
      </p>
      <main className="main">
        {/* A new key per page clears an earlier crash when you move to another page. */}
        <ErrorBoundary key={location.pathname}>
          <Outlet />
        </ErrorBoundary>
      </main>
    </div>
  )
}
