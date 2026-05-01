---
title: Sant Pau Tickets API — Reverse Engineering Notes
description: "Complete documentation of the EUROMUS/CCALGIR ticketing API used by tickets.santpaubarcelona.org, sufficient to re-implement the provider in any language without re-processing the HAR file."
methods:
  - activitats: List all available activities (tours, visits)
  - getCalendari: Per-day open/sold-out calendar for a date range
  - horaris: Time-slot availability for a single date
  - getDesActiv: Activity description text (not implemented)
  - getDataHoraSistema: Server date/time (not implemented)
  - getComentariLleg: Calendar footnote text (not implemented)
  - getTarifes: Pricing tiers for a session (implemented)
depends_on: []
used_by:
  - ticket_providers/sant_pau/constants.py
  - ticket_providers/sant_pau/helpers.py
  - ticket_providers/sant_pau/provider.py
  - tests/unit/test_sant_pau_activities.py
  - tests/unit/test_sant_pau_sessions.py
  - tests/unit/test_sant_pau_calendar.py
  - tests/unit/test_sant_pau_prices.py
  - tests/integration/test_sant_pau_integration.py
---

# Sant Pau Tickets API — Reverse Engineering Notes

HAR captured on 2026-05-01 with Firefox 149.0.

---

## Base Endpoint

All API calls are HTTP **POST** requests to:

```
https://tickets.santpaubarcelona.org/stpmuslinkIV/wsmuslinkIV
```

The body is encoded as `application/x-www-form-urlencoded; charset=UTF-8`.  
The server responds with JSON (`application/json;charset=UTF-8`).

---

## Session / Cookie Behaviour

The server uses a Java Servlet session cookie: **`JSESSIONID`**.

To obtain one, perform a **GET** to the index page before making POST calls:

```
https://tickets.santpaubarcelona.org/stpmuslinkIV/index.jsp
    ?lang=1&nom_cache=SANTPAU&property=SANTPAU&grupActiv=1
```

Additional cookies observed in the HAR:

| Cookie | Source | Purpose |
|---|---|---|
| `JSESSIONID` | Server (Set-Cookie) | Java session token — **required** |
| `valCookie1=1` | Server | Cookie consent flag |
| `valCookie2=1` | Server | Cookie consent flag |
| `cf_clearance` | Cloudflare | Bot protection token — may cause blocks for automated clients |
| `_ga*` | Google Analytics | Tracking only — not required for API calls |

> **Note:** The `cf_clearance` Cloudflare cookie indicates the endpoint has
> bot-protection active. Plain `httpx` requests may be challenged or blocked
> after heavy usage. The integration tests use conservative sleep intervals.

An `httpx.Client` with `follow_redirects=True` will automatically persist
`JSESSIONID` across requests within the same session.

---

## Required Request Headers

```
User-Agent:        Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:149.0) Gecko/20100101 Firefox/149.0
Accept:            */*
Accept-Language:   en,ca;q=0.9,en-US;q=0.8
Accept-Encoding:   gzip, deflate, br
Content-Type:      application/x-www-form-urlencoded; charset=UTF-8
X-Requested-With:  XMLHttpRequest
Origin:            https://tickets.santpaubarcelona.org
Referer:           https://tickets.santpaubarcelona.org/stpmuslinkIV/index.jsp?lang=1&nom_cache=SANTPAU&property=SANTPAU&grupActiv=1
```

---

## Common POST Parameters (all actions)

These parameters are included in every POST request:

| Parameter | Value |
|---|---|
| `codiMuseu` | `SANTPAU` |
| `property` | `SANTPAU` |
| `lang` | `1` (Catalan; 2=Spanish, 3=English — untested) |

---

## Known `elem` Actions

### `activitats` — List Activities

Returns the list of activities (types of visit) available at the venue.

**POST body:**
```
elem=activitats
codiMuseu=SANTPAU
property=SANTPAU
codiActiv=
codiCombi=
codiCicle=
grupActiv=1
dataVisita=
lang=1
besCodiActiv=
besCodiCombi=
```

**Response:** JSON array of activity objects.

| Field | Type | Description |
|---|---|---|
| `codi` | string | Activity identifier. May be non-numeric, e.g. `"0-8"` for combo activities |
| `desc` | string | Human-readable name — may have leading/trailing whitespace |
| `tipus` | string | `"S"` = standard, `"C"` = cultural event, `"COMBI"` = combined/combo |
| `calendariWeb` | string\|null | `"S"` if shown on the web calendar, null otherwise |
| `hihaPlaces` | int | Total bookable places (approximate, for informational use only) |
| `preu` | string | Appears to be total price for the group, not per-person |
| `primerMes` | string | First month of availability in `DD/MM/YYYY` format |
| `ultimMes` | string | Last month of availability in `DD/MM/YYYY` format |

**Activities observed in HAR (2026-05-01):**

| codi | desc | tipus |
|---|---|---|
| `1` | Visita Lliure | S |
| `2` | Visita Guiada | S |
| `42` | Pack Infantil | S |
| `111` | Ruta guiada: La rambla de la salut... | C |
| `112` | La Nit dels Museus 2026 | C |
| `0-8` | Visita Lliure amb audioguia interactiva | COMBI |

---

### `getCalendari` — Per-Day Availability Calendar

Returns which days have open / sold-out / free-admission sessions for a date range.

**POST body:**
```
elem=getCalendari
fI=DD/MM/YYYY        (start date, inclusive)
fF=DD/MM/YYYY        (end date, inclusive — leading zeros optional in browser)
fFBes=               (purpose unknown; send empty string)
cActivitats=<id>     (activity ID)
cActivitatsN=        (purpose unknown; send empty string)
activSel=<id>        (same activity ID as cActivitats)
codiMuseu=SANTPAU
lang=1
property=SANTPAU
```

**Response:** JSON array of calendar day objects.

| Field | Type | Description |
|---|---|---|
| `fecha` | string | Date in **ISO format `YYYY-MM-DD`** (the server normalises this) |
| `tipus` | string | `"EST"` = standard day with sessions; `"senseLloc"` = no availability |
| `portesObertes` | string | `"S"` = free-admission (open-doors) day; `"N"` = normal paid day |
| `comentariCal` | array | Calendar footnote objects (usually empty) |

**Day type legend:**

| `tipus` | `portesObertes` | Meaning |
|---|---|---|
| `EST` | `N` | Normal paid day — sessions available |
| `EST` | `S` | Free-admission day — sessions may be limited (requires reservation) |
| `senseLloc` | `N` | No availability — fully sold out or closed |

---

### `horaris` — Time-Slot Availability

Returns the list of bookable time slots for a specific activity on a specific date.

**POST body:**
```
elem=horaris
codiActiv=<id>       (activity ID)
lang=1
hora=0000            (using 0000 returns ALL slots for the day; using
                      current HH:MM would filter out past slots)
fecha=DD/MM/YYYY     (CRITICAL: must use forward slashes, NOT dashes;
                      "02/05/2026" works; "02-05-2026" returns empty [])
codiMuseu=SANTPAU
property=SANTPAU
```

> ⚠️ **Date format warning:** The browser was observed sending `hora` as the
> current system time (e.g. `2149`). This filters out past sessions.
> Using `hora=0000` returns every session regardless of current time,
> which is preferable for a read-only availability checker.

**Response:** JSON array of activity wrapper objects.

```json
[
  {
    "codi": "1",
    "portesObertes": "N",
    "tipus": "NORMAL",
    "codiCombi": "0",
    "desc": "Visita Lliure ",
    "mostrIdioma": "S",
    "error": "",
    "sessions": [ ... ]
  }
]
```

**Session object fields:**

| Field | Type | Description |
|---|---|---|
| `numSessio` | string | Session identifier |
| `idioma` | string | Language code; `"0"` = no restriction |
| `horaInici` | string | Start time as 4-digit string, e.g. `"0930"` = 09:30 |
| `horaFi` | string | End time as 4-digit string, e.g. `"1000"` = 10:00 |
| `totalPers` | int\|null | Total capacity; **may be `null` for special sessions** |
| `nPers` | int | **Seats still AVAILABLE** (not booked) — see note below |
| `percPers` | float | **Percentage of seats still AVAILABLE** (0.0–100.0) — see note below |

> ⚠️ **Field semantics — verified empirically:** Despite the names suggesting
> booking counts, `nPers` and `percPers` measure *availability*, not occupancy.
> Confirmation: on 16/05/2026 all sessions had `nPers≈342–350` and `percPers≈97–100%`
> while the website showed green (low-occupancy) bar-chart icons for every slot.
> Under a "booked" interpretation these would have been 97–100% full.
| `nomesCombi` | string\|null | `null` = bookable standalone; `"N"` observed on some sessions (semantics unclear) |
| `portesObertes` | string | `"S"/"N"` — free-admission flag for this session |
| `temporada` | string\|null | Season label (e.g. `"2025 "`); may be null |
| `identInt` | string\|null | Internal identifier; usually null or empty string |

---

## Date Format Conversions

| Direction | Format | Example |
|---|---|---|
| API input (`horaris`, `getCalendari`) | `DD/MM/YYYY` | `"02/05/2026"` |
| API output (`getCalendari`) | `YYYY-MM-DD` | `"2026-05-02"` |
| Our interface input | `YYYY-MM-DD` | `"2026-05-02"` |

**Algorithm (ISO → API):** split on `"-"`, reverse the three parts, join with `"/"`.

```
"2026-05-02"  →  ["2026", "05", "02"]  →  reversed  →  "02/05/2026"
```

---

## Time Format Conversions

| Direction | Format | Example |
|---|---|---|
| API value | 4-digit string, zero-padded | `"0930"` |
| Our interface | `HH:MM` | `"09:30"` |

**Algorithm:** insert `":"` after character index 2.

```
"0930"  →  "09" + ":" + "30"  →  "09:30"
"0000"  →  "00:00"
"2359"  →  "23:59"
```

---

## Availability Calculation

```
seats_available   = nPers              (None when totalPers is null)
seats_total       = totalPers          (None when null)
percent_available = percPers           (from API; 0.0–100.0)
percent_occupied  = 100.0 - percPers   (None when percPers is None)
```

`nPers` = seats still available (not booked).  
`percPers` = percentage of capacity still available.

---

## Status Mapping

| Condition | Status |
|---|---|
| `seats_available is None` | `unknown` |
| `seats_available <= 0` | `sold_out` |
| `percent_occupied >= 90.0` (i.e. `percPers <= 10.0`) | `limited` |
| otherwise | `available` |

The 90% occupied threshold is configurable via `SANT_PAU_LIMITED_THRESHOLD_PERCENT_OCCUPIED`.  
With 350 seats (typical capacity), 90% occupied means ≈ 35 seats remaining.

---

## Assumptions and Unknowns

- `lang=1` is assumed to be Catalan; other values (2=Spanish, 3=English…)
  likely exist but were not tested.
- `hora=0000` in `horaris` requests is an intentional deviation from browser
  behaviour (which sends the current clock time) to obtain all daily slots.
- `nomesCombi` semantics are not fully confirmed.  It may indicate combo-only
  booking; `null` appears to mean standalone-bookable.
- The `codi="0-8"` activity type (`COMBI`) has a non-numeric ID with a hyphen.
- Cloudflare bot-protection is active; heavy automated use may be blocked.
- The `fFBes`, `cActivitatsN` parameters in `getCalendari` are always sent as
  empty strings; their purpose is unknown.
- `getDesActiv`, `getDataHoraSistema`, `getComentariLleg` are additional `elem`
  values observed in the HAR but not implemented.
- `getTarifes` is implemented (see section below).

---

## `getTarifes` — Pricing Tiers for a Session

Returns the list of available ticket types and their prices for a specific
date + time slot.

**POST body:**
```
elem=getTarifes
cActivitats=<id>     (activity ID)
codiMuseu=SANTPAU
lang=1
property=SANTPAU
temporada=           (season label from session, e.g. "2025 "; send empty string to let API resolve)
fecha=DD/MM/YYYY     (date of the session)
hora=HHMM            (start time of the session as 4-digit string, e.g. "1100")
portesO=false        ("true" on free-admission days)
numerada=false       (numbered seating; false for general admission)
grupTarifa=          (empty string)
```

**Response:** JSON array of price tier objects.

| Field | Type | Description |
|---|---|---|
| `codi` | int | Tier identifier |
| `desc` | string | Tier name (e.g. `"General"`, `"Menors 12 anys"`) |
| `observ` | string | Conditions / extended description (may be empty) |
| `preu` | string | Current price as decimal string, e.g. `"18.00"` |
| `preuOriginal` | string | Pre-discount price; equals `preu` when no discount |
| `amic` | string | `"S"` if a membership card is required; `"N"` otherwise |
| `portesObertes` | string | `"S"` if valid only on free-admission days |
| `minPers` | int\|null | Minimum group size for this tier, or null |
| `maxPers` | int\|null | Maximum group size for this tier, or null |
| `favorita` | string | `"S"` if this is the highlighted/default tier |
| `abonament` | string | Season-pass flag (`"S"`/`"N"`) |
| `opcioBescanvi` | bool | Whether an exchange option is available |

**Price tiers observed in HAR (16/05/2026, activity 1, hora 1100):**

| Tier name | Price (EUR) | Notes |
|---|---|---|
| General | 18.00 | Standard adult price |
| Amics del Recinte Modernista | 0.00 | Membership card required (`amic=S`) |
| BCN Card | 14.40 | Discount card required |
| Carnet Biblioteques | 14.40 | Discount card required |
| CityTours | 14.40 | Discount card required |
| Club TR3SC | 14.40 | Discount card required |
| Membres del COAC | 14.40 | Col·legi d'Arquitectes |
| Discapacitat grau menor 65% | 12.60 | Disability discount |
| Família monoparental | 12.60 | Single-parent family |
| Família nombrosa | 12.60 | Large family |
| Joves de 12 a 24 anys | 12.60 | Youth discount |
| Majors de 65 anys | 12.60 | Senior discount |
| Menors 12 anys | 0.00 | Free for under-12s |
| Socis d'Òmnium Cultural | 14.40 | Cultural society members |
| Titulars RACC Màster | 14.40 | Automobile club members |
| Resident BCN | 12.60 | Barcelona residents |
| Subscriptors del Diari ARA | 14.40 | Newspaper subscribers |
| Targeta Rosa Reduïda | 12.60 | Social transport card |
