from fastapi import APIRouter

from app.api.routers import clarifications, core_accounts, core_journal_entries, ledger, transactions, users

api_router = APIRouter(prefix="/api")

api_router.include_router(users.router)
api_router.include_router(core_accounts.router)
api_router.include_router(transactions.router)
api_router.include_router(core_journal_entries.router)
api_router.include_router(ledger.router)
api_router.include_router(clarifications.router)
