export function formatMetric (value, unit = '%') {
  if (!Number.isFinite(value)) return '—'
  if (unit === 'bit/s') {
    if (value >= 1e6) return `${(value / 1e6).toFixed(2)} Mbit/s`
    return `${(value / 1e3).toFixed(1)} Kbit/s`
  }
  return `${value.toFixed(unit === '%' ? 1 : 2)}${unit}`
}

export function metricSummary (points = [], period = 60, now = Date.now()) {
  const values = points.filter(([time, value]) => Number.isFinite(time) && Number.isFinite(value))
  if (!values.length) return { latest: null, average: null, peak: null, stale: true }
  const last = values.at(-1)
  return {
    latest: last[1],
    time: last[0],
    average: values.reduce((total, point) => total + point[1], 0) / values.length,
    peak: Math.max(...values.map(point => point[1])),
    stale: now - last[0] > Math.max(180, period * 3) * 1000
  }
}

export function withGaps (points = [], period = 60) {
  const result = []
  for (const point of points) {
    const previous = result.at(-1)
    if (previous && point[0] - previous[0] > period * 1500) result.push([previous[0] + period * 1000, null])
    result.push(point)
  }
  return result
}

export function deviceChoices (metric) {
  return (metric?.series || []).map(series => ({
    value: series.device,
    label: series.name && series.name !== series.device ? `${series.name} · ${series.device}` : series.device
  }))
}

export function selectedSeries (metric, device, name) {
  return (metric?.series || []).filter(series => device === undefined || series.device === device)
    .map(series => ({ ...series, name: name || series.name || '使用率' }))
}
