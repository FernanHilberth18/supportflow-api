from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import TicketPriority, TicketStatus, UserRole


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=8, max_length=72)


class UserRead(ORMModel):
    id: int
    email: EmailStr
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime


class UserRoleUpdate(BaseModel):
    role: UserRole


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead


class CommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=4000)
    is_internal: bool = False


class CommentRead(ORMModel):
    id: int
    author_id: int
    body: str
    is_internal: bool
    created_at: datetime


class AuditEventRead(ORMModel):
    id: int
    actor_id: int
    action: str
    details: dict
    created_at: datetime


class TicketCreate(BaseModel):
    title: str = Field(min_length=4, max_length=160)
    description: str = Field(min_length=10, max_length=10000)
    category: str = Field(default="general", min_length=2, max_length=80)
    priority: TicketPriority = TicketPriority.MEDIUM


class TicketUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=4, max_length=160)
    description: str | None = Field(default=None, min_length=10, max_length=10000)
    category: str | None = Field(default=None, min_length=2, max_length=80)
    priority: TicketPriority | None = None
    status: TicketStatus | None = None
    assignee_id: int | None = None


class TicketRead(ORMModel):
    id: int
    title: str
    description: str
    category: str
    priority: TicketPriority
    status: TicketStatus
    requester_id: int
    assignee_id: int | None
    due_at: datetime
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None
    sla_breached: bool


class TicketDetail(TicketRead):
    comments: list[CommentRead] = []
    audit_events: list[AuditEventRead] = []


class TicketList(BaseModel):
    items: list[TicketRead]
    total: int
    page: int
    page_size: int


class AnalyticsSummary(BaseModel):
    total_tickets: int
    open_tickets: int
    resolved_tickets: int
    breached_sla: int
    sla_compliance_percent: float
    by_status: dict[str, int]
    by_priority: dict[str, int]
