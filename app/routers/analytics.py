from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_roles
from app.models import Ticket, TicketPriority, TicketStatus, User, UserRole
from app.schemas import AnalyticsSummary

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/summary", response_model=AnalyticsSummary)
def summary(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.AGENT, UserRole.ADMIN)),
) -> AnalyticsSummary:
    total = db.scalar(select(func.count()).select_from(Ticket)) or 0
    open_count = (
        db.scalar(
            select(func.count())
            .select_from(Ticket)
            .where(Ticket.status.not_in([TicketStatus.RESOLVED, TicketStatus.CLOSED]))
        )
        or 0
    )
    resolved = total - open_count
    tickets = list(db.scalars(select(Ticket)).all())
    breached = sum(ticket.sla_breached for ticket in tickets)
    by_status = {
        status.value: db.scalar(
            select(func.count()).select_from(Ticket).where(Ticket.status == status)
        )
        or 0
        for status in TicketStatus
    }
    by_priority = {
        priority.value: db.scalar(
            select(func.count()).select_from(Ticket).where(Ticket.priority == priority)
        )
        or 0
        for priority in TicketPriority
    }
    compliance = round(((total - breached) / total * 100), 2) if total else 100.0
    return AnalyticsSummary(
        total_tickets=total,
        open_tickets=open_count,
        resolved_tickets=resolved,
        breached_sla=breached,
        sla_compliance_percent=compliance,
        by_status=by_status,
        by_priority=by_priority,
    )
