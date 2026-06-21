from __future__ import annotations

from collections import defaultdict
import csv
from io import StringIO
from typing import Dict, Iterable, List, Tuple

from .storage import Payment, cents_to_decimal


def render_text_report(payments: Iterable[Payment]) -> str:
    payment_list = list(payments)
    lines = [
        "Payment Report",
        "=" * 14,
        f"Payments: {len(payment_list)}",
        "",
        "Totals by currency:",
    ]

    currency_totals = totals_by_currency(payment_list)
    if currency_totals:
        for currency, cents in sorted(currency_totals.items()):
            lines.append(f"  {currency}: {cents_to_decimal(cents)}")
    else:
        lines.append("  No payments found.")

    lines.extend(["", "Totals by method:"])
    method_totals = totals_by_method(payment_list)
    if method_totals:
        for (currency, method), cents in sorted(method_totals.items()):
            lines.append(f"  {currency} {method}: {cents_to_decimal(cents)}")
    else:
        lines.append("  No payments found.")

    lines.extend(["", "Payments:", _text_table(payment_list)])
    return "\n".join(lines).rstrip() + "\n"


def render_csv_report(payments: Iterable[Payment]) -> str:
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "id",
            "receipt_number",
            "payment_date",
            "customer_name",
            "customer_email",
            "currency",
            "amount",
            "payment_method",
            "reference",
            "description",
            "notes",
            "created_at",
        ]
    )
    for payment in payments:
        writer.writerow(
            [
                payment.id,
                payment.receipt_number,
                payment.payment_date.isoformat(),
                payment.customer_name,
                payment.customer_email or "",
                payment.currency,
                str(payment.amount),
                payment.payment_method,
                payment.reference or "",
                payment.description or "",
                payment.notes or "",
                payment.created_at.isoformat(),
            ]
        )
    return output.getvalue()


def totals_by_currency(payments: Iterable[Payment]) -> Dict[str, int]:
    totals: Dict[str, int] = defaultdict(int)
    for payment in payments:
        totals[payment.currency] += payment.amount_cents
    return dict(totals)


def totals_by_method(payments: Iterable[Payment]) -> Dict[Tuple[str, str], int]:
    totals: Dict[Tuple[str, str], int] = defaultdict(int)
    for payment in payments:
        totals[(payment.currency, payment.payment_method)] += payment.amount_cents
    return dict(totals)


def _text_table(payments: List[Payment]) -> str:
    if not payments:
        return "  No payments found."

    headers = ["ID", "Receipt", "Date", "Customer", "Amount", "Method"]
    rows = [
        [
            str(payment.id),
            payment.receipt_number,
            payment.payment_date.isoformat(),
            payment.customer_name,
            f"{payment.currency} {payment.amount}",
            payment.payment_method,
        ]
        for payment in payments
    ]
    widths = [
        max(len(row[index]) for row in [headers, *rows])
        for index in range(len(headers))
    ]

    def format_row(row: List[str]) -> str:
        return "  " + "  ".join(
            value.ljust(widths[index]) for index, value in enumerate(row)
        )

    separator = "  " + "  ".join("-" * width for width in widths)
    rendered = [format_row(headers), separator]
    rendered.extend(format_row(row) for row in rows)
    return "\n".join(rendered)

