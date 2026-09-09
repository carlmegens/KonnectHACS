"""RFC 5545 snapshots from the bounded, validated planning projection."""

from datetime import UTC, datetime

from .api import OuderAppError


class CalendarExportError(OuderAppError):
    """A snapshot cannot be exported without misleading the recipient."""


def _text(value: str) -> str:
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    value = "".join(
        char
        for char in value
        if (char in "\n\t" or ord(char) >= 32)
        and ord(char) != 127
        and not 0xD800 <= ord(char) <= 0xDFFF
    )
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace(";", "\\;").replace(",", "\\,")


def _fold(line: str) -> str:
    """Fold at 75 UTF-8 octets without splitting a code point."""
    parts = []
    current = ""
    size = 0
    for char in line:
        width = len(char.encode("utf-8"))
        if size + width > 75:
            parts.append(current)
            current, size = " ", 1
        current += char
        size += width
    parts.append(current)
    return "\r\n".join(parts)


def _utc(value: str) -> str:
    return datetime.fromisoformat(value).astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def export_calendar(planning: dict) -> str:
    """Only accepts project_planning output; no files, feeds or provider writes."""
    if planning["data_connector_offline"]:
        raise CalendarExportError("Planning provider is offline; calendar export is unavailable")
    if planning["truncated"]:
        raise CalendarExportError("Planning is truncated; shorten the period or increase the limit")
    if not planning["events"]:
        raise CalendarExportError("No childcare slots in this period to export")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//KonnectHACS//OuderApp planning snapshot//NL",
        "CALSCALE:GREGORIAN",
    ]
    stamp = _utc(planning["updated_at"])
    labels = {"absent": "Afwezig", "tentative": "Voorlopig", "unknown": "Status onbekend"}
    for event in planning["events"]:
        label = labels[event["status"]]
        summary = f"Opvang — {label}"
        if event["child"]:
            summary += f" — {event['child']}"
        description = (
            f"OuderApp: {label}.\n"
            "Momentopname van opvangtijdsloten; controleer actuele planning in OuderApp.\n"
            "Deze export wordt niet automatisch bijgewerkt."
        )
        if event["confirmation_required"] is True:
            description += "\nBevestiging vereist volgens de bron."
        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{event['id']}@ouderapp.konnecthacs",
                f"DTSTAMP:{stamp}",
                f"DTSTART:{_utc(event['start'])}",
                f"DTEND:{_utc(event['end'])}",
                "CLASS:PRIVATE",
                "TRANSP:TRANSPARENT",
                f"SUMMARY:{_text(summary)}",
                f"DESCRIPTION:{_text(description)}",
                f"X-OUDERAPP-STATUS:{event['status']}",
            ]
        )
        # Absence does not prove provider cancellation; unknown does not prove
        # confirmation. Preserve both in visible text instead of inventing STATUS.
        if event["status"] == "tentative":
            lines.append("STATUS:TENTATIVE")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold(line) for line in lines) + "\r\n"
