"""噪声投诉业务规则：受理校验、投诉时段规范、处置进度流转与回访超期判定。

与其它模块一样，数据暂存内存；本模块额外承担：
- 登记时拒绝重复提交与不规范投诉时段，并给出可读原因；
- 列表按同一区域、同一时段的投诉频次降序排列；
- 处置完成后补录回访信息，超过时限未回访的单独标记。
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any

from app.store import store

MODULE = "noise"

REQUIRED_FIELDS = ["投诉人", "联系电话", "投诉时段", "涉及区域"]
LIST_FIELDS = [
    "投诉编号",
    "投诉人",
    "联系电话",
    "投诉时段",
    "涉及区域",
    "受理时间",
    "处置状态",
]
STATUSES = ["待受理", "处置中", "待回访", "已回访"]
ACTION_RULES = {"受理投诉": "处置中", "完成处置": "待回访"}
# 处置完成后超过 3 天仍未补录回访，即视为超期未回访。
VISIT_DEADLINE_DAYS = 3

# 投诉时段统一为「YYYY-MM-DD HH:MM-HH:MM」，起止同一天、起早于止。
PERIOD_PATTERN = re.compile(r"^(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2})-(\d{2}:\d{2})$")
# 回访时间按「YYYY-MM-DD HH:MM」填写。
DATETIME_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$")
# 联系电话：手机号或带区号的座机，允许连字符。
PHONE_PATTERN = re.compile(r"^(?:1\d{10}|0\d{2,3}-?\d{7,8})$")


def _parse_period(period: str) -> tuple[date, datetime, datetime] | None:
    """校验投诉时段格式，返回日期与起止时刻；不规范时返回 None。"""
    match = PERIOD_PATTERN.match(period.strip())
    if not match:
        return None
    day_text, start_text, end_text = match.groups()
    try:
        day = datetime.strptime(day_text, "%Y-%m-%d").date()
        start = datetime.strptime(f"{day_text} {start_text}", "%Y-%m-%d %H:%M")
        end = datetime.strptime(f"{day_text} {end_text}", "%Y-%m-%d %H:%M")
    except ValueError:
        return None
    if end <= start:
        return None
    return day, start, end


def _frequency_key(row: dict[str, Any]) -> tuple[str, str]:
    """投诉频次的归并口径：同一涉及区域、同一日内时段（HH:MM-HH:MM）。"""
    parsed = _parse_period(str(row.get("投诉时段", "")))
    if parsed is None:
        return str(row.get("涉及区域", "")), str(row.get("投诉时段", ""))
    _, start, end = parsed
    return str(row.get("涉及区域", "")), f"{start:%H:%M}-{end:%H:%M}"


def _is_overdue(row: dict[str, Any], *, today: date | None = None) -> bool:
    """仅「待回访」状态可能超期：处置完成日起超过回访时限。"""
    if row.get("status") != "待回访":
        return False
    finished_text = str(row.get("处置完成时间") or "")
    if not finished_text:
        return False
    try:
        finished = datetime.strptime(finished_text[:16], "%Y-%m-%d %H:%M").date()
    except ValueError:
        return False
    current = today or date.today()
    return current > finished + timedelta(days=VISIT_DEADLINE_DAYS)


def _decorate(row: dict[str, Any], frequencies: dict[tuple[str, str], int]) -> dict[str, Any]:
    """列表/明细共用的派生字段：投诉频次、超期标记、处置进度提示。"""
    decorated = dict(row)
    decorated["投诉频次"] = frequencies.get(_frequency_key(row), 1)
    decorated["超期未回访"] = _is_overdue(row)
    return decorated


class NoiseService:
    def list_entries(
        self,
        *,
        period: str | None = None,
        area: str | None = None,
        status: str | None = None,
        overdue_only: bool = False,
        keyword: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        """按投诉时段、涉及区域等条件过滤，并按投诉频次降序排列。"""
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("投诉编号", ""))]
        if period:
            rows = [row for row in rows if period in str(row.get("投诉时段", ""))]
        if area:
            rows = [row for row in rows if area.strip() in str(row.get("涉及区域", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]

        frequencies: dict[tuple[str, str], int] = {}
        for row in store.rows(MODULE):
            key = _frequency_key(row)
            frequencies[key] = frequencies.get(key, 0) + 1

        decorated = [_decorate(row, frequencies) for row in rows]
        if overdue_only:
            decorated = [row for row in decorated if row["超期未回访"]]
        # 投诉频次高的排前面；频次相同按受理先后（id）稳定排列。
        decorated.sort(key=lambda row: (-int(row["投诉频次"]), int(row.get("id", 0))))
        total = len(decorated)
        start = max(page - 1, 0) * size
        return decorated[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        """读取单条投诉明细，派生字段与列表同源，保证处置进度一致。"""
        row = store.find(MODULE, entry_id)
        if row is None:
            return None
        frequencies: dict[tuple[str, str], int] = {}
        for existing in store.rows(MODULE):
            key = _frequency_key(existing)
            frequencies[key] = frequencies.get(key, 0) + 1
        return _decorate(row, frequencies)

    def filter_options(self) -> dict[str, list[str]]:
        """提供涉及区域下拉选项：直接来自已登记投诉，避免手输错选。"""
        areas = sorted({str(row.get("涉及区域", "")).strip() for row in store.rows(MODULE) if row.get("涉及区域")})
        return {"areas": areas, "statuses": list(STATUSES)}

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        """登记受理信息；缺项、时段不规范、重复提交都会被拒绝并逐条说明原因。"""
        reasons = [
            f"缺少必填字段：{field}"
            for field in REQUIRED_FIELDS
            if not str(values.get(field) or "").strip()
        ]
        if reasons:
            return None, reasons

        complainant = str(values["投诉人"]).strip()
        phone = str(values["联系电话"]).strip()
        period = str(values["投诉时段"]).strip()
        area = str(values["涉及区域"]).strip()

        if not PHONE_PATTERN.match(phone):
            reasons.append("联系电话格式不正确：请填写 11 位手机号或带区号座机号")
        if _parse_period(period) is None:
            reasons.append(
                "投诉时段不规范：需为「YYYY-MM-DD HH:MM-HH:MM」，起止须为同一天且开始早于结束"
            )
        if reasons:
            return None, reasons

        # 同一投诉人对同一区域、同一完整时段重复提交视为重复登记。
        duplicate = next(
            (
                row for row in store.rows(MODULE)
                if str(row.get("投诉人", "")).strip() == complainant
                and str(row.get("涉及区域", "")).strip() == area
                and str(row.get("投诉时段", "")).strip() == period
            ),
            None,
        )
        if duplicate is not None:
            return None, [
                f"投诉重复提交：与投诉编号 {duplicate.get('投诉编号')} 的投诉人、涉及区域、投诉时段完全一致"
            ]

        rows = store.rows(MODULE)
        next_id = max((int(row.get("id", 0)) for row in rows), default=0) + 1
        accepted_at = datetime.now().strftime("%Y-%m-%d %H:%M")
        entry = {
            "id": next_id,
            "投诉编号": f"NOIS-{next_id:04d}",
            "投诉人": complainant,
            "联系电话": phone,
            "投诉时段": period,
            "涉及区域": area,
            "受理时间": accepted_at,
            "处置状态": "",
            "处置人员": "",
            "处置完成时间": "",
            "回访时间": "",
            "回访结论": "",
            "降噪措施": "",
            "status": STATUSES[0],
            "pending": True,
            "abnormal": False,
        }
        rows.append(entry)
        return self.get_entry(next_id), []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        """推进处置进度：受理投诉 -> 处置中；完成处置 -> 待回访。"""
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"投诉记录 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于噪声投诉可执行范围"
        target = ACTION_RULES[action]
        current_index = STATUSES.index(entry["status"]) if entry.get("status") in STATUSES else -1
        target_index = STATUSES.index(target)
        if target_index <= current_index:
            return None, f"投诉当前为「{entry.get('status')}」，不能执行「{action}」"

        if action == "受理投诉":
            entry["处置人员"] = "值班调度员"
        elif action == "完成处置":
            entry["处置完成时间"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            entry["处置状态"] = "已处置待回访"

        entry["status"] = target
        entry["pending"] = True
        entry["abnormal"] = False
        return self.get_entry(entry_id), f"投诉已{action}"

    def record_visit(self, entry_id: int, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        """处置完成后补录回访时间、回访结论与降噪措施，三项缺一不可。"""
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, [f"投诉记录 {entry_id} 不存在或已归档"]
        if entry.get("status") != "待回访":
            return None, [f"投诉当前为「{entry.get('status')}」，仅处置完成（待回访）的记录可以补录回访"]

        visit_time = str(values.get("回访时间") or "").strip()
        conclusion = str(values.get("回访结论") or "").strip()
        measures = str(values.get("降噪措施") or "").strip()
        reasons: list[str] = []
        if not visit_time:
            reasons.append("缺少必填字段：回访时间")
        elif not DATETIME_PATTERN.match(visit_time):
            reasons.append("回访时间不规范：需为「YYYY-MM-DD HH:MM」")
        if not conclusion:
            reasons.append("缺少必填字段：回访结论")
        if not measures:
            reasons.append("缺少必填字段：降噪措施")
        if reasons:
            return None, reasons

        entry["回访时间"] = visit_time
        entry["回访结论"] = conclusion
        entry["降噪措施"] = measures
        entry["status"] = "已回访"
        entry["处置状态"] = "已回访闭环"
        entry["pending"] = False
        entry["abnormal"] = False
        return self.get_entry(entry_id), []
