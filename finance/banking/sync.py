"""Idempotent bank transaction and balance synchronisation."""
from decimal import Decimal, InvalidOperation
from django.db import transaction as db_transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from finance.models import BankConnection, BankTransaction
from .mono import MonoClient, MonoAPIError


def _decimal(value, label):
    try:
        return Decimal(str(value)).copy_abs()
    except (InvalidOperation, TypeError, ValueError):
        raise MonoAPIError(f"Mono returned an invalid {label} value.")


def _date(value):
    if not value:
        raise MonoAPIError("Mono returned a transaction without a date.")
    dt = parse_datetime(str(value))
    if dt is None:
        raise MonoAPIError("Mono returned an unrecognised transaction date.")
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def sync_mono_connection(connection, client=None):
    """Fetch balance and all available transaction pages for one connection."""
    if connection.provider != BankConnection.Provider.MONO:
        raise MonoAPIError("This sync implementation supports Mono connections only.")
    if not connection.provider_account_id:
        raise MonoAPIError("This connection has no provider account ID yet.")
    client = client or MonoClient()
    details = client.account_details(connection.provider_account_id).get("data", {})
    account = details.get("account", details) if isinstance(details, dict) else {}
    meta = details.get("meta", {}) if isinstance(details, dict) else {}
    status = str(meta.get("data_status", "AVAILABLE")).upper()
    if status in {"FAILED", "UNAVAILABLE"}:
        raise MonoAPIError(f"Bank data is currently {status.lower()} for this account.")

    balance_payload = client.balance(connection.provider_account_id).get("data", {})
    raw_balance = balance_payload.get("balance", account.get("balance"))
    now = timezone.now()
    if raw_balance is not None:
        connection.current_balance = Decimal(str(raw_balance))
        connection.balance_updated_at = now
    connection.account_name = (account.get("name") or account.get("account_name") or connection.account_name)[:160]
    raw_number = account.get("account_number") or account.get("accountNumber") or ""
    if raw_number:
        digits = str(raw_number)
        connection.account_number_masked = ("*" * max(0, len(digits) - 4) + digits[-4:])[:30]
    institution = account.get("institution") or {}
    connection.bank_name = (institution.get("name") or connection.bank_name)[:100]
    connection.currency = (account.get("currency") or "NGN")[:3]

    imported = 0
    page = 1
    while page <= 100:
        payload = client.transactions(connection.provider_account_id, page=page)
        data = payload.get("data", [])
        if isinstance(data, dict):
            rows = data.get("transactions", [])
            meta_page = payload.get("meta", {}) or data.get("meta", {})
            next_page = meta_page.get("next")
            total_pages = meta_page.get("pages")
        else:
            rows = data if isinstance(data, list) else []
            meta_page = payload.get("meta", {})
            next_page = meta_page.get("next")
            total_pages = meta_page.get("pages")
        for row in rows:
            provider_id = str(row.get("id") or row.get("_id") or row.get("transaction_id") or "")[:180]
            if not provider_id:
                continue
            raw_type = str(row.get("type") or row.get("transaction_type") or "").lower()
            if raw_type in {"credit", "deposit", "inflow"}:
                direction = BankTransaction.Direction.CREDIT
            elif raw_type in {"debit", "withdrawal", "outflow"}:
                direction = BankTransaction.Direction.DEBIT
            else:
                continue
            # Mono returns transaction amounts in the currency's smallest unit
            # (kobo for NGN). Convert to the major unit before storing in DepotFlow.
            currency = str(row.get("currency") or connection.currency or "NGN")[:3].upper()
            amount = _decimal(row.get("amount"), "transaction amount") / Decimal("100")
            raw_balance_after = row.get("balance")
            if raw_balance_after is None:
                raw_balance_after = row.get("balance_after")
            defaults = {
                "transaction_date": _date(row.get("date") or row.get("created_at") or row.get("transaction_date")),
                "description": str(row.get("narration") or row.get("description") or "")[:2000],
                "reference": str(row.get("reference") or row.get("ref") or "")[:180],
                "direction": direction,
                "amount": amount,
                "currency": currency,
                "balance_after": (Decimal(str(raw_balance_after)) / Decimal("100")) if raw_balance_after is not None else None,
            }
            with db_transaction.atomic():
                _, created = BankTransaction.objects.get_or_create(
                    connection=connection, provider_transaction_id=provider_id, defaults=defaults
                )
                imported += int(created)
        if not rows or not next_page and (not total_pages or page >= int(total_pages)):
            break
        page += 1

    connection.status = BankConnection.Status.ACTIVE
    connection.last_synced_at = now
    connection.last_sync_error = ""
    connection.save(update_fields=["current_balance", "balance_updated_at", "account_name", "account_number_masked", "bank_name", "currency", "status", "last_synced_at", "last_sync_error", "updated_at"])
    return imported
