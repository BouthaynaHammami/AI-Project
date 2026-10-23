import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { ChartRenderer } from './ChartRenderer'

afterEach(cleanup)

describe('ChartRenderer', () => {
	it('renders a legacy chart and allows selecting a compatible chart type', () => {
		render(
			<ChartRenderer
				config={{ title: 'Ventes', labels: ['1', '2'], values: [10, 20] }}
			/>,
		)

		const selector = screen.getByRole('combobox', { name: 'Type de graphique' }) as HTMLSelectElement
		expect(selector.value).toBe('bar')
		expect(Array.from(selector.options).map((option) => option.value)).toEqual([
			'bar',
			'line',
			'pie',
			'scatter',
		])

		fireEvent.change(selector, { target: { value: 'line' } })
		expect(selector.value).toBe('line')
	})

	it('does not offer pie charts for negative or multi-series data', () => {
		const { rerender } = render(
			<ChartRenderer config={{
				title: 'Évolution',
				type: 'line',
				labels: ['Janvier', 'Février'],
				series: [{ name: 'Nord', values: [-2, 4] }],
			}} />,
		)
		expect(screen.queryByRole('option', { name: 'Camembert' })).toBeNull()

		rerender(
			<ChartRenderer config={{
				title: 'Comparaison',
				type: 'bar',
				labels: ['Nord', 'Sud'],
				series: [
					{ name: '2025', values: [2, 4] },
					{ name: '2026', values: [3, 5] },
				],
			}} />,
		)
		expect(screen.queryByRole('option', { name: 'Camembert' })).toBeNull()
	})
})
