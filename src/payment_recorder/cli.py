from __future__ import annotations

import argparse
from datetime import date
from decimal import Decimal
from pathlib import Path
import sys
from typing import Iterable, Optional

from .receipts import render_html_receipt, render_text_receipt
from .reports import render_csv_report, render_text_report
from .storage import PaymentInput, PaymentStore


DEFAULT_DB_PATH = "payments.db"


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    store = PaymentStore(args.db)

    try:
        if args.command == "init":
            store.initialize()
            print(f"Initialized payment database at {args.db}")
        elif args.command == "add":
            payment = store.add_payment(
                PaymentInput(
                    customer_name=args.customer,
                    customer_email=args.email,
                    amount=Decimal(args.amount),
                    currency=args.currency,
                    payment_method=args.method,
                    payment_date=parse_date(args.date),
                    reference=args.reference,
                    description=args.description,
                    notes=args.notes,
                )
            )
            print(f"Recorded payment {payment.id} ({payment.receipt_number})")
        elif args.command == "list":
            payments = store.list_payments(
                start_date=parse_optional_date(args.start),
                end_date=parse_optional_date(args.end),
            )
            print(render_text_report(payments), end="")
        elif args.command == "receipt":
            payment = store.get_payment(args.payment)
            if args.format == "html":
                content = render_html_receipt(payment)
                default_filename = f"{payment.receipt_number}.html"
            else:
                content = render_text_receipt(payment)
                default_filename = f"{payment.receipt_number}.txt"
            write_or_print(content, args.output, default_filename)
        elif args.command == "report":
            payments = store.list_payments(
                start_date=parse_optional_date(args.start),
                end_date=parse_optional_date(args.end),
            )
            if args.format == "csv":
                content = render_csv_report(payments)
                default_filename = "payment-report.csv"
            else:
                content = render_text_report(payments)
                default_filename = "payment-report.txt"
            write_or_print(content, args.output, default_filename)
        else:
            parser.print_help()
            return 2
    except (LookupError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="payment-recorder",
        description="Record payments in SQLite and generate receipts and reports.",
    )
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument(
        "--db",
        default=DEFAULT_DB_PATH,
        help=f"SQLite database path. Defaults to {DEFAULT_DB_PATH}.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser(
        "init",
        parents=[parent],
        help="Create the payments database.",
    )

    add_parser = subparsers.add_parser(
        "add",
        parents=[parent],
        help="Record a new payment.",
    )
    add_parser.add_argument("--customer", required=True, help="Customer name.")
    add_parser.add_argument("--email", help="Customer email address.")
    add_parser.add_argument("--amount", required=True, help="Payment amount.")
    add_parser.add_argument("--currency", default="USD", help="ISO currency code.")
    add_parser.add_argument("--method", required=True, help="Payment method.")
    add_parser.add_argument(
        "--date",
        default=date.today().isoformat(),
        help="Payment date in YYYY-MM-DD format. Defaults to today.",
    )
    add_parser.add_argument("--reference", help="External invoice or transaction id.")
    add_parser.add_argument("--description", help="Payment description.")
    add_parser.add_argument("--notes", help="Internal notes.")

    list_parser = subparsers.add_parser(
        "list",
        parents=[parent],
        help="List payments with totals.",
    )
    add_date_range_arguments(list_parser)

    receipt_parser = subparsers.add_parser(
        "receipt",
        parents=[parent],
        help="Generate a receipt for a payment id or receipt number.",
    )
    receipt_parser.add_argument("payment", help="Payment id or receipt number.")
    receipt_parser.add_argument(
        "--format",
        choices=["text", "html"],
        default="text",
        help="Receipt output format.",
    )
    receipt_parser.add_argument(
        "--output",
        help="Output file or directory. Prints to stdout when omitted.",
    )

    report_parser = subparsers.add_parser(
        "report",
        parents=[parent],
        help="Generate a report for all or filtered payments.",
    )
    add_date_range_arguments(report_parser)
    report_parser.add_argument(
        "--format",
        choices=["text", "csv"],
        default="text",
        help="Report output format.",
    )
    report_parser.add_argument(
        "--output",
        help="Output file or directory. Prints to stdout when omitted.",
    )

    return parser


def add_date_range_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--start", help="Start date in YYYY-MM-DD format.")
    parser.add_argument("--end", help="End date in YYYY-MM-DD format.")


def parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"Invalid date '{value}'. Use YYYY-MM-DD.") from exc


def parse_optional_date(value: Optional[str]) -> Optional[date]:
    if value is None:
        return None
    return parse_date(value)


def write_or_print(content: str, output: Optional[str], default_filename: str) -> None:
    if output is None:
        print(content, end="")
        return

    path = Path(output)
    if output.endswith("/") or path.is_dir():
        path.mkdir(parents=True, exist_ok=True)
        path = path / default_filename
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"Wrote {path}")

