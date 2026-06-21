from __future__ import annotations

from html import escape

from .storage import Payment


def render_text_receipt(payment: Payment) -> str:
    lines = [
        "Payment Receipt",
        "=" * 15,
        f"Receipt: {payment.receipt_number}",
        f"Payment ID: {payment.id}",
        f"Date: {payment.payment_date.isoformat()}",
        f"Customer: {payment.customer_name}",
    ]
    if payment.customer_email:
        lines.append(f"Email: {payment.customer_email}")
    lines.extend(
        [
            f"Amount: {payment.currency} {payment.amount}",
            f"Method: {payment.payment_method}",
        ]
    )
    if payment.reference:
        lines.append(f"Reference: {payment.reference}")
    if payment.description:
        lines.append(f"Description: {payment.description}")
    if payment.notes:
        lines.append(f"Notes: {payment.notes}")
    lines.append(f"Recorded at: {payment.created_at.isoformat()}")
    return "\n".join(lines) + "\n"


def render_html_receipt(payment: Payment) -> str:
    optional_rows = []
    if payment.customer_email:
        optional_rows.append(("Email", payment.customer_email))
    if payment.reference:
        optional_rows.append(("Reference", payment.reference))
    if payment.description:
        optional_rows.append(("Description", payment.description))
    if payment.notes:
        optional_rows.append(("Notes", payment.notes))

    rows = [
        ("Receipt", payment.receipt_number),
        ("Payment ID", str(payment.id)),
        ("Date", payment.payment_date.isoformat()),
        ("Customer", payment.customer_name),
        *optional_rows,
        ("Amount", f"{payment.currency} {payment.amount}"),
        ("Method", payment.payment_method),
        ("Recorded at", payment.created_at.isoformat()),
    ]

    table_rows = "\n".join(
        f"<tr><th>{escape(label)}</th><td>{escape(value)}</td></tr>"
        for label, value in rows
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Receipt {escape(payment.receipt_number)}</title>
  <style>
    body {{
      color: #1f2933;
      font-family: Arial, sans-serif;
      line-height: 1.5;
      margin: 40px;
      max-width: 760px;
    }}
    h1 {{
      border-bottom: 2px solid #d9e2ec;
      padding-bottom: 12px;
    }}
    table {{
      border-collapse: collapse;
      width: 100%;
    }}
    th, td {{
      border-bottom: 1px solid #e4e7eb;
      padding: 10px 0;
      text-align: left;
      vertical-align: top;
    }}
    th {{
      color: #52606d;
      width: 180px;
    }}
  </style>
</head>
<body>
  <h1>Payment Receipt</h1>
  <table>
    {table_rows}
  </table>
</body>
</html>
"""

