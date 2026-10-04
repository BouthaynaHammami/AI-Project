import { useEffect, useState } from 'react'
import logoUrl from '../../../ai-data-analyst-icon.jpg'
import { getPublicSharedAnalysis, type PublicSharedAnalysis as SharedAnalysis } from '../services/analysisService'
import type { ChartConfig } from '../types'
import { ChartRenderer } from './ChartRenderer'

type Props = {
  token: string
}

export function PublicSharedAnalysis({ token }: Props) {
  const [analysis, setAnalysis] = useState<SharedAnalysis | null>(null)
  const [unavailable, setUnavailable] = useState(false)

  useEffect(() => {
    let active = true
    const previousTitle = document.title
    const robots = document.querySelector('meta[name="robots"]') ?? document.createElement('meta')
    const createdRobots = !robots.isConnected
    robots.setAttribute('name', 'robots')
    robots.setAttribute('content', 'noindex, nofollow, noarchive')
    if (createdRobots) document.head.appendChild(robots)
    document.title = 'Analyse partagée · AI Data Analyst'
    getPublicSharedAnalysis(token)
      .then((result) => {
        if (active) setAnalysis(result)
      })
      .catch(() => {
        if (active) setUnavailable(true)
      })
    return () => {
      active = false
      document.title = previousTitle
      if (createdRobots) robots.remove()
    }
  }, [token])

  let chart: ChartConfig | null = null
  try {
    chart = analysis?.chart_config ? JSON.parse(analysis.chart_config) as ChartConfig : null
  } catch {
    chart = null
  }

  return (
    <main className="public-share-page">
      <header className="public-share-header">
        <div className="public-share-brand">
          <img src={logoUrl} alt="" />
          <span>AI Data <strong>Analyst</strong></span>
        </div>
        <span className="public-share-label">Analyse partagée</span>
      </header>
      {analysis ? (
        <article className="public-share-content">
          <div className="public-share-meta">
            <span className="workspace-kicker">RAPPORT D’ANALYSE</span>
            <time dateTime={analysis.created_at}>
              {new Date(analysis.created_at).toLocaleString('fr-FR', {
                dateStyle: 'long',
                timeStyle: 'short',
              })}
            </time>
          </div>
          <section className="public-share-question">
            <h1>{analysis.question}</h1>
          </section>
          <section className="public-share-answer" aria-label="Réponse de l’analyse">
            <h2>Réponse</h2>
            <p>{analysis.answer}</p>
          </section>
          {chart && (
            <section className="public-share-chart" aria-label="Graphique de l’analyse">
              <ChartRenderer config={chart} />
            </section>
          )}
        </article>
      ) : unavailable ? (
        <section className="public-share-unavailable" role="status">
          <h1>Ce lien n’est plus disponible</h1>
          <p>Il a peut-être expiré ou été révoqué par son propriétaire.</p>
        </section>
      ) : (
        <p className="public-share-loading" role="status">Chargement de l’analyse…</p>
      )}
    </main>
  )
}
