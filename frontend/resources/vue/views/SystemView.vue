<template>
  <div class="system-view">
    <div class="services-heading system-heading">
      <div><span class="eyebrow">ROLIXTESK · SYSTEM</span><h1>每一刻，都有迹可循。</h1><p>资源与流量的变化，尽在眼前。</p></div>
      <RouterLink
        class="system-service-link"
        to="/services"
      >
        管理服务 ↗
      </RouterLink>
    </div>
    <div class="system-toolbar">
      <div>
        <span class="system-source"><i />阿里云云监控</span><p>{{ sourceInfo }}</p>
        <p
          class="system-update"
          aria-live="polite"
        >
          {{ loading ? '正在读取官方监控历史…' : `每分钟更新 · ${collectedAt ? `查询于 ${new Date(collectedAt).toLocaleString()}` : '等待首次查询'}` }}
        </p>
      </div>
      <div class="system-controls">
        <div
          class="system-ranges"
          role="group"
          aria-label="监控时间范围"
        >
          <button
            v-for="item in ranges"
            :key="item.value"
            type="button"
            :aria-pressed="window === item.value"
            @click="changeRange(item.value)"
          >
            {{ item.label }}
          </button>
        </div>
        <button
          class="system-refresh"
          type="button"
          :disabled="loading"
          @click="refresh"
        >
          {{ loading ? '读取中…' : '刷新' }}
        </button>
      </div>
    </div>
    <p
      v-if="error"
      class="service-alert"
      role="alert"
    >
      {{ error }}
    </p>
    <div
      class="system-primary-grid"
      :aria-busy="loading"
    >
      <MetricChart
        v-bind="chartProps"
        id="cpu"
        title="CPU 使用率"
        kicker="01 / COMPUTE"
        subtitle="处理器的忙碌程度"
        :series="selectedSeries(metrics.cpu, undefined, 'CPU')"
        :error="!!metrics.cpu?.error"
      />
      <MetricChart
        v-bind="chartProps"
        id="memory"
        title="内存使用率"
        kicker="02 / MEMORY"
        subtitle="实际使用，不含可回收缓存"
        color="#10b981"
        :series="selectedSeries(metrics.memory, undefined, '内存')"
        :error="!!metrics.memory?.error"
      />
      <MetricChart
        v-bind="chartProps"
        id="disk"
        title="硬盘使用率"
        kicker="03 / STORAGE"
        subtitle="文件系统已用空间占比"
        color="#f59e0b"
        :series="selectedSeries(metrics.disk, disk)"
        :error="!!metrics.disk?.error"
      >
        <label for="system-disk">分区</label><select
          id="system-disk"
          v-model="disk"
          :disabled="!disks.length"
        >
          <option
            v-for="item in disks"
            :key="item.value"
            :value="item.value"
          >
            {{ item.label }}
          </option><option v-if="!disks.length">
            暂无分区
          </option>
        </select>
      </MetricChart>
    </div>
    <div class="system-secondary-grid">
      <MetricChart
        v-bind="chartProps"
        id="load"
        title="系统负载"
        kicker="04 / LOAD"
        subtitle="运行与等待中的任务数"
        unit=""
        color="#6366f1"
        :series="[...selectedSeries(metrics.load1, undefined, '1 分钟'), ...selectedSeries(metrics.load5, undefined, '5 分钟')]"
        :error="!!(metrics.load1?.error || metrics.load5?.error)"
      />
      <MetricChart
        v-bind="chartProps"
        id="network"
        title="网络速率"
        kicker="05 / NETWORK"
        subtitle="所选网卡的接收与发送速率"
        unit="bit/s"
        color="#06b6d4"
        :series="[...selectedSeries(metrics.networkIn, network, '接收'), ...selectedSeries(metrics.networkOut, network, '发送')]"
        :error="!!(metrics.networkIn?.error || metrics.networkOut?.error)"
      >
        <label for="system-network">网卡</label><select
          id="system-network"
          v-model="network"
          :disabled="!networks.length"
        >
          <option
            v-for="item in networks"
            :key="item.value"
            :value="item.value"
          >
            {{ item.label }}
          </option><option v-if="!networks.length">
            暂无网卡
          </option>
        </select>
      </MetricChart>
    </div>
    <p class="system-caption">
      曲线来自已有云监控记录。空白表示没有样本，采样峰值为当前区间各统计周期平均值中的最大值。
    </p>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import MetricChart from '../components/MetricChart.vue'
import { deviceChoices, selectedSeries } from '../utils/systemMetrics.js'
import '../../../system.css'

const router = useRouter()
const ranges = [{ value: '1h', label: '1 小时' }, { value: '6h', label: '6 小时' }, { value: '24h', label: '24 小时' }]
const window = ref('1h')
const data = ref(null)
const collectedAt = ref('')
const loading = ref(false)
const error = ref('')
const disk = ref('')
const network = ref('eth0')
const metrics = computed(() => data.value?.metrics || {})
const disks = computed(() => deviceChoices(metrics.value.disk))
const networks = computed(() => deviceChoices(metrics.value.networkIn))
const sourceInfo = computed(() => data.value ? `${data.value.region} · ECS · ${data.value.period / 60} 分钟采样` : '读取现有 Agent 的历史记录')
const chartProps = computed(() => ({ loading: loading.value, period: data.value?.period || 60, start: data.value?.startTime, end: data.value?.endTime }))
let timer, controller

async function refresh () {
  controller?.abort()
  const current = new AbortController()
  controller = current
  loading.value = true
  error.value = ''
  try {
    const response = await fetch(`/service-monitor/system?range=${window.value}`, {
      credentials: 'same-origin', cache: 'no-store', signal: current.signal
    })
    if (response.status === 403) {
      await router.push('/login')
      return
    }
    if (!response.ok) throw new Error('CloudMonitor unavailable')
    const result = await response.json()
    if (current !== controller) return
    data.value = result.data
    collectedAt.value = result.collectedAt
    if (result.error) error.value = '云监控暂时查询失败，当前显示上次成功记录。'
    if (!disks.value.some(item => item.value === disk.value)) disk.value = metrics.value.disk?.series.find(item => item.name === '/')?.device || disks.value[0]?.value || ''
    if (!networks.value.some(item => item.value === network.value)) network.value = networks.value.find(item => item.value === 'eth0')?.value || networks.value[0]?.value || ''
  } catch (failure) {
    if (failure.name !== 'AbortError' && current === controller) error.value = '暂时无法读取阿里云监控，请稍后刷新。已有曲线保留，更新时间不变。'
  } finally {
    if (current === controller) loading.value = false
  }
}

function changeRange (value) {
  if (value === window.value) return
  window.value = value
  data.value = null
  collectedAt.value = ''
  refresh()
}

onMounted(() => {
  refresh()
  timer = setInterval(() => { if (!document.hidden && !loading.value) refresh() }, 60000)
})
onBeforeUnmount(() => {
  clearInterval(timer)
  controller?.abort()
})
</script>
