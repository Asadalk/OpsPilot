"""Small retry rules shared by the agent's external dependency calls."""

from __future__ import annotations

import asyncio

import psycopg

RETRY_BACKOFF_SECONDS = 0.1
TRANSIENT_HTTP_STATUSES = {408, 429, 500, 502, 503, 504}


def is_transient_error(error: BaseException) -> bool:
    current: BaseException | None = error
    while current is not None:
        if isinstance(current, (TimeoutError, ConnectionError, psycopg.OperationalError,
                                psycopg.InterfaceError, psycopg.errors.DeadlockDetected,
                                psycopg.errors.SerializationFailure, psycopg.errors.QueryCanceled)):
            return True
        if (getattr(current, "status_code", None) in TRANSIENT_HTTP_STATUSES
                or getattr(current, "code", None) in TRANSIENT_HTTP_STATUSES):
            return True
        current = current.__cause__ or current.__context__
    return False


def error_category(error: BaseException, *, operation: str) -> str:
    chain: list[BaseException] = []
    current: BaseException | None = error
    while current is not None:
        chain.append(current)
        current = current.__cause__ or current.__context__
    if any(isinstance(item, TimeoutError) for item in chain):
        return f"{operation}_timeout"
    if any(isinstance(item, (psycopg.OperationalError, psycopg.InterfaceError,
                             psycopg.errors.DeadlockDetected, psycopg.errors.SerializationFailure,
                             psycopg.errors.QueryCanceled))
           for item in chain):
        return "temporary_database_error"
    return f"{operation}_failure"


async def backoff(attempt: int) -> None:
    await asyncio.sleep(RETRY_BACKOFF_SECONDS * attempt)
