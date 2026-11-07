import { useQuery } from '@tanstack/react-query'

import { api, type Schemas } from '../api/client'
import { Badge, ErrorMessage, Loading } from '../components/Status'

function verdictTone(model: Schemas['ModelInfo']) {
  if (model.status === 'held') return 'critical'
  if (model.verdict === 'Ready') return 'good'
  if (model.verdict === 'Use the simple rule') return 'neutral'
  return 'warning'
}

function HealthSummary() {
  const health = useQuery({ queryKey: ['health'], queryFn: api.health })
  if (health.isPending) return <Loading label="Checking the API…" />
  if (health.isError) return <ErrorMessage error={health.error} />

  const { status, database_ready, loaded } = health.data
  return (
    <section className="card" aria-labelledby="health-title">
      <h2 id="health-title">System</h2>
      <dl className="facts">
        <div>
          <dt>API</dt>
          <dd>
            <Badge tone={status === 'ok' ? 'good' : 'warning'}>
              {status === 'ok' ? 'Working' : 'Degraded'}
            </Badge>
          </dd>
        </div>
        <div>
          <dt>Database</dt>
          <dd>
            <Badge tone={database_ready ? 'good' : 'critical'}>
              {database_ready ? 'Loaded' : 'Not loaded'}
            </Badge>
          </dd>
        </div>
        <div>
          <dt>Packages loaded</dt>
          <dd>{loaded.length} of 7</dd>
        </div>
      </dl>
    </section>
  )
}

export function Overview() {
  const models = useQuery({ queryKey: ['models'], queryFn: api.models })

  return (
    <>
      <h1>Overview</h1>
      <p className="lead">
        Seven business problems were tested on held-back orders. Three use trained models,
        three use simple rules because the models didn't clearly beat them, and one is held.
      </p>
      <HealthSummary />

      <h2>Problems and verdicts</h2>
      {models.isPending && <Loading />}
      {models.isError && <ErrorMessage error={models.error} />}
      {models.isSuccess && (
        <ul className="model-grid">
          {models.data.map((model) => (
            <li key={model.name} className="card model-card">
              <div className="model-heading">
                <h3>{model.problem.replace(/^\d+\.\s*/, '')}</h3>
                <Badge tone={verdictTone(model)}>
                  {model.status === 'held' ? 'Held' : model.verdict}
                </Badge>
              </div>
              <p className="muted small">
                {model.kind === 'regression' || model.kind === 'ranking' || model.kind === 'alert'
                  ? 'Trained model'
                  : model.status === 'held'
                    ? 'Not in use'
                    : 'Simple rule'}{' '}
                · <code>{model.name}</code>
              </p>
              {model.note && <p>{model.note}</p>}
            </li>
          ))}
        </ul>
      )}
    </>
  )
}
