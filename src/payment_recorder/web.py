from __future__ import annotations

from datetime import date
from decimal import Decimal
from html import escape
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlencode, urlparse

from .receipts import render_html_receipt
from .reports import render_csv_report, totals_by_currency, totals_by_method
from .storage import Payment, PaymentInput, PaymentStore, cents_to_decimal


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000


class PaymentHTTPRequestHandler(BaseHTTPRequestHandler):
    store: PaymentStore

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)

        try:
            if parsed.path == "/":
                self._send_html(render_dashboard(self.store, query))
            elif parsed.path == "/receipt":
                self._send_html(render_receipt_page(self.store, query))
            elif parsed.path == "/reports.csv":
                self._send_csv(render_csv_export(self.store, query), "payment-report.csv")
            elif parsed.path == "/health":
                self._send_text("ok\n")
            else:
                self._send_error(HTTPStatus.NOT_FOUND, "Page not found.")
        except (LookupError, ValueError) as exc:
            self._send_html(render_error_page(str(exc)), HTTPStatus.BAD_REQUEST)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/payments":
            self._send_error(HTTPStatus.NOT_FOUND, "Page not found.")
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(content_length).decode("utf-8")
        form = parse_qs(body)

        try:
            payment = self.store.add_payment(
                PaymentInput(
                    customer_name=field(form, "customer_name"),
                    customer_email=optional_field(form, "customer_email"),
                    amount=Decimal(field(form, "amount")),
                    currency=field(form, "currency", "USD"),
                    payment_method=field(form, "payment_method"),
                    payment_date=parse_date_field(field(form, "payment_date")),
                    reference=optional_field(form, "reference"),
                    description=optional_field(form, "description"),
                    notes=optional_field(form, "notes"),
                )
            )
            location = "/?" + urlencode({"created": payment.receipt_number})
            self.send_response(HTTPStatus.SEE_OTHER)
            self.send_header("Location", location)
            self.end_headers()
        except (ValueError, LookupError) as exc:
            self._send_html(render_dashboard(self.store, form, str(exc)), HTTPStatus.BAD_REQUEST)

    def log_message(self, format: str, *args: object) -> None:
        print(f"{self.address_string()} - {format % args}")

    def _send_html(
        self,
        content: str,
        status: HTTPStatus = HTTPStatus.OK,
    ) -> None:
        encoded = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _send_text(
        self,
        content: str,
        status: HTTPStatus = HTTPStatus.OK,
    ) -> None:
        encoded = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _send_csv(self, content: str, filename: str) -> None:
        encoded = content.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header(
            "Content-Disposition",
            f'attachment; filename="{filename}"',
        )
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _send_error(self, status: HTTPStatus, message: str) -> None:
        self._send_html(render_error_page(message), status)


def create_server(
    db_path: Path,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
) -> ThreadingHTTPServer:
    store = PaymentStore(db_path)
    store.initialize()

    class Handler(PaymentHTTPRequestHandler):
        pass

    Handler.store = store
    return ThreadingHTTPServer((host, port), Handler)


def run_server(db_path: Path, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
    server = create_server(db_path, host, port)
    actual_host, actual_port = server.server_address[:2]
    print(f"Serving payment recorder at http://{actual_host}:{actual_port}")
    print(f"Using database: {db_path}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server.")
    finally:
        server.server_close()


def render_dashboard(
    store: PaymentStore,
    query: Dict[str, List[str]],
    error: Optional[str] = None,
) -> str:
    start_date, end_date, filter_error = date_filters(query)
    payments = store.list_payments(start_date=start_date, end_date=end_date)
    error_message = error or filter_error
    created = optional_field(query, "created")

    return page(
        title="Payment Recorder",
        body=f"""
<header class="app-header">
  <div>
    <p class="eyebrow">Payment Recorder</p>
    <h1>Payments</h1>
  </div>
  <div class="header-actions">
    <a class="button secondary" href="/reports.csv{query_string(query, keep_filters=True)}">Download CSV</a>
  </div>
</header>
{render_alerts(error_message, created)}
<main class="layout">
  <section class="entry-panel" aria-labelledby="add-payment-heading">
    <h2 id="add-payment-heading">Add Payment</h2>
    {render_payment_form(query)}
  </section>
  <section class="report-panel" aria-labelledby="report-heading">
    <div class="section-title">
      <h2 id="report-heading">Report</h2>
      {render_filter_form(query)}
    </div>
    {render_summary(payments)}
    {render_payment_table(payments)}
  </section>
</main>
""",
    )


def render_payment_form(values: Dict[str, List[str]]) -> str:
    return f"""
<form class="payment-form" method="post" action="/payments">
  <label>
    <span>Customer</span>
    <input name="customer_name" value="{attr(field(values, "customer_name"))}" required>
  </label>
  <label>
    <span>Email</span>
    <input name="customer_email" type="email" value="{attr(field(values, "customer_email"))}">
  </label>
  <div class="form-row">
    <label>
      <span>Amount</span>
      <input name="amount" inputmode="decimal" value="{attr(field(values, "amount"))}" required>
    </label>
    <label>
      <span>Currency</span>
      <input name="currency" maxlength="3" value="{attr(field(values, "currency", "USD"))}" required>
    </label>
  </div>
  <div class="form-row">
    <label>
      <span>Method</span>
      <select name="payment_method" required>
        {option("cash", field(values, "payment_method"), "Cash")}
        {option("card", field(values, "payment_method"), "Card")}
        {option("upi", field(values, "payment_method"), "UPI")}
        {option("bank transfer", field(values, "payment_method"), "Bank Transfer")}
        {option("check", field(values, "payment_method"), "Check")}
      </select>
    </label>
    <label>
      <span>Date</span>
      <input name="payment_date" type="date" value="{attr(field(values, "payment_date", date.today().isoformat()))}" required>
    </label>
  </div>
  <label>
    <span>Reference</span>
    <input name="reference" value="{attr(field(values, "reference"))}">
  </label>
  <label>
    <span>Description</span>
    <input name="description" value="{attr(field(values, "description"))}">
  </label>
  <label>
    <span>Notes</span>
    <textarea name="notes" rows="3">{escape(field(values, "notes"))}</textarea>
  </label>
  <button class="button primary" type="submit">Save Payment</button>
</form>
"""


def render_filter_form(query: Dict[str, List[str]]) -> str:
    return f"""
<form class="filter-form" method="get" action="/">
  <label>
    <span>Start</span>
    <input name="start" type="date" value="{attr(field(query, "start"))}">
  </label>
  <label>
    <span>End</span>
    <input name="end" type="date" value="{attr(field(query, "end"))}">
  </label>
  <button class="button secondary" type="submit">Apply</button>
  <a class="button ghost" href="/">Clear</a>
</form>
"""


def render_summary(payments: List[Payment]) -> str:
    currency_cells = []
    for currency, cents in sorted(totals_by_currency(payments).items()):
        currency_cells.append(
            f"""
<div class="metric">
  <span>{escape(currency)}</span>
  <strong>{escape(str(cents_to_decimal(cents)))}</strong>
</div>
"""
        )
    if not currency_cells:
        currency_cells.append('<div class="metric"><span>Total</span><strong>0.00</strong></div>')

    method_rows = []
    for (currency, method), cents in sorted(totals_by_method(payments).items()):
        method_rows.append(
            f"<tr><td>{escape(method.title())}</td><td>{escape(currency)}</td><td>{escape(str(cents_to_decimal(cents)))}</td></tr>"
        )
    if not method_rows:
        method_rows.append('<tr><td colspan="3">No payments found.</td></tr>')

    return f"""
<div class="summary-grid">
  <div class="metric">
    <span>Payments</span>
    <strong>{len(payments)}</strong>
  </div>
  {"".join(currency_cells)}
</div>
<table class="compact-table" aria-label="Totals by payment method">
  <thead><tr><th>Method</th><th>Currency</th><th>Total</th></tr></thead>
  <tbody>{"".join(method_rows)}</tbody>
</table>
"""


def render_payment_table(payments: List[Payment]) -> str:
    if not payments:
        rows = '<tr><td colspan="8">No payments found.</td></tr>'
    else:
        rows = "\n".join(
            f"""
<tr>
  <td>{payment.id}</td>
  <td><a href="/receipt?payment={url(payment.receipt_number)}">{escape(payment.receipt_number)}</a></td>
  <td>{escape(payment.payment_date.isoformat())}</td>
  <td>{escape(payment.customer_name)}</td>
  <td>{escape(payment.currency)} {escape(str(payment.amount))}</td>
  <td>{escape(payment.payment_method.title())}</td>
  <td>{escape(payment.reference or "")}</td>
  <td><a class="table-action" href="/receipt?payment={url(payment.receipt_number)}">Receipt</a></td>
</tr>
"""
            for payment in payments
        )

    return f"""
<div class="table-wrap">
  <table class="payments-table">
    <thead>
      <tr>
        <th>ID</th>
        <th>Receipt</th>
        <th>Date</th>
        <th>Customer</th>
        <th>Amount</th>
        <th>Method</th>
        <th>Reference</th>
        <th></th>
      </tr>
    </thead>
    <tbody>{rows}</tbody>
  </table>
</div>
"""


def render_receipt_page(store: PaymentStore, query: Dict[str, List[str]]) -> str:
    payment_identifier = field(query, "payment")
    if not payment_identifier:
        raise ValueError("Receipt requires a payment id or receipt number.")
    receipt = render_html_receipt(store.get_payment(payment_identifier))
    return receipt.replace(
        "<body>",
        '<body><p><a href="/" style="color:#2563eb;text-decoration:none;">Back to payments</a></p>',
        1,
    )


def render_csv_export(store: PaymentStore, query: Dict[str, List[str]]) -> str:
    start_date, end_date, error = date_filters(query)
    if error:
        raise ValueError(error)
    return render_csv_report(store.list_payments(start_date=start_date, end_date=end_date))


def render_alerts(error: Optional[str], created: Optional[str]) -> str:
    alerts = []
    if error:
        alerts.append(f'<div class="alert error">{escape(error)}</div>')
    if created:
        receipt_href = "/receipt?" + urlencode({"payment": created})
        alerts.append(
            f'<div class="alert success">Recorded {escape(created)}. <a href="{receipt_href}">Open receipt</a></div>'
        )
    return "\n".join(alerts)


def page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style>{CSS}</style>
</head>
<body>
  {body}
</body>
</html>
"""


def render_error_page(message: str) -> str:
    return page(
        "Payment Recorder Error",
        f"""
<main class="error-page">
  <h1>Payment Recorder</h1>
  <div class="alert error">{escape(message)}</div>
  <a class="button secondary" href="/">Back to payments</a>
</main>
""",
    )


def date_filters(query: Dict[str, List[str]]) -> Tuple[Optional[date], Optional[date], Optional[str]]:
    try:
        start_date = parse_optional_date(optional_field(query, "start"))
        end_date = parse_optional_date(optional_field(query, "end"))
    except ValueError as exc:
        return None, None, str(exc)
    if start_date and end_date and start_date > end_date:
        return None, None, "Start date must be before or equal to end date."
    return start_date, end_date, None


def parse_date_field(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"Invalid date '{value}'. Use YYYY-MM-DD.") from exc


def parse_optional_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    return parse_date_field(value)


def field(values: Dict[str, List[str]], name: str, default: str = "") -> str:
    return values.get(name, [default])[0].strip()


def optional_field(values: Dict[str, List[str]], name: str) -> Optional[str]:
    value = field(values, name)
    return value or None


def option(value: str, selected: str, label: str) -> str:
    selected_attr = " selected" if value == selected else ""
    return f'<option value="{attr(value)}"{selected_attr}>{escape(label)}</option>'


def query_string(query: Dict[str, List[str]], keep_filters: bool = False) -> str:
    allowed = {"start", "end"} if keep_filters else set(query.keys())
    filtered = {
        key: field(query, key)
        for key in allowed
        if field(query, key)
    }
    if not filtered:
        return ""
    return "?" + urlencode(filtered)


def attr(value: str) -> str:
    return escape(value, quote=True)


def url(value: str) -> str:
    return urlencode({"": value})[1:]


CSS = """
:root {
  --background: #f7f9fc;
  --surface: #ffffff;
  --border: #d8e0ea;
  --text: #182230;
  --muted: #667085;
  --accent: #2563eb;
  --accent-dark: #1d4ed8;
  --success-bg: #eaf7ef;
  --success-text: #166534;
  --error-bg: #fff1f2;
  --error-text: #b42318;
}

* {
  box-sizing: border-box;
}

body {
  background: var(--background);
  color: var(--text);
  font-family: Arial, Helvetica, sans-serif;
  line-height: 1.45;
  margin: 0;
}

a {
  color: var(--accent);
}

.app-header {
  align-items: center;
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  display: flex;
  gap: 16px;
  justify-content: space-between;
  padding: 18px 28px;
}

.eyebrow {
  color: var(--muted);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0;
  margin: 0 0 3px;
  text-transform: uppercase;
}

h1, h2 {
  margin: 0;
}

h1 {
  font-size: 28px;
}

h2 {
  font-size: 18px;
}

.layout {
  display: grid;
  gap: 20px;
  grid-template-columns: minmax(280px, 420px) minmax(0, 1fr);
  padding: 20px 28px 32px;
}

.entry-panel,
.report-panel {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 18px;
}

.payment-form {
  display: grid;
  gap: 12px;
  margin-top: 16px;
}

.form-row {
  display: grid;
  gap: 12px;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
}

label {
  display: grid;
  gap: 6px;
}

label span {
  color: var(--muted);
  font-size: 13px;
  font-weight: 700;
}

input,
select,
textarea {
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  color: var(--text);
  font: inherit;
  min-height: 38px;
  padding: 8px 10px;
  width: 100%;
}

textarea {
  resize: vertical;
}

.button {
  align-items: center;
  border: 1px solid transparent;
  border-radius: 6px;
  cursor: pointer;
  display: inline-flex;
  font: inherit;
  font-weight: 700;
  justify-content: center;
  min-height: 38px;
  padding: 8px 13px;
  text-decoration: none;
  white-space: nowrap;
}

.primary {
  background: var(--accent);
  color: #ffffff;
}

.primary:hover {
  background: var(--accent-dark);
}

.secondary {
  background: #ffffff;
  border-color: #b9c5d4;
  color: var(--text);
}

.ghost {
  background: transparent;
  color: var(--muted);
}

.section-title {
  align-items: end;
  display: flex;
  gap: 14px;
  justify-content: space-between;
  margin-bottom: 16px;
}

.filter-form {
  align-items: end;
  display: grid;
  gap: 8px;
  grid-template-columns: 150px 150px auto auto;
}

.summary-grid {
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  margin-bottom: 14px;
}

.metric {
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 12px;
}

.metric span {
  color: var(--muted);
  display: block;
  font-size: 13px;
  font-weight: 700;
}

.metric strong {
  display: block;
  font-size: 24px;
  margin-top: 3px;
}

table {
  border-collapse: collapse;
  width: 100%;
}

th,
td {
  border-bottom: 1px solid #e5eaf1;
  padding: 10px 8px;
  text-align: left;
  vertical-align: top;
}

th {
  color: var(--muted);
  font-size: 13px;
}

.compact-table {
  margin-bottom: 18px;
}

.table-wrap {
  overflow-x: auto;
}

.payments-table {
  min-width: 760px;
}

.table-action {
  font-weight: 700;
  text-decoration: none;
}

.alert {
  border-radius: 8px;
  margin: 14px 28px 0;
  padding: 12px 14px;
}

.success {
  background: var(--success-bg);
  color: var(--success-text);
}

.error {
  background: var(--error-bg);
  color: var(--error-text);
}

.error-page {
  margin: 40px auto;
  max-width: 720px;
}

@media (max-width: 920px) {
  .app-header,
  .section-title {
    align-items: stretch;
    flex-direction: column;
  }

  .layout {
    grid-template-columns: 1fr;
    padding: 16px;
  }

  .filter-form {
    grid-template-columns: 1fr 1fr;
  }

  .alert {
    margin-left: 16px;
    margin-right: 16px;
  }
}

@media (max-width: 560px) {
  .app-header {
    padding: 16px;
  }

  .form-row,
  .filter-form {
    grid-template-columns: 1fr;
  }

  .button {
    width: 100%;
  }
}
"""

