# `payment_recorder.storage`

Source: `src/payment_recorder/storage.py`

## Summary

No module docstring provided.

## Classes

### `PaymentInput`

No class docstring provided.

Methods: none.

### `Payment`

No class docstring provided.

Methods:

- `amount(self) -> Decimal`

### `PaymentStore`

SQLite-backed payment store.

Methods:

- `__init__(self, db_path: Union[str, Path])`
- `initialize(self) -> None`
- `add_payment(self, payment: PaymentInput) -> Payment`
- `get_payment(self, payment_identifier: Union[int, str]) -> Payment`
- `list_payments(self, start_date: Optional[date] = None, end_date: Optional[date] = None) -> List[Payment]`
- `_connect(self) -> sqlite3.Connection`

## Functions

### `build_receipt_number(payment_id: int, payment_date: date) -> str`

No function docstring provided.

### `validate_payment_input(payment: PaymentInput) -> PaymentInput`

No function docstring provided.

### `normalize_optional_text(value: Optional[str]) -> Optional[str]`

No function docstring provided.

### `normalize_decimal(value: Decimal) -> Decimal`

No function docstring provided.

### `decimal_to_cents(value: Union[str, Decimal]) -> int`

No function docstring provided.

### `cents_to_decimal(cents: int) -> Decimal`

No function docstring provided.

### `row_to_payment(row: sqlite3.Row) -> Payment`

No function docstring provided.

### `total_cents(payments: Iterable[Payment]) -> int`

No function docstring provided.
