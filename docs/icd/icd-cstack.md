# Interface control: foundation-refrigeration and Cstack

| Side | Item |
|---|---|
| Provider | foundation-refrigeration, `foundation_refrigeration_bridge` |
| Consumer | Cstack host adapter for this Foundation |
| Transport | Child process, stdio, one JSON-RPC 2.0 message per line |
| Start command | `python -B -m foundation_refrigeration_bridge`, fixed cwd, minimal fixed environment, no shell |
| Pins | Manifest SHA-256, manifest file count, canonical tool inventory SHA-256, printed by `python -B tools/build_manifest.py` |
| Version | 0.1.0 (`SOURCE-MANIFEST.json`) |

## Methods

`initialize`, `tools/list`, `tools/call`. Tools: `saturation_pressure`, `saturation_temperature`, `convert_pressure`, `convert_temperature`, `check_reading_against_saturation`, `exposure_limits`, `resolve_equipment_kind`.

## Rules

1. The consumer re-verifies the pins before dispatch and after every accepted response.
2. Only integers or bounded decimal strings cross the bridge as the schemas state; floats are rejected where the schema says so.
3. The consumer grants only the `read` effect.
4. A change to any shipped source file outside the root `.github/` tree changes the manifest pin. The consumer repins in the same change that updates its vendored copy.

## Python invariant interface

`foundation_refrigeration.invariants.evaluate(check, claim)` is a standard-library-only local
Python API. It is separate from JSON-RPC and does not use bridge receipts or decimal-string schemas.
Quantity objects have exactly `value` (finite int or float, excluding bool, magnitude at most 1e9)
and `unit` (a supported domain pressure or temperature unit). Claims have exactly these fields:

| Check | Claim fields | Canonical comparison |
|---|---|---|
| `pressure_relation` | `left`, `right`, `relation`, `atmosphere` | kPa(a), tolerance 1e-6 |
| `temperature_relation` | `left`, `right`, `relation` | degC, tolerance 1e-6 |
| `saturation_temperature` | `fluid`, `side`, `pressure`, `temperature`, `atmosphere` | degC, table error plus 0.001 K |

Relations are `eq`, `lt`, `gt`; strict ordering must exceed the tolerance. Atmosphere may be
null for absolute pressure, but gauge quantities require an explicit `standard`, `elevation` or
`measured` basis using the domain unit API's atmosphere object. Blend `side` must be `bubble`
or `dew`; pure fluids also accept null. Absolute pressures must be positive and temperatures
above absolute zero. Unsupported fluids and out-of-table pressures fail.

Results contain `check`, `passed`, `reason`, `library_version` and, on success, `measurements`.
Unknown checks and invalid claims return `passed: false` with a reason. Pressure measurements
include atmosphere evidence; saturation measurements include table provenance and evidence.
`library_version` is `refrigeration-invariants/0:` plus the SHA-256 of canonical JSON source hashes
(sorted keys, compact separators). `SOURCE_HASHES` maps package-relative Python and data JSON
paths to SHA-256 values captured at import. Restart consumers after source/data changes.
These results are observations and do not authorize plant actions or establish compliance.

