from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Comment, Ticket, TicketPriority, TicketStatus, User, UserRole
from app.schemas import (
    CommentCreate,
    CommentRead,
    TicketCreate,
    TicketDetail,
    TicketList,
    TicketRead,
    TicketUpdate,
)
from app.services import add_audit_event, calculate_due_at

router = APIRouter(prefix="/tickets", tags=["tickets"])
STAFF_ROLES = {UserRole.AGENT, UserRole.ADMIN}


def ticket_query():
    return select(Ticket).options(selectinload(Ticket.comments), selectinload(Ticket.audit_events))


def get_ticket_or_404(db: Session, ticket_id: int, user: User) -> Ticket:
    ticket = db.scalar(ticket_query().where(Ticket.id == ticket_id))
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket no encontrado")
    if user.role == UserRole.CUSTOMER and ticket.requester_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket no encontrado")
    return ticket


def serialize_ticket(ticket: Ticket, user: User) -> TicketDetail:
    base = TicketRead.model_validate(ticket).model_dump()
    comments = ticket.comments
    audits = ticket.audit_events
    if user.role == UserRole.CUSTOMER:
        comments = [comment for comment in comments if not comment.is_internal]
        audits = []
    return TicketDetail(
        **base,
        comments=[CommentRead.model_validate(comment) for comment in comments],
        audit_events=audits,
    )


@router.post("", response_model=TicketRead, status_code=status.HTTP_201_CREATED)
def create_ticket(
    payload: TicketCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Ticket:
    ticket = Ticket(
        **payload.model_dump(),
        requester_id=current_user.id,
        due_at=calculate_due_at(payload.priority),
    )
    db.add(ticket)
    db.flush()
    add_audit_event(
        db,
        ticket_id=ticket.id,
        actor_id=current_user.id,
        action="ticket.created",
        details={"priority": payload.priority.value},
    )
    db.commit()
    db.refresh(ticket)
    return ticket


@router.get("", response_model=TicketList)
def list_tickets(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    ticket_status: TicketStatus | None = Query(None, alias="status"),
    priority: TicketPriority | None = None,
    search: str | None = Query(None, min_length=2, max_length=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TicketList:
    conditions = []
    if current_user.role == UserRole.CUSTOMER:
        conditions.append(Ticket.requester_id == current_user.id)
    if ticket_status:
        conditions.append(Ticket.status == ticket_status)
    if priority:
        conditions.append(Ticket.priority == priority)
    if search:
        pattern = f"%{search}%"
        conditions.append(or_(Ticket.title.ilike(pattern), Ticket.description.ilike(pattern)))

    count_stmt = select(func.count()).select_from(Ticket).where(*conditions)
    data_stmt = (
        select(Ticket)
        .where(*conditions)
        .order_by(Ticket.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return TicketList(
        items=list(db.scalars(data_stmt).all()),
        total=db.scalar(count_stmt) or 0,
        page=page,
        page_size=page_size,
    )


@router.get("/{ticket_id}", response_model=TicketDetail)
def get_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TicketDetail:
    return serialize_ticket(get_ticket_or_404(db, ticket_id, current_user), current_user)


@router.patch("/{ticket_id}", response_model=TicketRead)
def update_ticket(
    ticket_id: int,
    payload: TicketUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Ticket:
    ticket = get_ticket_or_404(db, ticket_id, current_user)
    changes = payload.model_dump(exclude_unset=True)
    staff_fields = {"priority", "status", "assignee_id"}
    if current_user.role == UserRole.CUSTOMER and staff_fields.intersection(changes):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permiso insuficiente")
    if (
        ticket.status in {TicketStatus.RESOLVED, TicketStatus.CLOSED}
        and current_user.role == UserRole.CUSTOMER
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="El ticket ya está finalizado"
        )
    if "assignee_id" in changes and changes["assignee_id"] is not None:
        assignee = db.get(User, changes["assignee_id"])
        if assignee is None or assignee.role not in STAFF_ROLES:
            raise HTTPException(
                status_code=422, detail="El responsable debe ser agente o administrador"
            )

    normalized: dict[str, object] = {}
    for field, value in changes.items():
        setattr(ticket, field, value)
        normalized[field] = value.value if hasattr(value, "value") else value
    if "priority" in changes:
        ticket.due_at = calculate_due_at(ticket.priority)
    if ticket.status in {TicketStatus.RESOLVED, TicketStatus.CLOSED} and ticket.resolved_at is None:
        ticket.resolved_at = datetime.now(UTC)
    elif ticket.status not in {TicketStatus.RESOLVED, TicketStatus.CLOSED}:
        ticket.resolved_at = None

    add_audit_event(
        db,
        ticket_id=ticket.id,
        actor_id=current_user.id,
        action="ticket.updated",
        details=normalized,
    )
    db.commit()
    db.refresh(ticket)
    return ticket


@router.post("/{ticket_id}/comments", response_model=CommentRead, status_code=201)
def add_comment(
    ticket_id: int,
    payload: CommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Comment:
    ticket = get_ticket_or_404(db, ticket_id, current_user)
    if payload.is_internal and current_user.role not in STAFF_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permiso insuficiente")
    comment = Comment(
        ticket_id=ticket.id,
        author_id=current_user.id,
        body=payload.body,
        is_internal=payload.is_internal,
    )
    db.add(comment)
    add_audit_event(
        db,
        ticket_id=ticket.id,
        actor_id=current_user.id,
        action="comment.created",
        details={"internal": payload.is_internal},
    )
    db.commit()
    db.refresh(comment)
    return comment
