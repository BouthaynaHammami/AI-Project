import { useState } from 'react'
import {
	Bar,
	BarChart,
	CartesianGrid,
	Cell,
	Legend,
	Line,
	LineChart,
	Pie,
	PieChart,
	ResponsiveContainer,
	Scatter,
	ScatterChart,
	Tooltip,
	XAxis,
	YAxis,
} from 'recharts'
import type { ChartConfig, ChartSeries, ChartType } from '../types'

const COLORS = ['#2563EB', '#0B1F3A', '#3B82F6', '#0B1F3A', '#2563EB']

type NormalizedChart = {
	type: ChartType
	title: string
	x_label: string
	y_label: string
	labels: string[]
	series: ChartSeries[]
}

function normalizeChart(config: ChartConfig): NormalizedChart | null {
	if (!config || typeof config !== 'object') return null
	const labels = Array.isArray(config.labels) ? config.labels.map(String) : []
	let series: ChartSeries[]
	if (Array.isArray(config.series)) {
		if (config.series.some((item) => !item || typeof item !== 'object')) return null
		series = config.series
	} else if (Array.isArray(config.values)) {
		series = [{ name: config.title || 'Valeur', values: config.values }]
	} else {
		return null
	}
	if (!labels.length || !series.length || series.some((item) =>
		!Array.isArray(item.values)
		|| item.values.length !== labels.length
		|| item.values.some((value) => typeof value !== 'number' || !Number.isFinite(value))
	)) return null
	if (!['bar', 'line', 'pie', 'scatter'].includes(config.type ?? 'bar')) return null
	return {
		type: config.type ?? 'bar',
		title: config.title || 'Résultat',
		x_label: config.x_label ?? '',
		y_label: config.y_label ?? '',
		labels,
		series,
	}
}

export function ChartRenderer({ config }: { config: ChartConfig }) {
	const chart = normalizeChart(config)
	const [selectedType, setSelectedType] = useState<ChartType>(chart?.type ?? 'bar')
	if (!chart) return null

	const numericLabels = chart.labels.every((label) => label.trim() !== '' && Number.isFinite(Number(label)))
	const pieAvailable = chart.labels.length <= 8 && chart.series.length === 1 && chart.series[0].values.every((value) => value >= 0)
	const availableTypes: ChartType[] = ['bar', 'line', ...(pieAvailable ? ['pie' as const] : []), ...(numericLabels ? ['scatter' as const] : [])]
	const type = availableTypes.includes(selectedType)
		? selectedType
		: availableTypes.includes(chart.type)
			? chart.type
			: 'bar'
	const rows = chart.labels.map((label, index) => ({
		label,
		...Object.fromEntries(chart.series.map((seriesItem) => [seriesItem.name, seriesItem.values[index]])),
	}))
	const scatterRows = chart.series.map((seriesItem) => ({
		name: seriesItem.name,
		data: chart.labels.map((label, index) => ({
			x: Number(label),
			y: seriesItem.values[index],
		})),
	}))
	const axisLabel = (value: string) => value ? { value, position: 'insideBottom' as const, offset: -3 } : undefined

	return (
		<div className="chart-renderer">
			<div className="chart-renderer-heading">
				<strong>{chart.title}</strong>
				{availableTypes.length > 1 && (
					<label>
						<span className="sr-only">Type de graphique</span>
						<select value={type} onChange={(event) => {
							const nextType = availableTypes.find((availableType) => availableType === event.target.value)
							if (nextType) setSelectedType(nextType)
						}}>
							{availableTypes.map((availableType) => (
								<option key={availableType} value={availableType}>
									{{ bar: 'Barres', line: 'Lignes', pie: 'Camembert', scatter: 'Nuage de points' }[availableType]}
								</option>
							))}
						</select>
					</label>
				)}
			</div>
			<div className="chart-renderer-canvas">
				<ResponsiveContainer width="100%" height="100%">
					{type === 'pie' ? (
						<PieChart>
							<Tooltip />
							<Legend />
							<Pie data={rows} dataKey={chart.series[0].name} nameKey="label" cx="50%" cy="50%" outerRadius="72%" label>
								{rows.map((row, index) => <Cell key={row.label} fill={COLORS[index % COLORS.length]} />)}
							</Pie>
						</PieChart>
					) : type === 'scatter' ? (
						<ScatterChart margin={{ top: 12, right: 20, bottom: 24, left: 8 }}>
							<CartesianGrid stroke="#DBEAFE" />
							<XAxis type="number" dataKey="x" name={chart.x_label || 'X'} label={axisLabel(chart.x_label)} />
							<YAxis type="number" dataKey="y" name={chart.y_label || 'Valeur'} label={chart.y_label ? { value: chart.y_label, angle: -90, position: 'insideLeft' } : undefined} />
							<Tooltip cursor={{ strokeDasharray: '3 3' }} />
							<Legend />
							{scatterRows.map((seriesItem, index) => (
								<Scatter key={seriesItem.name} name={seriesItem.name} data={seriesItem.data} fill={COLORS[index % COLORS.length]} />
							))}
						</ScatterChart>
					) : type === 'line' ? (
						<LineChart data={rows} margin={{ top: 12, right: 18, bottom: 24, left: 8 }}>
							<CartesianGrid stroke="#DBEAFE" />
							<XAxis dataKey="label" label={axisLabel(chart.x_label)} />
							<YAxis label={chart.y_label ? { value: chart.y_label, angle: -90, position: 'insideLeft' } : undefined} />
							<Tooltip />
							<Legend />
							{chart.series.map((seriesItem, index) => (
								<Line key={seriesItem.name} type="monotone" dataKey={seriesItem.name} name={seriesItem.name} stroke={COLORS[index % COLORS.length]} strokeWidth={2} dot={false} />
							))}
						</LineChart>
					) : (
						<BarChart data={rows} margin={{ top: 12, right: 18, bottom: 24, left: 8 }}>
							<CartesianGrid stroke="#DBEAFE" vertical={false} />
							<XAxis dataKey="label" label={axisLabel(chart.x_label)} />
							<YAxis label={chart.y_label ? { value: chart.y_label, angle: -90, position: 'insideLeft' } : undefined} />
							<Tooltip />
							<Legend />
							{chart.series.map((seriesItem, index) => (
								<Bar key={seriesItem.name} dataKey={seriesItem.name} name={seriesItem.name} fill={COLORS[index % COLORS.length]} radius={[3, 3, 0, 0]} />
							))}
						</BarChart>
					)}
				</ResponsiveContainer>
			</div>
		</div>
	)
}
