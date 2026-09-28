<template>
  <section class="page" data-module="noise">
    <header class="page-head">
      <div>
        <h2>噪声投诉管理</h2>
        <p class="page-desc">登记噪声投诉受理信息，按投诉时段、涉及区域筛选并按投诉频次排序，处置完成后补录回访，超期未回访可单独定位。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记噪声投诉</button>
        <button class="btn" type="button" @click="exportRows">导出投诉清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card" :class="{ alarm: item.alarm }">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload(true)">
      <label class="filter-item">
        <span>投诉时段</span>
        <input v-model="filters.period" placeholder="如 2026-09-27 或 22:00-23:30" />
      </label>
      <label class="filter-item">
        <span>涉及区域</span>
        <select v-model="filters.area">
          <option value="">全部区域</option>
          <option v-for="area in areaOptions" :key="area" :value="area">{{ area }}</option>
        </select>
      </label>
      <label class="filter-item">
        <span>处置进度</span>
        <select v-model="filters.status">
          <option value="">全部进度</option>
          <option v-for="status in statusOptions" :key="status" :value="status">{{ status }}</option>
        </select>
      </label>
      <label class="filter-check">
        <input v-model="filters.overdue" type="checkbox" />
        <span>仅看超期未回访</span>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)" :class="{ 'row-overdue': row.超期未回访 }">
          <td v-for="column in columns" :key="column">
            <template v-if="column === '投诉频次'">
              <span class="freq-badge" :class="{ hot: Number(row[column]) >= 3 }">{{ row[column] }}</span>
            </template>
            <template v-else-if="column === '处置状态/进度'">
              <span class="status-tag" :class="statusClass(row.status)">{{ row.status }}</span>
              <span v-if="row.超期未回访" class="overdue-tag">超期未回访</span>
            </template>
            <template v-else>{{ row[column] ?? '—' }}</template>
          </td>
          <td class="row-actions">
            <button class="link" type="button" @click="openDetail(row)">查看处置进度</button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">没有符合筛选条件的噪声投诉</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条噪声投诉（按同区域、同日内时段的投诉频次降序排列）</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <!-- 登记噪声投诉 -->
    <div v-if="creating" class="modal-mask" @click.self="closeCreate">
      <div class="modal">
        <h3>登记噪声投诉</h3>
        <div class="form-grid">
          <label class="form-item">
            <span>投诉人 *</span>
            <input v-model="createForm.投诉人" placeholder="投诉人姓名" />
          </label>
          <label class="form-item">
            <span>联系电话 *</span>
            <input v-model="createForm.联系电话" placeholder="手机号或带区号座机" />
          </label>
          <label class="form-item">
            <span>投诉日期 *</span>
            <input v-model="createForm._date" type="date" />
          </label>
          <label class="form-item">
            <span>投诉时段 *</span>
            <div class="period-range">
              <input v-model="createForm._start" type="time" aria-label="开始时间" />
              <em>至</em>
              <input v-model="createForm._end" type="time" aria-label="结束时间" />
            </div>
          </label>
          <label class="form-item wide">
            <span>涉及区域 *</span>
            <input v-model="createForm.涉及区域" list="noise-area-list" placeholder="如 东跑道北侧居民区" />
            <datalist id="noise-area-list">
              <option v-for="area in areaOptions" :key="area" :value="area" />
            </datalist>
          </label>
        </div>
        <p class="form-hint">投诉时段规范：同一自然日内「开始时间-结束时间」，且开始须早于结束；重复提交将被拒绝。</p>
        <p v-if="createError" class="error-text form-error">{{ createError }}</p>
        <div class="modal-actions">
          <button class="btn" type="button" @click="closeCreate">取消</button>
          <button class="btn primary" type="button" :disabled="submitting" @click="submitCreate">
            {{ submitting ? '保存中…' : '保存受理信息' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 处置进度 / 回访补录 -->
    <div v-if="detail" class="modal-mask" @click.self="closeDetail">
      <div class="modal modal-wide">
        <h3>投诉 {{ detail.投诉编号 }} · 处置进度</h3>

        <div class="detail-section">
          <h4>受理信息</h4>
          <dl class="detail-grid">
            <div><dt>投诉人</dt><dd>{{ detail.投诉人 }}</dd></div>
            <div><dt>联系电话</dt><dd>{{ detail.联系电话 }}</dd></div>
            <div><dt>投诉时段</dt><dd>{{ detail.投诉时段 }}</dd></div>
            <div><dt>涉及区域</dt><dd>{{ detail.涉及区域 }}</dd></div>
            <div><dt>受理时间</dt><dd>{{ detail.受理时间 || '—' }}</dd></div>
            <div>
              <dt>同区域同时段投诉频次</dt>
              <dd><span class="freq-badge" :class="{ hot: Number(detail.投诉频次) >= 3 }">{{ detail.投诉频次 }}</span> 次</dd>
            </div>
          </dl>
        </div>

        <div class="detail-section">
          <h4>处置进度</h4>
          <ol class="progress-track">
            <li v-for="step in progressSteps" :key="step.name" :class="step.state">
              <span class="dot"></span>
              <span class="step-name">{{ step.name }}</span>
              <span class="step-time">{{ step.time }}</span>
            </li>
          </ol>
          <p v-if="detail.超期未回访" class="error-text form-error">
            该投诉处置完成已超过 {{ visitDeadlineDays }} 天仍未回访，请尽快补录回访信息。
          </p>
        </div>

        <div v-if="detail.status === '待回访'" class="detail-section">
          <h4>补录回访信息</h4>
          <div class="form-grid">
            <label class="form-item">
              <span>回访时间 *</span>
              <input v-model="visitForm._time" type="datetime-local" />
            </label>
            <label class="form-item wide">
              <span>回访结论 *</span>
              <textarea v-model="visitForm.回访结论" rows="2" placeholder="如：投诉人对降噪效果表示认可"></textarea>
            </label>
            <label class="form-item wide">
              <span>降噪措施 *</span>
              <textarea v-model="visitForm.降噪措施" rows="2" placeholder="如：调整夜间作业路线、加装隔音屏障"></textarea>
            </label>
          </div>
        </div>

        <div v-else-if="detail.status === '已回访'" class="detail-section">
          <h4>回访记录</h4>
          <dl class="detail-grid">
            <div><dt>回访时间</dt><dd>{{ detail.回访时间 }}</dd></div>
            <div class="wide-col"><dt>回访结论</dt><dd>{{ detail.回访结论 }}</dd></div>
            <div class="wide-col"><dt>降噪措施</dt><dd>{{ detail.降噪措施 }}</dd></div>
          </dl>
        </div>

        <p v-if="detailError" class="error-text form-error">{{ detailError }}</p>
        <div class="modal-actions">
          <button class="btn" type="button" @click="closeDetail">关闭</button>
          <template v-if="detail.status === '待受理'">
            <button class="btn primary" type="button" :disabled="submitting" @click="runAction('受理投诉')">受理投诉</button>
          </template>
          <template v-else-if="detail.status === '处置中'">
            <button class="btn primary" type="button" :disabled="submitting" @click="runAction('完成处置')">完成处置（转待回访）</button>
          </template>
          <template v-else-if="detail.status === '待回访'">
            <button class="btn primary" type="button" :disabled="submitting" @click="submitVisit">
              {{ submitting ? '提交中…' : '提交回访并闭环' }}
            </button>
          </template>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | boolean | null>
type NoiseStatus = '待受理' | '处置中' | '待回访' | '已回访'

const ENDPOINT = '/api/noise'
const FILTER_STORAGE_KEY = 'noise-filters'
const visitDeadlineDays = 3

const columns = ['投诉编号', '投诉人', '联系电话', '投诉时段', '涉及区域', '受理时间', '投诉频次', '处置状态/进度']

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const areaOptions = ref<string[]>([])
const statusOptions: NoiseStatus[] = ['待受理', '处置中', '待回访', '已回访']

interface Filters {
  period: string
  area: string
  status: string
  overdue: boolean
}

function readStoredFilters(): Filters {
  const fallback: Filters = { period: '', area: '', status: '', overdue: false }
  try {
    const raw = window.localStorage.getItem(FILTER_STORAGE_KEY)
    if (!raw) return fallback
    return { ...fallback, ...(JSON.parse(raw) as Partial<Filters>) }
  } catch {
    return fallback
  }
}

// 再次进入页面时，上次选中的筛选条件仍然保留。
const filters = ref<Filters>(readStoredFilters())

function persistFilters() {
  window.localStorage.setItem(FILTER_STORAGE_KEY, JSON.stringify(filters.value))
}

const stats = computed(() => {
  const all = rows.value
  return [
    { label: '当前筛选投诉数', value: total.value, alarm: false },
    { label: '待受理', value: all.filter((r) => r.status === '待受理').length, alarm: false },
    { label: '处置中', value: all.filter((r) => r.status === '处置中').length, alarm: false },
    { label: '待回访', value: all.filter((r) => r.status === '待回访').length, alarm: false },
    { label: '超期未回访', value: all.filter((r) => r.超期未回访).length, alarm: true },
  ]
})

const creating = ref(false)
const submitting = ref(false)
const createError = ref('')
const emptyCreateForm = () => ({
  投诉人: '',
  联系电话: '',
  _date: '',
  _start: '',
  _end: '',
  涉及区域: '',
})
const createForm = ref(emptyCreateForm())

const detail = ref<Row | null>(null)
const detailError = ref('')
const visitForm = ref({ _time: '', 回访结论: '', 降噪措施: '' })

function statusClass(status: unknown) {
  return {
    待受理: 'st-created',
    处置中: 'st-doing',
    待回访: 'st-wait',
    已回访: 'st-done',
  }[String(status)] ?? ''
}

const progressSteps = computed(() => {
  const entry = detail.value
  if (!entry) return []
  const order: NoiseStatus[] = ['待受理', '处置中', '待回访', '已回访']
  const current = order.indexOf(String(entry.status) as NoiseStatus)
  const meta: { name: string; time: string }[] = [
    { name: '投诉受理', time: String(entry.受理时间 || '') },
    { name: '处置中', time: String(entry.处置人员 || '') ? `受理人：${String(entry.处置人员)}` : '' },
    { name: '待回访', time: String(entry.处置完成时间 || '') },
    { name: '已回访闭环', time: String(entry.回访时间 || '') },
  ]
  return meta.map((step, index) => ({
    ...step,
    state: index < current ? 'done' : index === current ? 'current' : 'pending',
  }))
})

function buildQuery() {
  const params = new URLSearchParams()
  if (filters.value.period.trim()) params.set('period', filters.value.period.trim())
  if (filters.value.area) params.set('area', filters.value.area)
  if (filters.value.status) params.set('status', filters.value.status)
  if (filters.value.overdue) params.set('overdue', 'true')
  const query = params.toString()
  return query ? `?${query}` : ''
}

async function loadOptions() {
  try {
    const response = await request(`${ENDPOINT}/options`)
    if (response.ok) {
      const payload = (await response.json()) as { areas: string[] }
      areaOptions.value = payload.areas ?? []
    }
  } catch {
    // 选项加载失败不阻塞列表，区域仍可手输
  }
}

async function reload(persist = false) {
  errorMessage.value = ''
  if (persist) persistFilters()
  try {
    const response = await request(`${ENDPOINT}${buildQuery()}`)
    if (!response.ok) throw new Error('噪声投诉列表读取失败')
    const payload = (await response.json()) as { items: Row[]; total: number }
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '噪声投诉列表读取失败'
  }
}

function resetFilters() {
  filters.value = { period: '', area: '', status: '', overdue: false }
  persistFilters()
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export${buildQuery()}`, '_blank')
}

function openCreate() {
  createForm.value = emptyCreateForm()
  createError.value = ''
  creating.value = true
}

function closeCreate() {
  creating.value = false
  createError.value = ''
}

async function submitCreate() {
  createError.value = ''
  const form = createForm.value
  if (!form._date || !form._start || !form._end) {
    createError.value = '请补全投诉日期与起止时段'
    return
  }
  if (!form.投诉人.trim() || !form.联系电话.trim() || !form.涉及区域.trim()) {
    createError.value = '请补全投诉人、联系电话与涉及区域'
    return
  }
  const payload = {
    values: {
      投诉人: form.投诉人.trim(),
      联系电话: form.联系电话.trim(),
      投诉时段: `${form._date} ${form._start}-${form._end}`,
      涉及区域: form.涉及区域.trim(),
    },
  }
  submitting.value = true
  try {
    const response = await request(ENDPOINT, { method: 'POST', body: JSON.stringify(payload) })
    const result = (await response.json()) as { ok: boolean; message: string }
    if (!response.ok || !result.ok) {
      // 重复提交、投诉时段不规范等：拒绝保存并把原因原样说明。
      createError.value = result.message || '投诉未保存，请检查填写内容'
      return
    }
    creating.value = false
    await Promise.all([reload(), loadOptions()])
  } catch (error) {
    createError.value = error instanceof Error ? error.message : '投诉登记失败'
  } finally {
    submitting.value = false
  }
}

async function openDetail(row: Row) {
  detailError.value = ''
  detail.value = row
  visitForm.value = { _time: '', 回访结论: '', 降噪措施: '' }
  try {
    const response = await request(`${ENDPOINT}/${row.id}`)
    if (!response.ok) {
      const failed = (await response.json().catch(() => null)) as { detail?: string } | null
      detailError.value = failed?.detail ?? '投诉记录不存在或已归档'
      return
    }
    // 单条记录始终以后端最新数据为准，与列表保持同一份处置进度。
    detail.value = (await response.json()) as Row
  } catch (error) {
    detailError.value = error instanceof Error ? error.message : '投诉明细读取失败'
  }
}

function closeDetail() {
  detail.value = null
  detailError.value = ''
}

async function runAction(action: string) {
  if (!detail.value) return
  detailError.value = ''
  submitting.value = true
  try {
    const response = await request(`${ENDPOINT}/${detail.value.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    const result = (await response.json()) as { ok: boolean; message: string; entry?: Row }
    if (!response.ok || !result.ok || !result.entry) {
      detailError.value = result.message || '操作未生效'
      return
    }
    detail.value = result.entry
    await reload()
  } catch (error) {
    detailError.value = error instanceof Error ? error.message : '处置操作失败'
  } finally {
    submitting.value = false
  }
}

async function submitVisit() {
  if (!detail.value) return
  detailError.value = ''
  const form = visitForm.value
  if (!form._time) {
    detailError.value = '请选择回访时间'
    return
  }
  if (!form.回访结论.trim() || !form.降噪措施.trim()) {
    detailError.value = '请补全回访结论与降噪措施'
    return
  }
  submitting.value = true
  try {
    const response = await request(`${ENDPOINT}/${detail.value.id}/visit`, {
      method: 'POST',
      body: JSON.stringify({
        values: {
          回访时间: form._time.replace('T', ' '),
          回访结论: form.回访结论.trim(),
          降噪措施: form.降噪措施.trim(),
        },
      }),
    })
    const result = (await response.json()) as { ok: boolean; message: string; entry?: Row }
    if (!response.ok || !result.ok || !result.entry) {
      detailError.value = result.message || '回访信息未保存'
      return
    }
    detail.value = result.entry
    await reload()
  } catch (error) {
    detailError.value = error instanceof Error ? error.message : '回访提交失败'
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  await Promise.all([reload(), loadOptions()])
})
</script>

<style scoped>
.page-actions {
  display: flex;
  gap: 8px;
}
.stat-card.alarm {
  border-color: #f04438;
  background: #fff5f4;
}
.stat-card.alarm .stat-value {
  color: #b42318;
}
.filter-item select {
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 6px 8px;
  font-size: 13px;
  min-width: 150px;
}
.filter-check {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  padding-bottom: 7px;
  white-space: nowrap;
}
.freq-badge {
  display: inline-block;
  min-width: 24px;
  text-align: center;
  padding: 1px 8px;
  border-radius: 999px;
  background: #eef2f7;
  color: #475569;
  font-weight: 600;
}
.freq-badge.hot {
  background: #fff1e8;
  color: #c2410c;
}
.status-tag {
  display: inline-block;
  padding: 1px 8px;
  border-radius: 4px;
  font-size: 12px;
}
.st-created { background: #eef2ff; color: #3730a3; }
.st-doing { background: #e0f2fe; color: #075985; }
.st-wait { background: #fef9c3; color: #854d0e; }
.st-done { background: #dcfce7; color: #166534; }
.overdue-tag {
  display: inline-block;
  margin-left: 6px;
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 12px;
  background: #fee4e2;
  color: #b42318;
}
tr.row-overdue {
  background: #fff7f6;
}

.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 50;
}
.modal {
  width: 520px;
  max-height: 88vh;
  overflow-y: auto;
  background: #fff;
  border-radius: 10px;
  padding: 18px 20px;
  box-shadow: 0 12px 32px rgba(15, 23, 42, 0.25);
}
.modal-wide {
  width: 680px;
}
.modal h3 {
  margin: 0 0 14px;
  font-size: 16px;
}
.modal h4 {
  margin: 0 0 8px;
  font-size: 13px;
  color: #334155;
}
.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px 12px;
}
.form-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12px;
  color: var(--muted);
}
.form-item.wide {
  grid-column: 1 / -1;
}
.form-item input,
.form-item textarea,
.form-item select {
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 6px 8px;
  font-size: 13px;
  color: #1f2937;
  font-family: inherit;
}
.period-range {
  display: flex;
  align-items: center;
  gap: 6px;
}
.period-range input {
  flex: 1;
  min-width: 0;
}
.period-range em {
  font-style: normal;
  color: var(--muted);
  font-size: 12px;
}
.form-hint {
  margin: 10px 0 0;
  font-size: 12px;
  color: var(--muted);
}
.form-error {
  margin: 10px 0 0;
  font-size: 12px;
}
.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 16px;
}
.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.detail-section {
  border-top: 1px dashed var(--border);
  padding-top: 10px;
  margin-top: 12px;
}
.detail-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px 16px;
  margin: 0;
}
.detail-grid dt {
  font-size: 12px;
  color: var(--muted);
}
.detail-grid dd {
  margin: 2px 0 0;
  font-size: 13px;
}
.detail-grid .wide-col {
  grid-column: 1 / -1;
}
.progress-track {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
}
.progress-track li {
  flex: 1;
  position: relative;
  padding-left: 20px;
  font-size: 12px;
}
.progress-track li::before {
  content: '';
  position: absolute;
  top: 6px;
  left: 0;
  width: 100%;
  height: 2px;
  background: var(--border);
}
.progress-track li:first-child::before {
  width: 8px;
}
.progress-track .dot {
  position: relative;
  z-index: 1;
  display: inline-block;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: #cbd5e1;
  border: 2px solid #fff;
  margin-bottom: 4px;
}
.progress-track li.done::before,
.progress-track li.current::before {
  background: var(--brand);
}
.progress-track li.done .dot,
.progress-track li.current .dot {
  background: var(--brand);
}
.step-name {
  display: block;
  color: #334155;
}
.step-time {
  display: block;
  color: var(--muted);
  font-size: 11px;
}
</style>
