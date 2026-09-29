<template>
  <section class="page" data-module="noise">
    <header class="page-head">
      <div>
        <h2>噪声投诉管理</h2>
        <p class="page-desc">登记投诉受理信息（投诉人、联系电话、投诉时段、涉及区域），按投诉时段与涉及区域筛选，并按区域投诉频次排序；处置完成后补录回访与降噪措施。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记噪声投诉</button>
        <button class="btn" type="button" @click="exportRows">导出噪声投诉清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card" :class="{ alert: item.alert }">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>投诉时段（日期）</span>
        <input v-model="filters.period" type="date" />
      </label>
      <label class="filter-item">
        <span>涉及区域</span>
        <input v-model="filters.area" placeholder="按涉及区域检索" />
      </label>
      <label class="filter-item">
        <span>处置进度</span>
        <select v-model="filters.status">
          <option value="">全部进度</option>
          <option v-for="s in statuses" :key="s" :value="s">{{ s }}</option>
        </select>
      </label>
      <label class="filter-check">
        <input v-model="filters.overdue" type="checkbox" />
        <span>仅看超期未回访</span>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
      <span class="filter-tip">列表按涉及区域投诉频次由高到低排序，筛选条件再次进入页面时保留</span>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>处置进度</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)" :class="{ 'row-overdue': row['超期未回访'] }">
          <td v-for="column in columns" :key="column">
            <template v-if="column === '涉及区域'">
              {{ row[column] }}
              <span class="freq-tag">{{ row['投诉频次'] }} 次</span>
            </template>
            <template v-else-if="column === '投诉状态'">
              <span :class="['status-tag', statusClass(row)]">{{ row[column] }}</span>
              <span v-if="row['超期未回访']" class="overdue-tag">超期未回访</span>
            </template>
            <template v-else>{{ row[column] || '—' }}</template>
          </td>
          <td>
            <ol class="progress-line">
              <li v-for="(step, index) in progressSteps" :key="step.key" :class="{ done: progressIndex(row) >= index }">
                {{ step.label }}
              </li>
            </ol>
          </td>
          <td class="row-actions">
            <button class="link" type="button" @click="openDetail(row)">查看详情</button>
            <button v-if="row.status === '待受理'" class="link" type="button" @click="quickAccept(row)">受理</button>
            <button v-if="row.status === '处置中'" class="link" type="button" @click="quickFinish(row)">完成处置</button>
            <button v-if="row.status === '待回访'" class="link danger" type="button" @click="openDetail(row, true)">补录回访</button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 2" class="empty-state">暂无符合条件的噪声投诉，可先登记一条投诉</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条噪声投诉记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <!-- 登记投诉 -->
    <div v-if="createVisible" class="modal-mask" @click.self="createVisible = false">
      <div class="modal">
        <header class="modal-head">
          <h3>登记噪声投诉</h3>
          <button class="link" type="button" @click="createVisible = false">关闭</button>
        </header>
        <div class="modal-body">
          <label class="form-item">
            <span>投诉人 *</span>
            <input v-model="createForm.complainant" placeholder="投诉人姓名" />
          </label>
          <label class="form-item">
            <span>联系电话 *</span>
            <input v-model="createForm.phone" placeholder="7~15 位数字，如 13800001234 或 01088886666" />
          </label>
          <label class="form-item">
            <span>投诉开始 *</span>
            <input v-model="createForm.periodStart" type="datetime-local" />
          </label>
          <label class="form-item">
            <span>投诉结束 *</span>
            <input v-model="createForm.periodEnd" type="datetime-local" />
          </label>
          <p class="form-hint">投诉时段须为同一天内结束晚于开始的完整时段，提交后按「YYYY-MM-DD HH:MM~HH:MM」保存。</p>
          <label class="form-item">
            <span>涉及区域 *</span>
            <input v-model="createForm.area" placeholder="如 东跑道北侧 / 西滑行道 / 货运区" />
          </label>
          <label class="form-item">
            <span>投诉内容</span>
            <textarea v-model="createForm.content" rows="3" placeholder="噪声现象、影响等"></textarea>
          </label>
          <p v-if="createError" class="error-text">{{ createError }}</p>
        </div>
        <footer class="modal-foot">
          <button class="btn" type="button" @click="createVisible = false">取消</button>
          <button class="btn primary" type="button" :disabled="creating" @click="submitCreate">
            {{ creating ? '提交中…' : '保存投诉' }}
          </button>
        </footer>
      </div>
    </div>

    <!-- 单条详情：与列表共用同一份处置进度 -->
    <div v-if="detailVisible" class="modal-mask" @click.self="closeDetail">
      <div class="modal modal-wide">
        <header class="modal-head">
          <h3>投诉详情 {{ detail['投诉编号'] }}</h3>
          <button class="link" type="button" @click="closeDetail">关闭</button>
        </header>
        <div class="modal-body">
          <p v-if="detail['超期未回访']" class="error-text overdue-banner">
            该投诉处置已于 {{ detail['处置完成时间'] }} 完成，回访期限 {{ detail['回访期限'] }} 已过，请尽快补录回访。
          </p>
          <ol class="progress-line progress-large">
            <li v-for="(step, index) in progressSteps" :key="step.key" :class="{ done: detailProgressIndex >= index }">
              {{ step.label }}
              <small>{{ stepTime(step.key) }}</small>
            </li>
          </ol>
          <dl class="detail-grid">
            <template v-for="field in detailFields" :key="field">
              <dt>{{ field }}</dt>
              <dd>{{ detail[field] || '—' }}</dd>
            </template>
            <dt>处置进度</dt>
            <dd>{{ detail.status }}<span v-if="detail['超期未回访']" class="overdue-tag">超期未回访</span></dd>
          </dl>

          <div v-if="detail.status === '处置中'" class="detail-action">
            <button class="btn primary" type="button" @click="finishFromDetail">完成处置，转待回访</button>
          </div>

          <div v-if="detail.status === '待受理'" class="detail-action">
            <label class="inline-item">
              <span>处置人员</span>
              <input v-model="handlerInput" placeholder="指定处置人员后受理" />
            </label>
            <button class="btn primary" type="button" @click="acceptFromDetail">受理投诉</button>
          </div>

          <div v-if="detail.status === '待回访'" class="revisit-box">
            <h4>补录回访（回访时间、回访结论、降噪措施均必填）</h4>
            <label class="form-item">
              <span>回访时间 *</span>
              <input v-model="revisitForm.revisitAt" type="datetime-local" />
            </label>
            <label class="form-item">
              <span>回访结论 *</span>
              <textarea v-model="revisitForm.conclusion" rows="2" placeholder="如 投诉人认可整改，噪声明显减弱"></textarea>
            </label>
            <label class="form-item">
              <span>降噪措施 *</span>
              <textarea v-model="revisitForm.measure" rows="2" placeholder="如 夜间优化跑道方向、限制 APU 怠速"></textarea>
            </label>
            <p v-if="revisitError" class="error-text">{{ revisitError }}</p>
            <button class="btn primary" type="button" :disabled="revisiting" @click="submitRevisit">
              {{ revisiting ? '提交中…' : '提交回访' }}
            </button>
          </div>

          <p v-if="detailError" class="error-text">{{ detailError }}</p>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | boolean | null>

const ENDPOINT = '/api/noise'
const FILTER_STORAGE_KEY = 'noise-filters'
const columns = [
  '投诉编号', '投诉人', '联系电话', '投诉时段', '涉及区域',
  '处置人员', '受理时间', '处置完成时间', '回访期限', '投诉状态',
]
const detailFields = [
  '投诉编号', '投诉人', '联系电话', '投诉时段', '涉及区域', '投诉内容',
  '受理时间', '处置人员', '处置完成时间', '回访期限',
  '回访时间', '回访结论', '降噪措施',
]
const statuses = ['待受理', '处置中', '待回访', '已回访']
const progressSteps = [
  { key: '受理时间', label: '已受理' },
  { key: '处置完成时间', label: '处置中' },
  { key: '回访期限', label: '待回访' },
  { key: '回访时间', label: '已回访' },
] as const

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')

interface Filters {
  period: string
  area: string
  status: string
  overdue: boolean
}

function loadFilters(): Filters {
  // 仅噪声投诉模块记忆筛选条件；其它模块的列表行为保持原样。
  const fallback: Filters = { period: '', area: '', status: '', overdue: false }
  try {
    const raw = window.localStorage.getItem(FILTER_STORAGE_KEY)
    if (!raw) return fallback
    return { ...fallback, ...(JSON.parse(raw) as Partial<Filters>) }
  } catch {
    return fallback
  }
}

// 再次进入页面时，上次选中的筛选条件仍在输入框与查询请求里。
const filters = ref<Filters>(loadFilters())

function persistFilters() {
  try {
    window.localStorage.setItem(FILTER_STORAGE_KEY, JSON.stringify(filters.value))
  } catch {
    // 本地存储不可用时只影响条件记忆，不阻断查询。
  }
}

const stats = ref([
  { label: '投诉总数', value: 0, alert: false },
  { label: '处置中/待受理', value: 0, alert: false },
  { label: '待回访', value: 0, alert: false },
  { label: '超期未回访', value: 0, alert: true },
  { label: '已回访', value: 0, alert: false },
])

function buildQuery() {
  const params = new URLSearchParams()
  if (filters.value.period) params.set('period', filters.value.period)
  if (filters.value.area.trim()) params.set('area', filters.value.area.trim())
  if (filters.value.status) params.set('status', filters.value.status)
  if (filters.value.overdue) params.set('overdue', 'true')
  return params.toString()
}

async function reload() {
  errorMessage.value = ''
  persistFilters()
  try {
    const response = await request(`${ENDPOINT}?${buildQuery()}`)
    if (!response.ok) throw new Error('噪声投诉列表读取失败')
    const payload = await response.json()
    rows.value = (payload.items ?? []) as Row[]
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '噪声投诉列表读取失败'
  }
}

async function reloadStats() {
  try {
    const response = await request(`${ENDPOINT}/stats`)
    if (!response.ok) return
    const data = (await response.json()) as Record<string, number>
    stats.value[0].value = data.total ?? 0
    stats.value[1].value = (data.pendingAccept ?? 0) + (data.handling ?? 0)
    stats.value[2].value = data.awaitingRevisit ?? 0
    stats.value[3].value = data.overdue ?? 0
    stats.value[4].value = data.revisited ?? 0
  } catch {
    // 指标卡读取失败不阻塞列表。
  }
}

function resetFilters() {
  filters.value = { period: '', area: '', status: '', overdue: false }
  persistFilters()
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export?${buildQuery()}`, '_blank')
}

function progressIndex(row: Row): number {
  const status = String(row.status ?? '')
  if (status === '已回访') return 3
  if (status === '待回访') return 2
  if (status === '处置中') return 1
  return 0
}

function statusClass(row: Row): string {
  if (row['超期未回访']) return 'status-overdue'
  const map: Record<string, string> = {
    待受理: 'status-created',
    处置中: 'status-doing',
    待回访: 'status-wait',
    已回访: 'status-done',
  }
  return map[String(row.status ?? '')] ?? ''
}

function stepTime(key: string): string {
  const value = detail.value[key]
  return value ? String(value) : ''
}

// ---------- 登记投诉 ----------
const createVisible = ref(false)
const creating = ref(false)
const createError = ref('')
const createForm = reactive({
  complainant: '',
  phone: '',
  periodStart: '',
  periodEnd: '',
  area: '',
  content: '',
})

function openCreate() {
  createError.value = ''
  createVisible.value = true
}

function toPeriodText(value: string): string {
  // datetime-local: "2026-09-29T22:00" -> "2026-09-29 22:00"
  return value.replace('T', ' ')
}

async function submitCreate() {
  createError.value = ''
  if (!createForm.complainant.trim() || !createForm.phone.trim()
      || !createForm.periodStart || !createForm.periodEnd || !createForm.area.trim()) {
    createError.value = '请填齐投诉人、联系电话、投诉起止时段与涉及区域'
    return
  }
  if (!/^\d{7,15}$/.test(createForm.phone.trim())) {
    createError.value = '联系电话应为 7~15 位数字'
    return
  }
  const start = toPeriodText(createForm.periodStart)
  const end = toPeriodText(createForm.periodEnd)
  if (start.slice(0, 10) !== end.slice(0, 10)) {
    createError.value = '投诉时段须在同一天内，请重新选择起止时间'
    return
  }
  if (end <= start) {
    createError.value = '投诉结束时刻须晚于开始时刻'
    return
  }
  creating.value = true
  try {
    const response = await request(ENDPOINT, {
      method: 'POST',
      body: JSON.stringify({
        values: {
          投诉人: createForm.complainant.trim(),
          联系电话: createForm.phone.trim(),
          投诉时段: `${start}~${end.slice(11)}`,
          涉及区域: createForm.area.trim(),
          投诉内容: createForm.content.trim(),
        },
      }),
    })
    const payload = await response.json().catch(() => null) as { ok?: boolean; message?: string } | null
    if (!response.ok || !payload?.ok) {
      // 重复提交、时段不规范等拒绝原因由后端给出，原样展示。
      throw new Error(payload?.message || '投诉未保存，请稍后重试')
    }
    createVisible.value = false
    Object.assign(createForm, {
      complainant: '', phone: '', periodStart: '', periodEnd: '', area: '', content: '',
    })
    await reload()
    await reloadStats()
  } catch (error) {
    createError.value = error instanceof Error ? error.message : '投诉保存失败'
  } finally {
    creating.value = false
  }
}

// ---------- 单条详情与处置/回访 ----------
const detailVisible = ref(false)
const detail = ref<Row>({})
const detailError = ref('')
const handlerInput = ref('')
const revisiting = ref(false)
const revisitError = ref('')
const revisitForm = reactive({ revisitAt: '', conclusion: '', measure: '' })

const detailProgressIndex = computed(() => progressIndex(detail.value))

function nowLocalInput(): string {
  const now = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}T${pad(now.getHours())}:${pad(now.getMinutes())}`
}

async function openDetail(row: Row, focusRevisit = false) {
  detailError.value = ''
  revisitError.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}`)
    if (!response.ok) throw new Error('投诉详情读取失败')
    detail.value = (await response.json()) as Row
    handlerInput.value = String(detail.value['处置人员'] ?? '')
    Object.assign(revisitForm, { revisitAt: nowLocalInput(), conclusion: '', measure: '' })
    detailVisible.value = true
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '投诉详情读取失败'
  }
}

function closeDetail() {
  detailVisible.value = false
}

async function runEntryAction(id: Row['id'], values: Record<string, string>): Promise<Row | null> {
  const response = await request(`${ENDPOINT}/${id}/actions`, {
    method: 'POST',
    body: JSON.stringify({ values }),
  })
  const payload = await response.json().catch(() => null) as
    | { ok?: boolean; message?: string; entry?: Row }
    | null
  if (!response.ok || !payload?.ok || !payload.entry) {
    throw new Error(payload?.message || '操作未生效，请稍后重试')
  }
  return payload.entry
}

async function afterAction(entry: Row | null) {
  await reload()
  await reloadStats()
  if (entry && detailVisible.value) {
    // 详情与列表始终指向同一条记录的最新处置进度。
    const fresh = await request(`${ENDPOINT}/${entry.id}`)
    if (fresh.ok) detail.value = (await fresh.json()) as Row
  }
}

async function quickAccept(row: Row) {
  errorMessage.value = ''
  const handler = window.prompt('请输入处置人员姓名')?.trim()
  if (!handler) return
  try {
    const entry = await runEntryAction(row.id, { action: '受理投诉', 处置人员: handler })
    await afterAction(entry)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '受理失败'
  }
}

async function quickFinish(row: Row) {
  errorMessage.value = ''
  try {
    const entry = await runEntryAction(row.id, { action: '完成处置' })
    await afterAction(entry)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '完成处置失败'
  }
}

async function acceptFromDetail() {
  detailError.value = ''
  if (!handlerInput.value.trim()) {
    detailError.value = '请先指定处置人员'
    return
  }
  try {
    const entry = await runEntryAction(detail.value.id as number, {
      action: '受理投诉', 处置人员: handlerInput.value.trim(),
    })
    await afterAction(entry)
  } catch (error) {
    detailError.value = error instanceof Error ? error.message : '受理失败'
  }
}

async function finishFromDetail() {
  detailError.value = ''
  try {
    const entry = await runEntryAction(detail.value.id as number, { action: '完成处置' })
    await afterAction(entry)
  } catch (error) {
    detailError.value = error instanceof Error ? error.message : '完成处置失败'
  }
}

async function submitRevisit() {
  revisitError.value = ''
  if (!revisitForm.revisitAt || !revisitForm.conclusion.trim() || !revisitForm.measure.trim()) {
    revisitError.value = '回访时间、回访结论与降噪措施均为必填'
    return
  }
  revisiting.value = true
  try {
    const entry = await runEntryAction(detail.value.id as number, {
      action: '补录回访',
      回访时间: toPeriodText(revisitForm.revisitAt),
      回访结论: revisitForm.conclusion.trim(),
      降噪措施: revisitForm.measure.trim(),
    })
    // 回访办结后详情仍停留在当前记录，展示最新进度（已回访）与回访内容。
    await afterAction(entry)
  } catch (error) {
    revisitError.value = error instanceof Error ? error.message : '回访提交失败'
  } finally {
    revisiting.value = false
  }
}

onMounted(() => {
  void reload()
  void reloadStats()
})
</script>

<style scoped>
.page-actions { display: flex; gap: 8px; }
.stat-card.alert .stat-value { color: #b42318; }
.filter-check { display: flex; align-items: center; gap: 4px; font-size: 13px; }
.filter-check input { margin: 0; }
.filter-tip { color: var(--muted); font-size: 12px; }
.filter-item select { padding: 4px 6px; }
.freq-tag { display: inline-block; margin-left: 6px; font-size: 12px; color: var(--brand); background: #eef4ff; border-radius: 4px; padding: 0 6px; }
.status-tag { border-radius: 4px; padding: 1px 8px; font-size: 12px; }
.status-created { background: #f2f4f7; color: #475467; }
.status-doing { background: #eef4ff; color: #1d4ed8; }
.status-wait { background: #fffaeb; color: #b54708; }
.status-done { background: #ecfdf3; color: #027a48; }
.status-overdue { background: #fef3f2; color: #b42318; }
.overdue-tag { display: inline-block; margin-left: 6px; background: #fef3f2; color: #b42318; border-radius: 4px; padding: 1px 6px; font-size: 12px; }
.row-overdue { background: #fff8f7; }
.link.danger { color: #b42318; }
.progress-line { list-style: none; display: flex; gap: 6px; margin: 0; padding: 0; }
.progress-line li { font-size: 12px; color: #98a2b3; border-bottom: 2px solid #e4e7ec; padding: 0 6px 2px; }
.progress-line li.done { color: #027a48; border-bottom-color: #12b76a; }
.progress-large { margin-bottom: 12px; }
.progress-large li { display: flex; flex-direction: column; font-size: 13px; min-width: 90px; }
.progress-large small { color: var(--muted); font-size: 11px; }
.modal-mask { position: fixed; inset: 0; background: rgba(16, 24, 40, 0.45); display: flex; align-items: center; justify-content: center; z-index: 20; }
.modal { background: #fff; border-radius: 10px; width: 480px; max-height: 88vh; overflow: auto; }
.modal-wide { width: 720px; }
.modal-head { display: flex; justify-content: space-between; align-items: center; padding: 12px 16px; border-bottom: 1px solid var(--border); }
.modal-head h3 { margin: 0; font-size: 15px; }
.modal-body { padding: 14px 16px; }
.modal-foot { display: flex; justify-content: flex-end; gap: 8px; padding: 12px 16px; border-top: 1px solid var(--border); }
.form-item { display: block; margin-bottom: 10px; }
.form-item span { display: block; font-size: 12px; color: var(--muted); margin-bottom: 4px; }
.form-item input, .form-item textarea { width: 100%; padding: 6px 8px; border: 1px solid var(--border); border-radius: 6px; font: inherit; }
.form-hint { color: var(--muted); font-size: 12px; margin: 0 0 10px; }
.inline-item { display: inline-flex; align-items: center; gap: 6px; margin-right: 8px; }
.inline-item input { padding: 6px 8px; border: 1px solid var(--border); border-radius: 6px; }
.detail-grid { display: grid; grid-template-columns: 110px 1fr 110px 1fr; gap: 6px 10px; font-size: 13px; }
.detail-grid dt { color: var(--muted); }
.detail-grid dd { margin: 0; }
.detail-action { margin-top: 14px; display: flex; align-items: center; gap: 8px; }
.revisit-box { margin-top: 14px; border: 1px dashed var(--border); border-radius: 8px; padding: 12px; background: #fcfcfd; }
.revisit-box h4 { margin: 0 0 10px; font-size: 13px; }
.overdue-banner { border: 1px solid #fecdca; background: #fef3f2; border-radius: 6px; padding: 8px 10px; margin-top: 0; }
</style>
