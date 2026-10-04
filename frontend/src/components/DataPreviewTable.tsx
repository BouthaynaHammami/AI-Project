import { Rows3 } from 'lucide-react'
import type { DatasetPreview } from '../services/fileService'
import { DataProfile } from './DataProfile'

type Props = { datasets: DatasetPreview[] }

function SingleTable({ dataset }: { dataset: DatasetPreview }) {
  return <section className="preview-card"><div className="preview-header"><div><span className="section-kicker">APERÇU DU FICHIER</span><h2>{dataset.filename}</h2></div><span className="success-badge">● Données prêtes</span></div><div className="stats-row"><div><strong>{dataset.row_count.toLocaleString('fr-FR')}</strong><span>Lignes</span></div><div><strong>{dataset.column_count}</strong><span>Colonnes</span></div><div className="columns-stat"><Rows3 size={16} /><span>{dataset.column_names.join(' · ')}</span></div></div><div className="table-wrap"><table><thead><tr>{dataset.column_names.map((column, index) => <th key={`${column}-${index}`}>{column}</th>)}</tr></thead><tbody>{dataset.preview.map((row, rowIndex) => <tr key={rowIndex}>{dataset.column_names.map((column, columnIndex) => <td key={`${column}-${columnIndex}`}>{String(row[column] ?? '')}</td>)}</tr>)}</tbody></table></div>{dataset.profile && <DataProfile profile={dataset.profile} />}</section>
}

export function DataPreviewTable({ datasets }: Props) {
  if (!datasets.length) return <section className="preview-card empty-state"><Rows3 size={22} /><p>Aucun aperçu disponible. Importez un fichier pour afficher ses données.</p></section>
  return <>{datasets.map((dataset) => <SingleTable key={dataset.dataset_id} dataset={dataset} />)}</>
}