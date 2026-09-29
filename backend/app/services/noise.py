"""噪声投诉业务规则：受理校验、处置/回访流转、超期定位、按区域统计投诉频次。"""
from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timedelta
from typing import Any

from app.store import store

MODULE = "noise"
REQUIRED_FIELDS = ["投诉人", "联系电话", "投诉时段", "涉及区域"]
# 受理后按「待受理 → 处置中 → 待回访 → 已回访」推进，前三个环节都属于未办结。
STATUS_ORDER = ["待受理", "处置中", "待回访", "已回访"]
ACTION_RULES = {"受理投诉": "处置中", "完成处置": "待回访", "补录回访": "已回访"}
NEGATIVE_ACTIONS: list[str] = []

# 投诉时段必须是「2026-09-29 22:00~23:30」这种起止完整、先后有序的形式。
PERIOD_PATTERN = re.compile(r"^(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2})~(\d{2}:\d{2})$")
PHONE_PATTERN = re.compile(r"^\d{7,15}$")
REVISIT_DAYS = 3  # 处置完成后 3 日内须回访，逾期未回访单独定位。
DETAIL_FIELDS = [
    "投诉编号", "投诉人", "联系电话", "投诉时段", "涉及区域", "投诉内容",
    "受理时间", "处置人员", "处置完成时间", "回访期限",
    "回访时间", "回访结论", "降噪措施",
]


def _now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _parse_period(period: str) -> tuple[datetime, datetime] | None:
    """把规范的投诉时段拆成起止时刻；不规范时返回 None，由上层拒绝保存。"""
    match = PERIOD_PATTERN.match(period.strip())
    if match is None:
        return None
    day, start_text, end_text = match.groups()
    try:
        start = datetime.strptime(f"{day} {start_text}", "%Y-%m-%d %H:%M")
        end = datetime.strptime(f"{day} {end_text}", "%Y-%m-%d %H:%M")
    except ValueError:
        return None
    if end <= start:
        return None
    return start, end


def _period_day(period: str) -> str:
    """取投诉时段所属日期，用于按投诉时段（日期）筛选。"""
    return period.strip()[:10]


def _is_overdue(row: dict[str, Any], *, now: datetime | None = None) -> bool:
    """处置完成后超过回访期限仍未补录回访，即超期未回访。"""
    if row.get("status") != "待回访":
        return False
    deadline = str(row.get("回访期限") or "").strip()
    if not deadline:
        return False
    try:
        due = datetime.strptime(deadline, "%Y-%m-%d")
    except ValueError:
        return False
    current = now or datetime.now()
    return current.date() > due.date()


def _frequency(rows: list[dict[str, Any]]) -> Counter[str]:
    """投诉频次口径：同一涉及区域内已受理投诉的条数。"""
    return Counter(str(row.get("涉及区域") or "").strip() for row in rows)


def _attach_progress(row: dict[str, Any], freq: Counter[str]) -> dict[str, Any]:
    """补齐列表与单条共用的派生字段，保证两处看到的是同一份处置进度。"""
    row["投诉频次"] = freq.get(str(row.get("涉及区域") or "").strip(), 0)
    row["投诉状态"] = row.get("status", "")
    row["超期未回访"] = _is_overdue(row)
    return row


class NoiseService:
    def list_entries(
        self,
        *,
        period: str | None = None,
        area: str | None = None,
        status: str | None = None,
        overdue_only: bool = False,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if period:
            period = period.strip()
            rows = [row for row in rows if _period_day(str(row.get("投诉时段", ""))) == period]
        if area:
            area = area.strip()
            rows = [row for row in rows if area in str(row.get("涉及区域", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        if overdue_only:
            rows = [row for row in rows if _is_overdue(row)]

        freq = _frequency(rows)
        decorated = [_attach_progress(dict(row), freq) for row in rows]
        # 按投诉频次降序；频次相同时受理时间晚的排前面，再相同时按 id 稳定排序。
        decorated.sort(
            key=lambda row: (
                -int(row.get("投诉频次", 0)),
                -int(row.get("id", 0)),
            )
        )
        total = len(decorated)
        start = max(page - 1, 0) * size
        return decorated[start:start + size], total

    def all_overdue_ids(self) -> list[int]:
        """供看板/统计使用：直接定位全部超期未回访投诉。"""
        return [int(row["id"]) for row in store.rows(MODULE) if _is_overdue(row)]

    def stats(self) -> dict[str, int]:
        rows = store.rows(MODULE)
        counts = Counter(str(row.get("status") or "") for row in rows)
        return {
            "total": len(rows),
            "pendingAccept": counts.get("待受理", 0),
            "handling": counts.get("处置中", 0),
            "awaitingRevisit": counts.get("待回访", 0),
            "revisited": counts.get("已回访", 0),
            "overdue": sum(1 for row in rows if _is_overdue(row)),
        }

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        row = store.find(MODULE, entry_id)
        if row is None:
            return None
        # 频次按全量口径计算，保证列表与单条看到的区域频次一致。
        return _attach_progress(dict(row), _frequency(store.rows(MODULE)))

    def validate_period(self, period: Any) -> str | None:
        """校验投诉时段规范性，返回可读的拒绝原因；规范时返回 None。"""
        text = str(period or "").strip()
        if not text:
            return "投诉时段不能为空，请按「YYYY-MM-DD HH:MM~HH:MM」填写，例如 2026-09-29 22:00~23:30"
        if not PERIOD_PATTERN.match(text):
            return "投诉时段格式不规范，应为「YYYY-MM-DD HH:MM~HH:MM」，例如 2026-09-29 22:00~23:30"
        if _parse_period(text) is None:
            return "投诉时段不规范：日期或时刻不存在，或结束时刻不晚于开始时刻"
        return None

    def create_entry(
        self, values: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, str]:
        """登记投诉受理信息；重复提交或时段不规范时拒绝保存并说明原因。"""
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, f"缺少必填字段：{'、'.join(missing)}"

        period = str(values["投诉时段"]).strip()
        period_error = self.validate_period(period)
        if period_error:
            return None, period_error

        phone = str(values["联系电话"]).strip()
        if not PHONE_PATTERN.match(phone):
            return None, "联系电话不规范：应为 7~15 位数字（座机可带区号连写）"

        complainant = str(values["投诉人"]).strip()
        area = str(values["涉及区域"]).strip()
        rows = store.rows(MODULE)
        # 同一投诉人、同一电话、同一时段、同一区域视为同一条投诉重复提交。
        duplicate = next(
            (
                row for row in rows
                if str(row.get("投诉人", "")).strip() == complainant
                and str(row.get("联系电话", "")).strip() == phone
                and str(row.get("投诉时段", "")).strip() == period
                and str(row.get("涉及区域", "")).strip() == area
            ),
            None,
        )
        if duplicate is not None:
            return None, (
                f"该投诉已登记（投诉编号 {duplicate.get('投诉编号')}，受理时间 {duplicate.get('受理时间')}），"
                "同一投诉人、联系电话、投诉时段与涉及区域的投诉请勿重复提交"
            )

        next_id = max((int(row.get("id", 0)) for row in rows), default=0) + 1
        entry: dict[str, Any] = {
            "id": next_id,
            "投诉编号": f"NOIS-{next_id:04d}",
            "投诉人": complainant,
            "联系电话": phone,
            "投诉时段": period,
            "涉及区域": area,
            "投诉内容": str(values.get("投诉内容") or "").strip(),
            "受理时间": _now_text(),
            "处置人员": str(values.get("处置人员") or "").strip(),
            "处置完成时间": "",
            "回访期限": "",
            "回访时间": "",
            "回访结论": "",
            "降噪措施": "",
            "status": STATUS_ORDER[0],
            "pending": True,
            "abnormal": False,
        }
        rows.append(entry)
        return self.get_entry(next_id), ""

    def run_action(
        self, entry_id: int, action: str, values: dict[str, Any] | None = None
    ) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"噪声投诉 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于噪声投诉可执行范围"

        values = values or {}
        status = str(entry.get("status") or "")

        if action == "受理投诉":
            if status != "待受理":
                return None, f"当前状态为「{status}」，不能重复受理"
            handler = str(values.get("处置人员") or entry.get("处置人员") or "").strip()
            if not handler:
                return None, "受理投诉需先指定处置人员"
            entry["处置人员"] = handler
            entry["status"] = "处置中"

        elif action == "完成处置":
            if status != "处置中":
                return None, f"当前状态为「{status}」，仅处置中的投诉可以完成处置"
            finished_at = _now_text()
            entry["处置完成时间"] = finished_at
            entry["回访期限"] = (datetime.now() + timedelta(days=REVISIT_DAYS)).strftime("%Y-%m-%d")
            entry["status"] = "待回访"

        elif action == "补录回访":
            if status != "待回访":
                return None, f"当前状态为「{status}」，仅处置完成、待回访的投诉可以补录回访"
            revisit_fields = ["回访时间", "回访结论", "降噪措施"]
            missing = [field for field in revisit_fields if not str(values.get(field) or "").strip()]
            if missing:
                return None, f"补录回访缺少必填项：{'、'.join(missing)}"
            revisit_at = str(values["回访时间"]).strip()
            try:
                revisit_time = datetime.strptime(revisit_at, "%Y-%m-%d %H:%M")
            except ValueError:
                return None, "回访时间不规范，应为「YYYY-MM-DD HH:MM」，例如 2026-09-29 10:30"
            entry["回访时间"] = revisit_time.strftime("%Y-%m-%d %H:%M")
            entry["回访结论"] = str(values["回访结论"]).strip()
            entry["降噪措施"] = str(values["降噪措施"]).strip()
            entry["status"] = "已回访"

        # 已回访为办结状态；待回访仍属待处理，且逾期的在看板异常量里单独体现。
        entry["pending"] = entry["status"] != "已回访"
        entry["abnormal"] = _is_overdue(entry)
        return self.get_entry(entry_id), f"噪声投诉已{action}"

    def export_entries(
        self,
        *,
        period: str | None = None,
        area: str | None = None,
        status: str | None = None,
        overdue_only: bool = False,
    ) -> tuple[list[dict[str, Any]], int]:
        return self.list_entries(
            period=period,
            area=area,
            status=status,
            overdue_only=overdue_only,
            page=1,
            size=10000,
        )
