"""噪声投诉接口：登记受理信息，按时段/区域筛选与频次排序，处置完成后补录回访。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.noise import STATUS_ORDER, NoiseService

router = APIRouter(prefix="/api/noise", tags=["噪声投诉"])

service = NoiseService()

LIST_FIELDS = [
    "投诉编号", "投诉人", "联系电话", "投诉时段", "涉及区域",
    "投诉频次", "处置人员", "受理时间", "处置完成时间", "回访期限",
    "回访时间", "回访结论", "降噪措施", "投诉状态",
]
STATUSES = STATUS_ORDER


@router.get("", response_model=PageResult[dict])
def list_entries(
    period: str | None = Query(default=None, description="按投诉时段日期筛选，格式 YYYY-MM-DD"),
    area: str | None = Query(default=None, description="按涉及区域模糊筛选"),
    status: str | None = Query(default=None, description="待受理、处置中、待回访、已回访"),
    overdue: bool = Query(default=False, description="仅看超期未回访"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按投诉时段与涉及区域筛选，并按区域投诉频次降序排列。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(
        period=period, area=area, status=status, overdue_only=overdue, page=page, size=size
    )
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/stats")
def complaint_stats() -> dict[str, int]:
    """各处置环节数量与超期未回访数量，供页面顶部指标卡使用。"""
    return service.stats()


@router.get("/export")
def export_entries(
    period: str | None = None,
    area: str | None = None,
    status: str | None = None,
    overdue: bool = False,
) -> dict[str, Any]:
    """导出噪声投诉清单：返回当前筛选条件下的全量数据。"""
    items, total = service.export_entries(
        period=period, area=area, status=status, overdue_only=overdue
    )
    return {"module": "noise", "total": total, "items": items}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条投诉明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"噪声投诉 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记投诉受理信息；重复提交或投诉时段不规范时拒绝保存并说明原因。"""
    entry, message = service.create_entry(payload.values)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message="噪声投诉已登记受理", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """执行受理投诉、完成处置、补录回访；不允许的动作或越环节流转会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action, payload.values)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
