from fastapi import APIRouter

from app.api.routers import (
    accounts,
    assets,
    documents,
    integrations,
    journal_entries,
    organizations,
    reconciliation,
    reports,
    schedules,
    shareholder_loans,
    tax,
    templates,
)

api_router = APIRouter(prefix="/api")

api_router.include_router(organizations.router)
api_router.include_router(accounts.router)
api_router.include_router(journal_entries.router)
api_router.include_router(assets.router)
api_router.include_router(shareholder_loans.router)
api_router.include_router(tax.router)
api_router.include_router(documents.router)
api_router.include_router(schedules.router)
api_router.include_router(integrations.router)
api_router.include_router(reconciliation.router)
api_router.include_router(templates.router)
api_router.include_router(reports.router)
