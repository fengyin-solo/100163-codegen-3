"""噪声投诉接口：受理登记、按投诉时段/区域筛选、处置流转与回访补录。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.noise import LIST_FIELDS, STATUSES, NoiseService

router = APIRouter(prefix="/api/noise", tags=["噪声投诉"])

service = NoiseService()


@router.get("", response_model=PageResult[dict])
def list_entries(
    period: str | None = Query(default=None, description="按投诉时段过滤，支持日期或完整时段片段"),
    area: str | None = Query(default=None, description="按涉及区域过滤"),
    status: str | None = Query(default=None, description="待受理、处置中、待回访、已回访"),
    overdue: bool = Query(default=False, description="仅定位超期未回访的投诉"),
    keyword: str | None = Query(default=None, description="按投诉编号检索"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按投诉时段与涉及区域等条件查询，结果按投诉频次降序；无数据返回空页。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(
        period=period,
        area=area,
        status=status,
        overdue_only=overdue,
        keyword=keyword,
        page=page,
        size=size,
    )
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/options")
def filter_options() -> dict[str, list[str]]:
    """筛选项：涉及区域下拉数据与状态枚举。"""
    return service.filter_options()


@router.get("/export")
def export_entries(
    period: str | None = None,
    area: str | None = None,
    status: str | None = None,
    overdue: bool = False,
) -> dict[str, Any]:
    """导出当前筛选条件下的噪声投诉清单（保持频次排序）。"""
    items, total = service.list_entries(
        period=period, area=area, status=status, overdue_only=overdue, page=1, size=10000
    )
    return {"module": "noise", "total": total, "items": items}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条投诉明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"投诉记录 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记投诉受理信息；重复提交或投诉时段不规范时拒绝保存并说明原因。"""
    entry, reasons = service.create_entry(payload.values)
    if reasons:
        return ActionResult(ok=False, message="；".join(reasons))
    return ActionResult(ok=True, message="噪声投诉已受理登记", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """推进处置进度：受理投诉、完成处置；非法或乱序的动作会被拦下。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


@router.post("/{entry_id}/visit", response_model=ActionResult)
def record_visit(entry_id: int, payload: EntryPayload) -> ActionResult:
    """处置完成后补录回访时间、回访结论与降噪措施。"""
    entry, reasons = service.record_visit(entry_id, payload.values)
    if entry is None:
        return ActionResult(ok=False, message="；".join(reasons))
    return ActionResult(ok=True, message="回访信息已补录，投诉闭环", entry=entry)
