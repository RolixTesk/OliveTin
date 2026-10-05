import assert from 'node:assert/strict'
import test from 'node:test'
import { deviceChoices, formatMetric, metricSummary, selectedSeries, withGaps } from './systemMetrics.js'

test('missing metrics stay empty and gaps never become zero or connected lines', () => {
  assert.equal(metricSummary([]).latest, null)
  assert.equal(formatMetric(null), '—')
  assert.deepEqual(withGaps([[60000, 4], [120000, 6], [300000, 8]], 60), [[60000, 4], [120000, 6], [180000, null], [300000, 8]])
})

test('summaries use valid samples and report delayed source timestamps', () => {
  const summary = metricSummary([[60000, 10], [120000, null], [180000, 20]], 60, 400000)
  assert.equal(summary.latest, 20)
  assert.equal(summary.average, 15)
  assert.equal(summary.peak, 20)
  assert.equal(summary.stale, true)
  assert.equal(metricSummary([[180000, 20]], 60, 200000).stale, false)
  assert.equal(formatMetric(1250000, 'bit/s'), '1.25 Mbit/s')
})

test('disk and network selectors keep dimensions separate', () => {
  const metric = { series: [{ device: '/dev/vda3', name: '/', points: [[1, 50]] }, { device: '/dev/vda2', name: '/boot/efi', points: [[1, 1]] }] }
  assert.equal(deviceChoices(metric)[0].label, '/ · /dev/vda3')
  assert.deepEqual(selectedSeries(metric, '/dev/vda2')[0].points, [[1, 1]])
  assert.deepEqual(selectedSeries(metric, 'missing'), [])
})
