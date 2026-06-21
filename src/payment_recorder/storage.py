from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
import sqlite3
from typing import Iterable, List, Optional, Union


SCHEMA = """
CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    receipt_number TEXT UNIQUE,
    customer_name TEXT NOT NULL,
    customer_email TEXT,
    amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
    currency TEXT NOT NULL,
    payment_method TEXT NOT NULL,
    payment_date TEXT NOT NULL,
    reference TEXT,
    description TEXT,
    notes TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_payments_payment_date
ON payments(payment_date);

CREATE INDEX IF NOT EXISTS idx_payments_receipt_number
ON payments(receipt_number);
"""


@dataclass(frozen=True)
class PaymentInput:
    customer_name: str
    amount: Decimal
    payment_method: str
    payment_date: date
    currency: str = "USD"
    customer_email: Optional[str] = None
    reference: Optional[str] = None
    description: Optional[str] = None
    notes: Optional[str] = None


@dataclass(frozen=True)
class Payment:
    id: int
    receipt_number: str
    customer_name: str
    customer_email: Optional[str]
    amount_cents: int
    currency: str
    payment_method: str
    payment_date: date
    reference: Optional[str]
    description: Optional[str]
    notes: Optional[str]
    created_at: datetime

    @property
    def amount(self) -> Decimal:
        return cents_to_decimal(self.amount_cents)


class PaymentStore:
    """SQLite-backed payment store."""

    def __init__(self, db_path: Union[str, Path]):
        self.db_path = Path(db_path)

    def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(SCHEMA)

    def add_payment(self, payment: PaymentInput) -> Payment:
        self.initialize()
        cleaned = validate_payment_input(payment)
        created_at = datetime.now(timezone.utc).replace(microsecond=0)

        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO payments (
                    customer_name,
                    customer_email,
                    amount_cents,
                    currency,
                    payment_method,
                    payment_date,
                    reference,
                    description,
                    notes,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    cleaned.customer_name,
                    normalize_optional_text(cleaned.customer_email),
                    decimal_to_cents(cleaned.amount),
                    cleaned.currency.upper(),
                    cleaned.payment_method,
                    cleaned.payment_date.isoformat(),
                    normalize_optional_text(cleaned.reference),
                    normalize_optional_text(cleaned.description),
                    normalize_optional_text(cleaned.notes),
                    created_at.isoformat(),
                ),
            )
            payment_id = int(cursor.lastrowid)
            receipt_number = build_receipt_number(payment_id, cleaned.payment_date)
            connection.execute(
                "UPDATE payments SET receipt_number = ? WHERE id = ?",
                (receipt_number, payment_id),
            )
            row = connection.execute(
                "SELECT * FROM payments WHERE id = ?",
                (payment_id,),
            ).fetchone()

        return row_to_payment(row)

    def get_payment(self, payment_identifier: Union[int, str]) -> Payment:
        self.initialize()
        if isinstance(payment_identifier, int):
            where_clause = "id = ?"
            value: Union[int, str] = payment_identifier
        else:
            value = payment_identifier.strip()
            where_clause = "id = ?" if value.isdigit() else "receipt_number = ?"

        with self._connect() as connection:
            row = connection.execute(
                f"SELECT * FROM payments WHERE {where_clause}",
                (value,),
            ).fetchone()
        if row is None:
            raise LookupError(f"Payment not found: {payment_identifier}")
        return row_to_payment(row)

    def list_payments(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[Payment]:
        self.initialize()
        clauses = []
        values: List[str] = []
        if start_date is not None:
            clauses.append("payment_date >= ?")
            values.append(start_date.isoformat())
        if end_date is not None:
            clauses.append("payment_date <= ?")
            values.append(end_date.isoformat())

        query = "SELECT * FROM payments"
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY payment_date DESC, id DESC"

        with self._connect() as connection:
            rows = connection.execute(query, values).fetchall()
        return [row_to_payment(row) for row in rows]

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.db_path))
        connection.row_factory = sqlite3.Row
        return connection


def build_receipt_number(payment_id: int, payment_date: date) -> str:
    return f"RCPT-{payment_date.strftime('%Y%m')}-{payment_id:06d}"


def validate_payment_input(payment: PaymentInput) -> PaymentInput:
    customer_name = payment.customer_name.strip()
    payment_method = payment.payment_method.strip()
    currency = payment.currency.strip().upper()

    if not customer_name:
        raise ValueError("Customer name is required.")
    if not payment_method:
        raise ValueError("Payment method is required.")
    if not currency:
        raise ValueError("Currency is required.")
    if decimal_to_cents(payment.amount) <= 0:
        raise ValueError("Amount must be greater than zero.")

    return PaymentInput(
        customer_name=customer_name,
        customer_email=normalize_optional_text(payment.customer_email),
        amount=normalize_decimal(payment.amount),
        currency=currency,
        payment_method=payment_method,
        payment_date=payment.payment_date,
        reference=normalize_optional_text(payment.reference),
        description=normalize_optional_text(payment.description),
        notes=normalize_optional_text(payment.notes),
    )


def normalize_optional_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def normalize_decimal(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def decimal_to_cents(value: Union[str, Decimal]) -> int:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Invalid amount: {value}") from exc
    normalized = normalize_decimal(amount)
    return int(normalized * 100)


def cents_to_decimal(cents: int) -> Decimal:
    return (Decimal(cents) / Decimal(100)).quantize(Decimal("0.01"))


def row_to_payment(row: sqlite3.Row) -> Payment:
    receipt_number = row["receipt_number"]
    if receipt_number is None:
        raise ValueError("Stored payment is missing a receipt number.")
    return Payment(
        id=int(row["id"]),
        receipt_number=receipt_number,
        customer_name=row["customer_name"],
        customer_email=row["customer_email"],
        amount_cents=int(row["amount_cents"]),
        currency=row["currency"],
        payment_method=row["payment_method"],
        payment_date=date.fromisoformat(row["payment_date"]),
        reference=row["reference"],
        description=row["description"],
        notes=row["notes"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def total_cents(payments: Iterable[Payment]) -> int:
    return sum(payment.amount_cents for payment in payments)

