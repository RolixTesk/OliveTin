<template>
  <article
    class="metric-card"
    :data-metric="id"
    :style="{ '--metric-color': color }"
  >
    <div class="metric-heading">
      <div><span class="metric-kicker">{{ kicker }}</span><h2>{{ title }}</h2><p>{{ subtitle }}</p></div>
      <span
        class="metric-status"
        :data-stale="stale"
      >{{ error ? '查询失败' : !hasData ? '暂无数据' : stale ? '数据延迟' : '已更新' }}</span>
    </div>
    <div class="metric-selection">
      <slot />
    </div>
    <div class="metric-readings">
      <div
        v-for="(item, index) in summaries"
        :key="item.name"
      >
        <span class="metric-series-name"><i :style="{ background: palette[index % palette.length] }" />{{ item.name }}</span>
        <strong>{{ formatMetric(item.latest, unit) }}</strong>
        <span class="metric-statistics">均值 {{ formatMetric(item.average, unit) }} · 采样峰值 {{ formatMetric(item.peak, unit) }}</span>
      </div>
      <strong v-if="!summaries.length">—</strong>
    </div>
    <div
      ref="element"
      class="metric-chart"
      role="img"
      :aria-label="description"
    />
    <p
      v-if="!hasData || error"
      class="metric-empty"
    >
      {{ error ? '此指标暂时查询失败，稍后刷新重试。' : loading ? '正在读取官方监控历史…' : '当前时段没有监控记录。' }}
    </p>
    <p class="metric-footnote">
      {{ hasData ? `最新样本 ${latestTime}` : '缺失数据保留为空' }} · {{ periodLabel }}平均值
    </p>
  </article>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { init, use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { SVGRenderer } from 'echarts/renderers'
import { formatMetric, metricSummary, withGaps } from '../utils/systemMetrics.js'

use([LineChart, GridComponent, TooltipComponent, SVGRenderer])
const props = defineProps({
  id: { type: String, required: true },
  title: { type: String, required: true },
  kicker: { type: String, default: '' },
  subtitle: { type: String, default: '' },
  series: { type: Array, default: () => [] },
  unit: { type: String, default: '%' },
  period: { type: Number, default: 60 },
  start: { type: Number, default: undefined },
  end: { type: Number, default: undefined },
  color: { type: String, default: '#3b82f6' },
  loading: Boolean,
  error: Boolean
})
const element = ref(null)
const palette = computed(() => [props.color, '#a78bfa'])
const summaries = computed(() => props.series.map(series => ({ name: series.name, ...metricSummary(series.points, props.period) })))
const hasData = computed(() => summaries.value.some(item => item.latest !== null))
const stale = computed(() => summaries.value.some(item => item.stale))
const latestTime = computed(() => new Date(Math.max(...summaries.value.map(item => item.time || 0))).toLocaleTimeString())
const periodLabel = computed(() => props.period === 60 ? '1 分钟' : `${props.period / 60} 分钟`)
const description = computed(() => `${props.title}折线图。${summaries.value.map(item => `${item.name}最新 ${formatMetric(item.latest, props.unit)}，均值 ${formatMetric(item.average, props.unit)}`).join('；')}`)
let chart, resizeObserver, themeObserver

function render () {
  if (!chart) return
  const style = getComputedStyle(document.documentElement)
  const muted = style.getPropertyValue('--site-muted').trim()
  const dark = document.documentElement.dataset.theme === 'dark'
  chart.setOption({
    animation: false,
    color: palette.value,
    grid: { left: 8, right: 15, top: 12, bottom: 4, outerBoundsMode: 'same', containLabel: true },
    tooltip: {
      trigger: 'axis',
      renderMode: 'richText',
      confine: true,
      backgroundColor: dark ? '#111a2b' : '#f4f7fc',
      borderColor: dark ? '#334155' : '#cbd5e1',
      textStyle: { color: dark ? '#eef3fb' : '#172033', fontSize: 12 },
      valueFormatter: value => formatMetric(value, props.unit)
    },
    xAxis: {
      type: 'time',
      min: props.start,
      max: props.end,
      splitNumber: 3,
      axisLabel: { color: muted, fontSize: 11, hideOverlap: true, formatter: value => new Date(value).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) },
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: { show: false }
    },
    yAxis: {
      type: 'value',
      min: 0,
      max: props.unit === '%' ? 100 : undefined,
      interval: props.unit === '%' ? 25 : undefined,
      splitNumber: 3,
      axisLabel: { color: muted, fontSize: 11, formatter: value => props.unit === '%' ? `${value}%` : formatMetric(value, props.unit) },
      splitLine: { lineStyle: { color: dark ? '#ffffff14' : '#64748b22', type: 'dashed' } }
    },
    series: props.series.map((series, index) => ({
      name: series.name,
      type: 'line',
      data: withGaps(series.points, props.period),
      showSymbol: false,
      connectNulls: false,
      lineStyle: { width: 2.5 },
      areaStyle: props.series.length === 1 ? { opacity: 0.09 } : undefined,
      itemStyle: { color: palette.value[index % palette.value.length] }
    }))
  }, true)
}

watch(() => [props.series, props.period, props.start, props.end], render, { deep: true })
onMounted(() => {
  chart = init(element.value, null, { renderer: 'svg' })
  resizeObserver = new ResizeObserver(() => chart.resize())
  resizeObserver.observe(element.value)
  themeObserver = new MutationObserver(render)
  themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })
  render()
})
onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  themeObserver?.disconnect()
  chart?.dispose()
})
</script>
