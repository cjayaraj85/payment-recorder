# Payment Recorder

A small dependency-free Python application for recording payments in SQLite and
generating receipts and reports.

## Features

- Store payments with customer, amount, method, date, reference, description, and notes.
- Generate stable receipt numbers such as `RCPT-202606-000001`.
- Export receipts as plain text or HTML.
- Generate text summaries and CSV reports with optional date filtering.
- Uses only the Python standard library.

## Quick Start

```bash
python3 app.py init --db payments.db
```

Record a payment:

```bash
python3 app.py add \
  --db payments.db \
  --customer "Ada Lovelace" \
  --email ada@example.com \
  --amount 125.50 \
  --currency USD \
  --method card \
  --date 2026-06-21 \
  --reference INV-1001 \
  --description "Consulting invoice"
```

Generate a receipt:

```bash
python3 app.py receipt --db payments.db 1
python3 app.py receipt --db payments.db 1 --format html --output receipts/
```

Generate reports:

```bash
python3 app.py report --db payments.db
python3 app.py report --db payments.db --start 2026-06-01 --end 2026-06-30 --format csv --output reports/june.csv
```

## Development

Run the test suite:

```bash
python3 -m unittest discover -s tests
```

Run the CLI from the working tree:

```bash
python3 app.py --help
```

## Data Model

Payments are stored in a local SQLite database. The database file defaults to
`payments.db` when `--db` is not provided. Each payment row contains:

- receipt number
- customer name and optional email
- amount and currency
- payment method and date
- optional reference, description, and notes
- creation timestamp
