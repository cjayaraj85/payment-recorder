from datetime import date
from decimal import Decimal
from http.client import HTTPConnection
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from urllib.parse import urlencode


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from payment_recorder.cli import main
from payment_recorder.receipts import render_html_receipt, render_text_receipt
from payment_recorder.reports import render_csv_report, render_text_report
from payment_recorder.storage import PaymentInput, PaymentStore
from payment_recorder.web import create_server


class PaymentRecorderTests(unittest.TestCase):
    def test_add_payment_persists_payment_and_receipt_number(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = PaymentStore(Path(tmp) / "payments.db")

            payment = store.add_payment(
                PaymentInput(
                    customer_name="Ada Lovelace",
                    customer_email="ada@example.com",
                    amount=Decimal("125.50"),
                    currency="usd",
                    payment_method="card",
                    payment_date=date(2026, 6, 21),
                    reference="INV-1001",
                    description="Consulting invoice",
                )
            )

            self.assertEqual(payment.id, 1)
            self.assertEqual(payment.receipt_number, "RCPT-202606-000001")
            self.assertEqual(payment.currency, "USD")
            self.assertEqual(payment.amount, Decimal("125.50"))
            self.assertEqual(store.get_payment("RCPT-202606-000001"), payment)

    def test_rejects_invalid_payment_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = PaymentStore(Path(tmp) / "payments.db")

            with self.assertRaises(ValueError):
                store.add_payment(
                    PaymentInput(
                        customer_name=" ",
                        amount=Decimal("10.00"),
                        payment_method="cash",
                        payment_date=date(2026, 6, 21),
                    )
                )

            with self.assertRaises(ValueError):
                store.add_payment(
                    PaymentInput(
                        customer_name="Grace Hopper",
                        amount=Decimal("0.00"),
                        payment_method="cash",
                        payment_date=date(2026, 6, 21),
                    )
                )

    def test_receipts_include_payment_details(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = PaymentStore(Path(tmp) / "payments.db")
            payment = store.add_payment(
                PaymentInput(
                    customer_name="Grace Hopper",
                    amount=Decimal("42.00"),
                    payment_method="cash",
                    payment_date=date(2026, 6, 20),
                )
            )

            text = render_text_receipt(payment)
            html = render_html_receipt(payment)

            self.assertIn("Payment Receipt", text)
            self.assertIn("RCPT-202606-000001", text)
            self.assertIn("USD 42.00", text)
            self.assertIn("<h1>Payment Receipt</h1>", html)

    def test_reports_filter_and_render_totals(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = PaymentStore(Path(tmp) / "payments.db")
            store.add_payment(
                PaymentInput(
                    customer_name="Customer A",
                    amount=Decimal("10.00"),
                    payment_method="cash",
                    payment_date=date(2026, 6, 1),
                )
            )
            store.add_payment(
                PaymentInput(
                    customer_name="Customer B",
                    amount=Decimal("20.25"),
                    payment_method="card",
                    payment_date=date(2026, 7, 1),
                )
            )

            payments = store.list_payments(
                start_date=date(2026, 6, 1),
                end_date=date(2026, 6, 30),
            )
            report = render_text_report(payments)
            csv_report = render_csv_report(payments)

            self.assertEqual(len(payments), 1)
            self.assertIn("Payments: 1", report)
            self.assertIn("USD: 10.00", report)
            self.assertIn("Customer A", csv_report)
            self.assertNotIn("Customer B", csv_report)

    def test_cli_add_and_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = str(Path(tmp) / "payments.db")
            receipt_path = Path(tmp) / "receipt.txt"

            add_result = main(
                [
                    "add",
                    "--db",
                    db_path,
                    "--customer",
                    "CLI Customer",
                    "--amount",
                    "12.99",
                    "--method",
                    "upi",
                    "--date",
                    "2026-06-21",
                ]
            )
            receipt_result = main(
                [
                    "receipt",
                    "--db",
                    db_path,
                    "1",
                    "--output",
                    str(receipt_path),
                ]
            )

            self.assertEqual(add_result, 0)
            self.assertEqual(receipt_result, 0)
            self.assertIn("CLI Customer", receipt_path.read_text(encoding="utf-8"))

    def test_web_ui_adds_payment_and_serves_reports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            server = create_server(Path(tmp) / "payments.db", port=0)
            host, port = server.server_address[:2]
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()

            try:
                connection = HTTPConnection(host, port)
                connection.request("GET", "/")
                response = connection.getresponse()
                body = response.read().decode("utf-8")
                self.assertEqual(response.status, 200)
                self.assertIn("Add Payment", body)

                payload = urlencode(
                    {
                        "customer_name": "Web Customer",
                        "customer_email": "web@example.com",
                        "amount": "33.45",
                        "currency": "USD",
                        "payment_method": "card",
                        "payment_date": "2026-06-21",
                        "reference": "WEB-1",
                    }
                )
                connection.request(
                    "POST",
                    "/payments",
                    body=payload,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                response = connection.getresponse()
                response.read()
                self.assertEqual(response.status, 303)
                self.assertIn("RCPT-202606-000001", response.getheader("Location", ""))

                connection.request("GET", "/receipt?payment=RCPT-202606-000001")
                response = connection.getresponse()
                receipt = response.read().decode("utf-8")
                self.assertEqual(response.status, 200)
                self.assertIn("Web Customer", receipt)

                connection.request("GET", "/reports.csv")
                response = connection.getresponse()
                csv_body = response.read().decode("utf-8")
                self.assertEqual(response.status, 200)
                self.assertIn("Web Customer", csv_body)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
