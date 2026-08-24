from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.models import AuditEvent, TicketPriority

SLA_HOURS = {
    TicketPriority.LOW: 72,
    TicketPriority.MEDIUM: 24,
    TicketPriority.HIGH: 8,
    TicketPriority.URGENT: 2,
}


def calculate_due_at(priority: TicketPriority) -> datetime:
    return datetime.now(UTC) + timedelta(hours=SLA_HOURS[priority])


def add_audit_event(
    db: Session, *, ticket_id: int, actor_id: int, action: str, details: dict | None = None
) -> None:
    db.add(
        AuditEvent(
            ticket_id=ticket_id,
            actor_id=actor_id,
            action=action,
            details=details or {},
        )
    )
