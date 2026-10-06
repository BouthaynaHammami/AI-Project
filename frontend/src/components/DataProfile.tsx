import { AlertTriangle, BarChart3, Columns3, Rows3, ShieldAlert } from 'lucide-react'
import { useEffect, useState } from 'react'
import { updatePiiPreferences, type DataProfile as DataProfileType, type PiiPreference, type PiiReport } from '../services/fileService'

type Props = {
  profile?: DataProfileType | null
  datasetId: number
  piiReport: PiiReport
  piiPreferences: Record<string, PiiPreference>
}

const formatValue = (value: unknown) => {
  if (value == null) return '—'
  if (typeof value === 'number') return value.toLocaleString('fr-FR', { maximumFractionDigits: 2 })
  return String(value)
}

export function DataProfile({ profile, datasetId, piiReport, piiPreferences }: Props) {
  const [preferences, setPreferences] = useState(piiPreferences)
  const [savingColumn, setSavingColumn] = useState<string | null>(null)
  const [preferenceError, setPreferenceError] = useState('')

  useEffect(() => setPreferences(piiPreferences), [piiPreferences])

  const savePreference = async (column: string, preference: PiiPreference) => {
    const next = { ...preferences, [column]: preference }
    setSavingColumn(column)
    setPreferenceError('')
    try {
      const saved = await updatePiiPreferences(datasetId, next)
      setPreferences(saved)
    } catch {
      setPreferenceError('La préférence de confidentialité n’a pas pu être enregistrée.')
    } finally {
      setSavingColumn(null)
    }
  }

  return (
    <section className="data-profile" aria-label="Profil de qualité des données">
      {piiReport.column_count > 0 && (
        <div className="pii-report-banner" role="region" aria-label="Données personnelles détectées">
          <div className="pii-report-heading">
            <ShieldAlert size={17} aria-hidden="true" />
            <strong>{piiReport.column_count} colonne{piiReport.column_count > 1 ? 's' : ''} sensible{piiReport.column_count > 1 ? 's' : ''} détectée{piiReport.column_count > 1 ? 's' : ''}</strong>
          </div>
          <p>Par défaut, les valeurs détectées sont masquées avant tout envoi à l’IA.</p>
          <div className="pii-report-columns">
            {piiReport.columns.map((column) => (
              <div className="pii-report-column" key={`${column.position}-${column.name}`}>
                <span>
                  <strong>{column.name}</strong>
                  <small>{column.category} · {column.values_touched.toLocaleString('fr-FR')} valeur{column.values_touched > 1 ? 's' : ''} · confiance {column.confidence === 'high' ? 'élevée' : 'moyenne'}</small>
                </span>
                <label>
                  <span className="sr-only">Action pour {column.name}</span>
                  <select
                    value={preferences[column.name] ?? 'mask'}
                    disabled={savingColumn !== null}
                    onChange={(event) => void savePreference(column.name, event.target.value as PiiPreference)}
                  >
                    <option value="exclude">Exclure de l’analyse</option>
                    <option value="mask">Masquer avant l’IA</option>
                    <option value="allow">Autoriser l’envoi à l’IA</option>
                  </select>
                </label>
              </div>
            ))}
          </div>
          {preferenceError && <p className="pii-preference-error" role="alert">{preferenceError}</p>}
        </div>
      )}
      {profile && <>
      <div className="data-profile-heading">
        <div>
          <span className="section-kicker">QUALITÉ DES DONNÉES</span>
          <h3>Profil du fichier</h3>
        </div>
        {profile.sampled_rows < profile.row_count && (
          <span className="profile-sample-note">
            Profil calculé sur {profile.sampled_rows.toLocaleString('fr-FR')} lignes
          </span>
        )}
      </div>

      <div className="profile-summary">
        <article className="profile-summary-card">
          <Rows3 size={17} aria-hidden="true" />
          <strong>{profile.row_count.toLocaleString('fr-FR')}</strong>
          <span>Lignes</span>
        </article>
        <article className="profile-summary-card">
          <Columns3 size={17} aria-hidden="true" />
          <strong>{profile.column_count.toLocaleString('fr-FR')}</strong>
          <span>Colonnes</span>
        </article>
        <article className="profile-summary-card">
          <BarChart3 size={17} aria-hidden="true" />
          <strong>{profile.duplicate_rows.toLocaleString('fr-FR')}</strong>
          <span>Lignes en doublon</span>
        </article>
      </div>

      {profile.alerts.length > 0 && (
        <div className="profile-alerts" aria-label="Alertes de qualité">
          {profile.alerts.map((alert, index) => (
            <div className={`profile-alert profile-alert-${alert.severity}`} key={`${alert.type}-${alert.column}-${index}`}>
              <AlertTriangle size={16} aria-hidden="true" />
              <span>{alert.message}</span>
            </div>
          ))}
        </div>
      )}

      <div className="profile-columns-wrap">
        <table className="profile-columns-table">
          <thead>
            <tr>
              <th>Colonne</th>
              <th>Type détecté</th>
              <th>Valeurs manquantes</th>
              <th>Valeurs uniques</th>
              <th>Détails</th>
            </tr>
          </thead>
          <tbody>
            {profile.columns.map((column) => (
              <tr key={`${column.position}-${column.name}`}>
                <td>{column.name || `Colonne ${column.position + 1}`}</td>
                <td><span className="profile-type">{column.detected_type}</span></td>
                <td>
                  <div className="profile-missing-cell">
                    <div
                      className="profile-missing-track"
                      role="img"
                      aria-label={`${column.missing_percentage} % de valeurs manquantes`}
                    >
                      <span style={{ width: `${Math.min(column.missing_percentage, 100)}%` }} />
                    </div>
                    <span>{column.missing_percentage.toLocaleString('fr-FR')} %</span>
                  </div>
                </td>
                <td>{column.unique_count.toLocaleString('fr-FR')}</td>
                <td className="profile-details">
                  {column.statistics && (
                    <span>
                      Min {formatValue(column.statistics.min)} · Max {formatValue(column.statistics.max)}
                      {' · '}Moy. {formatValue(column.statistics.mean)} · Méd. {formatValue(column.statistics.median)}
                    </span>
                  )}
                  {column.date_range && (
                    <span>{formatValue(column.date_range.min)} → {formatValue(column.date_range.max)}</span>
                  )}
                  {column.top_values?.map((item, index) => (
                    <span key={`${column.position}-top-${index}`}>
                      {formatValue(item.value)} ({item.count.toLocaleString('fr-FR')})
                    </span>
                  ))}
                  {!column.statistics && !column.date_range && !column.top_values?.length && '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      </>}
    </section>
  )
}
