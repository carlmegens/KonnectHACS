"""Bounded projection of Dutch childcare planning; no provider mutations."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo

from .api import OuderAppError
from .content import _safe_text

TIME_ZONE = ZoneInfo("Europe/Amsterdam")
MAX_DAYS = 31
MAX_EVENTS = 100
MAX_RAW_SLOTS = 5000


@dataclass(frozen=True)
class Period:
    start: date
    end: date

    @property
    def start_time(self) -> datetime:
        return datetime.combine(self.start, time.min, TIME_ZONE)

    @property
    def end_time(self) -> datetime:
        return datetime.combine(self.end, time.min, TIME_ZONE)


def date_value(value: Any) -> date:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        raise ValueError("Use YYYY-MM-DD")
    result = date.fromisoformat(value)
    if not 1970 <= result.year <= 2100:
        raise ValueError("Unsupported year")
    return result


def period_for(start: Any, end: Any) -> Period:
    period = Period(date_value(start), date_value(end))
    if not 1 <= (period.end - period.start).days <= MAX_DAYS:
        raise ValueError("Planning period must contain 1 to 31 days")
    return period


def limit_value(value: Any) -> int:
    if type(value) is not int or not 1 <= value <= MAX_EVENTS:
        raise ValueError("Planning limit must be between 1 and 100")
    return value


def _rows(value: Any, maximum: int) -> list[dict[str, Any]]:
    if (
        not isinstance(value, list)
        or len(value) > maximum
        or any(not isinstance(row, dict) for row in value)
    ):
        raise OuderAppError("Unsupported planning shape")
    return value


def _timestamp(value: Any) -> datetime:
    if type(value) is not int:
        raise OuderAppError("Unsupported planning time")
    try:
        result = datetime.fromtimestamp(value / 1000, UTC)
    except ValueError, OverflowError, OSError:
        raise OuderAppError("Unsupported planning time") from None
    if not 1970 <= result.year <= 2100:
        raise OuderAppError("Unsupported planning time")
    return result


def child_identifier(value: Any) -> str | None:
    # Child identifiers are opaque identities, not numeric conversation IDs.
    # They are only hashed locally, never interpolated into a provider route.
    if type(value) is int:
        return str(value) if 0 < value < 10**40 else None
    if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value):
        return value
    return None


def project_planning(
    payload: dict[str, Any], account_id: str, period: Period, limit: int = 50
) -> dict[str, Any]:
    """Times are milliseconds; retain attend/absent/tentative and never infer confirmation."""
    limit_value(limit)
    if not isinstance(payload, dict):
        raise OuderAppError("Unsupported planning shape")
    events: dict[str, dict[str, Any]] = {}
    count = 0
    for day in _rows(payload.get("days"), MAX_DAYS + 2):
        for group in _rows(day.get("children", []), 100):
            child = group.get("child")
            if (
                not isinstance(child, dict)
                or (child_id := child_identifier(child.get("id"))) is None
            ):
                raise OuderAppError("Unsupported planning child")
            for combined in _rows(group.get("combinedPlanningParts", []), 100):
                for slot in _rows(combined.get("planningParts", []), 100):
                    count += 1
                    if count > MAX_RAW_SLOTS:
                        raise OuderAppError("Planning response exceeds limit")
                    start, end = _timestamp(slot.get("startTime")), _timestamp(slot.get("endTime"))
                    if end <= start:
                        raise OuderAppError("Unsupported planning interval")
                    if start >= period.end_time or end <= period.start_time:
                        continue
                    code = slot.get("plannedAttendanceCode")
                    code = code.get("code") if isinstance(code, dict) else None
                    status = code if code in ("attend", "absent", "tentative") else "unknown"
                    # No stable provider slot ID has been proven. Same unchanged slot
                    # keeps its ID across reordering/refreshes; rescheduling changes it.
                    identity = hashlib.sha256(
                        f"{account_id}\0{child_id}\0{start.isoformat()}\0{end.isoformat()}".encode()
                    ).hexdigest()
                    event = {
                        "id": identity,
                        "summary": "Opvangmoment",
                        "child": _safe_text(child.get("firstName"), 100),
                        "start": start.astimezone(TIME_ZONE).isoformat(),
                        "end": end.astimezone(TIME_ZONE).isoformat(),
                        "status": status,
                        "confirmation_required": slot.get("toConfirmProduct")
                        if type(slot.get("toConfirmProduct")) is bool
                        else None,
                    }
                    if identity in events and events[identity] != event:
                        raise OuderAppError("Conflicting planning slots")
                    events[identity] = event
    ordered = sorted(
        events.values(), key=lambda event: (datetime.fromisoformat(event["start"]), event["id"])
    )
    return {
        "events": ordered[:limit],
        "returned": min(len(ordered), limit),
        "limit": limit,
        "truncated": len(ordered) > limit,
        "start_date": period.start.isoformat(),
        "end_date": period.end.isoformat(),
        "time_zone": str(TIME_ZONE),
        "data_connector_offline": payload.get("data_connector_offline") is True,
        "scope": "childcare_slots",
        "updated_at": datetime.now(UTC).isoformat(),
    }
