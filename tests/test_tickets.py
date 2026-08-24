from fastapi.testclient import TestClient

from tests.conftest import login_staff, register_and_login

TICKET = {
    "title": "No puedo acceder al portal",
    "description": "El portal muestra un error 403 desde esta mañana.",
    "category": "access",
    "priority": "high",
}


def test_ticket_lifecycle_and_audit(client: TestClient) -> None:
    customer_headers = register_and_login(client)
    created = client.post("/api/v1/tickets", json=TICKET, headers=customer_headers)
    assert created.status_code == 201
    ticket_id = created.json()["id"]
    assert created.json()["sla_breached"] is False

    agent_headers = login_staff(client)
    updated = client.patch(
        f"/api/v1/tickets/{ticket_id}",
        json={"status": "in_progress", "priority": "urgent"},
        headers=agent_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "in_progress"

    comment = client.post(
        f"/api/v1/tickets/{ticket_id}/comments",
        json={"body": "Diagnóstico interno", "is_internal": True},
        headers=agent_headers,
    )
    assert comment.status_code == 201

    customer_view = client.get(f"/api/v1/tickets/{ticket_id}", headers=customer_headers).json()
    assert customer_view["comments"] == []
    assert customer_view["audit_events"] == []

    agent_view = client.get(f"/api/v1/tickets/{ticket_id}", headers=agent_headers).json()
    assert len(agent_view["comments"]) == 1
    assert len(agent_view["audit_events"]) == 3


def test_customer_cannot_manage_another_ticket(client: TestClient) -> None:
    owner_headers = register_and_login(client, "owner@example.com")
    ticket_id = client.post("/api/v1/tickets", json=TICKET, headers=owner_headers).json()["id"]
    other_headers = register_and_login(client, "other@example.com")
    assert client.get(f"/api/v1/tickets/{ticket_id}", headers=other_headers).status_code == 404
    assert (
        client.patch(
            f"/api/v1/tickets/{ticket_id}", json={"status": "closed"}, headers=owner_headers
        ).status_code
        == 403
    )


def test_filters_pagination_and_analytics(client: TestClient) -> None:
    customer_headers = register_and_login(client)
    client.post("/api/v1/tickets", json=TICKET, headers=customer_headers)
    client.post(
        "/api/v1/tickets",
        json={**TICKET, "title": "La impresora no responde", "priority": "low"},
        headers=customer_headers,
    )
    filtered = client.get(
        "/api/v1/tickets?priority=high&page=1&page_size=10", headers=customer_headers
    ).json()
    assert filtered["total"] == 1
    assert filtered["items"][0]["category"] == "access"

    agent_headers = login_staff(client)
    analytics = client.get("/api/v1/analytics/summary", headers=agent_headers)
    assert analytics.status_code == 200
    assert analytics.json()["total_tickets"] == 2
    assert analytics.json()["sla_compliance_percent"] == 100.0
