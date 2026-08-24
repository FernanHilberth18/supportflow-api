# SupportFlow API

[![CI](https://github.com/FernanHilberth18/supportflow-api/actions/workflows/ci.yml/badge.svg)](https://github.com/FernanHilberth18/supportflow-api/actions/workflows/ci.yml)

API REST de soporte técnico lista para portafolio: autenticación JWT, roles, SLA, auditoría, comentarios, filtros y métricas operativas.

## Tecnologías

- Python 3.13, FastAPI, SQLAlchemy 2 y Pydantic 2
- PostgreSQL 16 en producción y SQLite para pruebas
- JWT con contraseñas protegidas mediante bcrypt
- Pytest, cobertura, Ruff y GitHub Actions
- Docker y Docker Compose

## Inicio rápido

```powershell
Copy-Item .env.example .env
# Completa DATABASE_URL, JWT_SECRET y las credenciales bootstrap solo en `.env`.
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
.venv\Scripts\python -m uvicorn app.main:app --reload
```

Documentación interactiva: `http://127.0.0.1:8000/docs`.

## Flujo de demostración

1. Registra dos usuarios en `POST /api/v1/auth/register`.
2. Inicia sesión en `POST /api/v1/auth/login` y copia el token.
3. Crea un ticket en `POST /api/v1/tickets`.
4. Inicia sesión con el administrador bootstrap configurado en `.env` y promueve al segundo usuario con `PATCH /api/v1/users/{id}/role`.
5. El agente asigna, comenta y cambia el estado del ticket.
6. Consulta métricas en `GET /api/v1/analytics/summary`.

## Controles incluidos

- Los clientes solo ven sus propios tickets y comentarios públicos.
- Agentes y administradores pueden gestionar toda la cola.
- Solo los administradores cambian roles.
- Cada cambio relevante genera un registro de auditoría.
- Fechas objetivo se calculan según prioridad y exponen si el SLA fue incumplido.

## Calidad

```powershell
.venv\Scripts\python -m ruff check .
.venv\Scripts\python -m pytest --cov=app --cov-report=term-missing
```

## Variables de entorno

Consulta `.env.example`. El secreto JWT y las credenciales del entorno real nunca deben versionarse.
