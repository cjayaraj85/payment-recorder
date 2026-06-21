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

## Web UI

Run the local HTTP server:

```bash
python3 app.py serve --db payments.db --host 127.0.0.1 --port 8000
```

Then open:

```text
http://127.0.0.1:8000
```

The browser UI supports adding payments, opening HTML receipts, filtering the
payments report by date, and downloading a CSV report.

## Development

Run the test suite:

```bash
python3 -m unittest discover -s tests
```

Run the CLI from the working tree:

```bash
python3 app.py --help
```

## Documentation Agent

This repository also includes a small AI-agent style example that demonstrates
structured tool descriptions, JSON Schema parameter metadata, validated tool
execution, and generated documentation.

Print the available tool metadata:

```bash
python3 doc_agent.py tools
```

Generate Markdown documentation from Python files in `src/` into `docs/`:

```bash
python3 doc_agent.py run --show-trace
```

Update only missing or changed generated docs and remove stale generated docs:

```bash
python3 doc_agent.py run --incremental --prune-stale
```

Check whether generated docs are current without writing files:

```bash
python3 doc_agent.py run --check
```

Install the repository pre-push hook:

```bash
python3 scripts/install_git_hooks.py
```

After installation, `git push` runs the same documentation freshness check
locally. GitHub Actions also runs tests and `python doc_agent.py run --check`
on pushes to `main` and pull requests.

The agent uses six tools:

- `list_python_files` returns Python files from the configured source directory.
- `read_file` reads a selected Python file after validating the `file_path` arg.
- `write_doc_file` writes Markdown into the configured docs directory after
  validating `file_name` and `content`.
- `list_doc_files` returns Markdown files from the configured docs directory.
- `read_doc_file` reads generated Markdown before deciding whether it changed.
- `delete_doc_file` removes stale generated Markdown when `--prune-stale` is used.

## Data Model

Payments are stored in a local SQLite database. The database file defaults to
`payments.db` when `--db` is not provided. Each payment row contains:

- receipt number
- customer name and optional email
- amount and currency
- payment method and date
- optional reference, description, and notes
- creation timestamp
