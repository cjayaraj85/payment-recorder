# `payment_recorder.web`

Source: `src/payment_recorder/web.py`

## Summary

No module docstring provided.

## Classes

### `PaymentHTTPRequestHandler`

No class docstring provided.

Methods:

- `do_GET(self) -> None`
- `do_POST(self) -> None`
- `log_message(self, format: str, *args) -> None`
- `_send_html(self, content: str, status: HTTPStatus = HTTPStatus.OK) -> None`
- `_send_text(self, content: str, status: HTTPStatus = HTTPStatus.OK) -> None`
- `_send_csv(self, content: str, filename: str) -> None`
- `_send_error(self, status: HTTPStatus, message: str) -> None`

## Functions

### `create_server(db_path: Path, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> ThreadingHTTPServer`

No function docstring provided.

### `run_server(db_path: Path, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None`

No function docstring provided.

### `render_dashboard(store: PaymentStore, query: Dict[str, List[str]], error: Optional[str] = None) -> str`

No function docstring provided.

### `render_payment_form(values: Dict[str, List[str]]) -> str`

No function docstring provided.

### `render_filter_form(query: Dict[str, List[str]]) -> str`

No function docstring provided.

### `render_summary(payments: List[Payment]) -> str`

No function docstring provided.

### `render_payment_table(payments: List[Payment]) -> str`

No function docstring provided.

### `render_receipt_page(store: PaymentStore, query: Dict[str, List[str]]) -> str`

No function docstring provided.

### `render_csv_export(store: PaymentStore, query: Dict[str, List[str]]) -> str`

No function docstring provided.

### `render_alerts(error: Optional[str], created: Optional[str]) -> str`

No function docstring provided.

### `page(title: str, body: str) -> str`

No function docstring provided.

### `render_error_page(message: str) -> str`

No function docstring provided.

### `date_filters(query: Dict[str, List[str]]) -> Tuple[Optional[date], Optional[date], Optional[str]]`

No function docstring provided.

### `parse_date_field(value: str) -> date`

No function docstring provided.

### `parse_optional_date(value: Optional[str]) -> Optional[date]`

No function docstring provided.

### `field(values: Dict[str, List[str]], name: str, default: str = '') -> str`

No function docstring provided.

### `optional_field(values: Dict[str, List[str]], name: str) -> Optional[str]`

No function docstring provided.

### `option(value: str, selected: str, label: str) -> str`

No function docstring provided.

### `query_string(query: Dict[str, List[str]], keep_filters: bool = False) -> str`

No function docstring provided.

### `attr(value: str) -> str`

No function docstring provided.

### `url(value: str) -> str`

No function docstring provided.
