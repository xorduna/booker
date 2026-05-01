# ticket-providers

A small, clean Python package for read-only ticket availability checking
across multiple providers and venues.

**Current providers:** Sant Pau (Recinte Modernista de Sant Pau, Barcelona)

> This wrapper is **read-only**.  It checks availability only and does
> not support purchasing, reservations, or any write operations.

---

## Project Structure

```
ticket_providers/        # Core package
  __init__.py
  models.py              # Shared data models (Venue, Activity, AvailabilitySlot, …)
  base.py                # Abstract TicketProvider base class
  sant_pau.py            # Sant Pau provider implementation

examples/
  sant_pau_availability.py   # CLI: print availability for a given day

tests/
  fixtures.py                # Shared mock data (from real HAR capture)
  unit/                      # Unit tests (no network)
  integration/               # Integration tests (real API, opt-in)

docs/
  sant_pau_api.md            # Full Sant Pau API reverse-engineering notes
  code-index.md              # Auto-generated code index

scripts/
  build_code_index.py        # Regenerates docs/code-index.md
```

---

## Requirements

- Python 3.12+
- [httpx](https://www.python-httpx.org/) ≥ 0.27

---

## Installation

```bash
pip install -e ".[dev]"
```

---

## Quick Start

```python
from ticket_providers import SantPauProvider

provider = SantPauProvider()
provider.init()

venues = provider.get_venues()
activities = provider.get_activities("sant_pau")
calendar = provider.get_calendar("sant_pau", "2026-06-01", "2026-06-30")
slots = provider.get_availability("sant_pau", "2026-06-15", num_people=2)

for slot in slots:
    print(
        f"{slot.start_time}–{slot.end_time}  "
        f"avail={slot.seats_available}/{slot.seats_total} "
        f"({slot.percent_available:.1f}% free)  "
        f"[{slot.status}]  group_ok={slot.has_availability}"
    )
```

---

## Example CLI

```bash
# Availability for a specific day (default: 1 person, activity 1)
python examples/sant_pau_availability.py 2026-06-15

# Check for a group of 4 people
python examples/sant_pau_availability.py 2026-06-15 --people 4

# Different activity
python examples/sant_pau_availability.py 2026-06-15 --activity 2 --people 2
```

Sample output:

```
Sant Pau — 2026-06-15  (activity=1, group=1)
------------------------------------------------------------------------
Start   End     Avail  Total    Occ%   Free%  Group?  Status
------------------------------------------------------------------------
09:30   10:00      25    350   93.0%    7.0%     YES  limited
10:00   10:30      18    350   95.0%    5.0%     YES  limited
...
14:30   15:00       0    350  100.0%    0.0%      NO  sold_out
------------------------------------------------------------------------
  14 of 17 slots have availability for 1 person(s).
```

---

## API Reference

### `TicketProvider` (abstract base class)

| Method | Signature | Description |
|---|---|---|
| `init` | `() → None` | Establish HTTP session (call once first) |
| `get_venues` | `() → list[Venue]` | List supported venues |
| `get_activities` | `(venue_id: str) → list[Activity]` | List activities at a venue |
| `get_calendar` | `(venue_id, from_date, to_date, activity_id=None) → list[CalendarDay]` | Per-day availability calendar |
| `get_availability` | `(venue_id, day, activity_id=None, num_people=1) → list[AvailabilitySlot]` | Time-slot availability |

All dates are in **ISO 8601 `YYYY-MM-DD`** format.

### `AvailabilitySlot` fields

| Field | Type | Description |
|---|---|---|
| `start_time` | `str` | Slot start in `HH:MM` |
| `end_time` | `str \| None` | Slot end in `HH:MM` |
| `seats_available` | `int \| None` | Remaining bookable seats |
| `seats_total` | `int \| None` | Total capacity |
| `percent_occupied` | `float \| None` | % seats taken (0–100) |
| `percent_available` | `float \| None` | % seats free (0–100) |
| `has_availability` | `bool` | `True` when `seats_available >= num_people` |
| `requested_seats` | `int` | The `num_people` value used in the query |
| `status` | `str` | `available` / `limited` / `sold_out` / `closed` / `unknown` |
| `metadata` | `dict` | Raw provider fields |

---

## Running Tests

### Unit Tests (no network)

```bash
pytest tests/unit/ -v
```

The unit tests use mocked HTTP responses derived from the real HAR capture.
They do **not** call the Sant Pau API.

### Integration Tests (real API)

```bash
RUN_INTEGRATION_TESTS=1 pytest tests/integration/ -v
```

> ⚠️ Integration tests **call the real Sant Pau ticketing endpoint**.
> Use them sparingly and never in automated CI loops.
> The tests are intentionally conservative: only a single future date is
> queried, with 2-second sleeps between calls.
>
> This wrapper is **read-only** and does not test purchasing.

### All Tests at Once

```bash
pytest -v                        # unit tests only (integration skipped)
RUN_INTEGRATION_TESTS=1 pytest   # unit + integration
```

---

## Regenerating the Code Index

```bash
python scripts/build_code_index.py
```

This reads the YAML front-matter from every file in `docs/` and writes
`docs/code-index.md`.

---

## Adding a New Provider

1. Create `ticket_providers/<provider_name>.py`.
2. Subclass `TicketProvider` and implement all five abstract methods.
3. Export the new class from `ticket_providers/__init__.py`.
4. Add unit tests in `tests/unit/`.
5. Add an example script in `examples/`.
6. Document the API in `docs/<provider_name>_api.md` and run
   `python scripts/build_code_index.py`.

---

## Security Notes

- This package makes outbound HTTPS requests only.
- No credentials are stored or transmitted beyond what the normal
  browser session requires (session cookie).
- No purchasing, form submission, or account-level operations are performed.
