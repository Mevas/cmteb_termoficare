# CMTEB Termoficare for Home Assistant

Home Assistant integration for monitoring CMTEB Bucuresti hot water / heating incidents for a configured street and block.

This fork focuses on a cleaner Home Assistant UX:

- one short-state source sensor: `normal`, `affected`, `error`, `unknown`
- long CMTEB text stored as attributes, not sensor state
- Home Assistant-parseable ETA attribute (`YYYY-MM-DDTHH:MM:SS`)
- street + block matching inside grouped CMTEB rows like `Str Avionului - bl. 16J, 15H, 15D`
- parser tests with checked-in HTML fixtures
- aggregate/statistical sensors are intended to be built afterwards with HA helpers

## Install

### HACS Custom Repository

Add this repository as a HACS custom repository:

```text
https://github.com/Mevas/cmteb_termoficare
```

Category: `Integration`

Restart Home Assistant after installation, then add the integration from:

`Settings -> Devices & Services -> Add Integration -> CMTEB Termoficare`

## Configuration

The config flow asks for:

- `Street`: street name as it appears, or approximately appears, on CMTEB
- `Block`: exact block token, e.g. `15D`, `205`
- `Thermal point`: optional hint / disambiguator

The parser is diacritics-insensitive, so `Moinesti` can match `Moineşti`.

## Entity Model

Each configured address creates one sensor:

```text
sensor.cmteb_hot_water_status_<street>_<block>
```

The state is intentionally short:

| State | Meaning |
|---|---|
| `normal` | Address/block not found in the current CMTEB affected rows |
| `affected` | Address/block is currently listed as affected |
| `error` | Fetch or parser error |
| `unknown` | Not updated yet |

Detailed data is exposed as attributes:

- `match_found`
- `sector`
- `punct_termic`
- `affected_count`
- `service` (`ACC`, `ÎNC`, or both)
- `status_type` (`Deficienta ACC`, `Oprire ACC`, etc.)
- `cause`
- `eta` (ISO datetime string)
- `eta_raw` (original CMTEB text)
- `matched_zone`
- `address_lines`
- `record_text`
- `parser`
- `last_checked`
- `source_url`

## Helper-Derived Stats

Keep this integration as the current-source parser. Build long-running stats with Home Assistant helpers.

Recommended helpers:

- Template binary sensor: `on` when the CMTEB status sensor state is `affected`
- History Stats helper: monthly time spent affected
- Template sensor: affected hours converted to approximate affected days if desired

This keeps Recorder/statistics behavior in Home Assistant instead of hiding history in custom integration attributes.

## Parser Tests

Tests use checked-in HTML artifacts under `tests/fixtures/`.

Run locally:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-test.txt
.venv/bin/python -m pytest tests/test_parser.py
```

The fixture tests cover:

- grouped CMTEB rows with multiple `Punct termic` sections
- split `Punct termic:` / name / count line structure
- exact block-token matching (`15` must not match `15D`)
- no-match -> `normal`

## Credits

Forked from [`GeorgeRPI/cmteb_termoficare`](https://github.com/GeorgeRPI/cmteb_termoficare). Thanks to the original author for the HACS integration scaffold and initial CMTEB integration work.
