# foundation-refrigeration assurance record

| Field | Value |
|---|---|
| Document ID | FREFRIG-SAR |
| Version | 1.1 |
| Status | Baselined |
| Owner | Akilleez-QA |
| Date | 2026-11-10 |
| Baseline commit | 62764c7526ce2bbf064ccf633d5295f4390fc984 |
| Applies to | foundation-refrigeration main at baseline commit |
| Classification | Self-assessed Class E analog; not safety-critical (see SMP §1) |

> Organized after [NPR 7150.2D](https://nodis3.gsfc.nasa.gov/displayAll.cfm?Internal_ID=N_PR_7150_002D_&page_name=all), [NASA-STD-8739.8B](https://standards.nasa.gov/standard/nasa/nasa-std-87398) and the [NASA Software Engineering Handbook](https://swehb.nasa.gov/display/SWEHBVD/7.18+-+Documentation+Guidance) documentation guidance. This is not a NASA compliance determination or certification. The software classification is a self-assessed analog (Class E, not safety-critical); no NASA authority, independent verification and validation, or hazard analysis is asserted. The document describes the implementation inspected at the baseline commit.

Rolling record, newest entry first.

## Entry 2026-11-10 — findings sweep (atom commits 4d3fdf9, 9229fa9 and d531cec)

- Analyzed by: agent lanes of the family findings sweep (agent analysis is not independent).
- Inputs: the open findings F-4 and F-7 to F-10 and the gap register GAP-REF-001 to GAP-REF-008 at `main` `f78905d`; the sweep commits 4d3fdf9, 9229fa9 and d531cec on branch `fix/findings-sweep`; Cstack pull request #82.
- Code changed: `tests/test_gap_register.py` (36 tests, one or more per gap); two tests in `tests/test_names_and_manifest.py` (version agreement, `.ruff_cache/` exclusion); `foundation_refrigeration_bridge/server.py` (`encode_response` also catches `TypeError`; the dispatch catch-all now raises `-32603` from the original exception); `tools/build_manifest.py` and the manifest test exclude `.ruff_cache/`; a CI `ruff` job; ruff-driven cleanups across the package, tests and tools with no behaviour change (generated documents and report output byte-identical).

### Testing analysis

- Each new gap test was checked to fail against a deliberately broken copy of the code outside the tree (21 of 21 breakages caught, including one for the version test).
- The GAP-REF-002 test found a defect: a result holding a set, bytes or another non-JSON type raised `TypeError` inside `encode_response`, which caught only `ValueError`, `OverflowError` and `RecursionError`, so the session ended without a reply. `TypeError` is now caught and the response is `-32603` "Result cannot be represented; evidence withheld" (REQ-REF-039, [ICD §4](../icd/icd-cstack.md#4-errors-and-result-semantics)).
- Requirements REQ-REF-038 to REQ-REF-045 were added and REQ-REF-008 and REQ-REF-035 extended; the trace check reports 45 requirements, all traced, and every test traced or classified.

### Source code quality

| Tool | Command | Findings (new / total) |
|---|---|---|
| ruff 0.17.0 (CI gate from this entry) | `ruff check --no-cache .` (CI: `uvx ruff@0.17.0 check .`) | 0 / 0 ("All checks passed!"), also with `--isolated` |

### Findings closed

| ID | Closure |
|---|---|
| F-4 | `tests/test_names_and_manifest.py::ManifestTests.test_version_is_written_identically_everywhere` checks that the package, bridge, `schemas.VERSION`, `tools/build_manifest.py` and manifest versions agree (REQ-REF-045) |
| F-7 | GAP-REF-001 to GAP-REF-008 each have tests in `tests/test_gap_register.py` and trace to REQ-REF-035 or REQ-REF-038 to REQ-REF-044 |
| F-8 | The unused `pathlib.Path` import was removed from `tests/test_process_safety.py` |
| F-9 | Cstack pull request #82 (merged 2026-11-10) re-vendored this repository at its backfill-fix commit and repinned the manifest. Every later merge here, this one included, changes the pin again and needs the usual repin ([ICD §8](../icd/icd-cstack.md#8-change-acceptance)) |
| F-10 (static analyzer) | The CI `ruff` job runs ruff 0.17.0 with its default rules on every pull request and push |

Still open: the branch-protection half of F-10 (a GitHub setting outside the repository; SMP risk R-3) and the code half of F-2.

## Entry 2026-11-08 — baseline 62764c7 (documentation baseline PR)

- Analyzed by: agent documentation lane N5 (agent analysis is not independent).
- Inputs: all source, tests, data, golden files, CI workflow and documentation at `62764c7526ce2bbf064ccf633d5295f4390fc984`; git history; GitHub pull requests #1 to #9; the family documentation standard.
- Code under `foundation_refrigeration/`, `foundation_refrigeration_bridge/` and `golden/` was not changed by this entry. Added: `tools/check_trace.py`, `tools/gen_docs.py`, `tools/gen_reports.py`, `tests/test_docs_trace.py`.

### Requirements analysis

Techniques: every claim in the previous requirements, ICD, architecture, configuration and README text was checked against the code; every test was read and mapped to a requirement; `tests/` was searched for each code path to find untested behaviour; the trace check (`python -B tools/check_trace.py`) was written and run.

Results: 16 previous requirements kept with their IDs; REQ-REF-010 corrected (F-1); 20 requirements added for behaviour that tests already check (REQ-REF-017 to REQ-REF-036); 8 untested behaviours recorded as gaps GAP-REF-001 to GAP-REF-008 rather than requirements. Trace check: 36 requirements, 36 traced; every test traced or classified (counts in [STR-unreleased](../verification/reports/STR-unreleased.md)). No TBDs.

### Design analysis

SDD compared with the package tree. `process_safety.py`, `evidence.py`, `units.py`, `projection.py`, `decisions.py` and `plant_model.py` existed but were not described; all are now components with requirement IDs. No documented component is absent from the code. Every requirement is allocated to at least one component (checked by `tools/check_trace.py`).

### Testing analysis

- 55 tests at the baseline, all mapped; one (`test_projection_json_is_stable_regardless_of_key_order`) checks a helper the shipped code does not call and is classified as supporting.
- Untested paths: GAP-REF-001 to GAP-REF-008 (output-size cap, internal-error paths, envelope and id validation, `ping`, projection-loader refusals, load-time data validation, three tool error codes, broken pipe).
- Weak assertion noted: `tests/test_bridge.py::ReceiptTests.test_every_tool_succeeds_with_evidence_and_boundary` checks success, Evidence and boundary but not numeric values for most tools; values are checked in the unit tests and the golden tests.
- Coverage is not measured (no tool pinned).

### Source code quality

| Tool | Command | Findings (new / total) |
|---|---|---|
| ruff 0.14.0 (ad hoc, not a CI gate) | `uvx ruff@0.14.0 check --no-cache --select F,E9 foundation_refrigeration foundation_refrigeration_bridge tools tests` | 0 / 1 (F401 unused `pathlib.Path` import in `tests/test_process_safety.py`, F-8) |
| gitleaks 8.28.0 | `gitleaks git --redact --no-banner --exit-code 1 --config .gitleaks.toml .` | 0 / 0 ("no leaks found") |
| Imports review (manual) | `grep -rn "import " foundation_refrigeration foundation_refrigeration_bridge` | Standard library only; no `socket`, `urllib`, `http` or `subprocess` |

### Configuration audit

- `tools/build_manifest.py` reproduces the committed manifest at the baseline (CI manifest job and `tests/test_names_and_manifest.py`).
- The canonical tool inventory SHA-256 at the baseline, `aa89d7ea2acdc601e997de880282877c5efdfeaa510823a2902c77374507fa1b`, equals the `INVENTORY_SHA256` pinned in Cstack's `adapters/refrigeration_stdio.py` (Cstack main, 2026-11-08).
- Cstack's vendored copy pins an older manifest (63 files, including `.github/` files that PR #9 later excluded). Every merge here changes the manifest pin; Cstack must repin (F-9).
- No tags exist; the version description is labelled `unreleased`.

### Peer review summary

`gh pr list --state merged`: 9 pull requests merged (#1 to #9). One (#6) has a formal GitHub review; the others were merged by the maintainer with one or two comments each and no recorded review findings. Review is by a single maintainer plus agents; it is not independent.

### Findings

| ID | Severity | Finding | Location | Issue | Status |
|---|---|---|---|---|---|
| F-1 | S3 | REQ-REF-010 and the README said every result, errors included, carries Evidence; the code and `tests/test_bridge.py` return an empty Evidence list on tool errors, and the output schema requires it | `docs/requirements/requirements.md`, `README.md`, `AGENTS.md` | — | Closed: documents corrected |
| F-2 | S4 | The ICD said `tools/build_manifest.py` prints the inventory digest; it prints only the file count and manifest SHA-256 (foundation-template's generator does print it) | `docs/icd/icd-cstack.md`, `tools/build_manifest.py` | — | Doc closed; code difference open (not fixed in a docs lane) |
| F-3 | S4 | `exposure-limits.json` `generatedBy` refers to `tests/test_safety_limits.py`, which does not exist here | `foundation_refrigeration/data/exposure-limits.json` | — | Closed: `generatedBy` now names `tests/test_domain_data.py`, and a test checks every cited test file exists; the data digest changed, so Cstack repins |
| F-4 | S4 | The version `0.1.0` is written in three places (`__init__.py`, `schemas.VERSION`, `tools/build_manifest.py`) with no check that they agree | those files | — | Closed 2026-11-10 (4d3fdf9, 9229fa9 and d531cec): version-agreement test, REQ-REF-045 |
| F-5 | S4 | The SCMP said gitleaks and trufflehog run before every push; only gitleaks runs, in CI | `docs/configuration/configuration-management.md` | — | Closed: document corrected |
| F-6 | S4 | The ICD said numbers cross as "bounded decimal strings" and floats are rejected; decimals are JSON numbers parsed to floats | `docs/icd/icd-cstack.md` | — | Closed: document corrected |
| F-7 | S3 | Eight untested behaviours (GAP-REF-001 to GAP-REF-008) | `foundation_refrigeration_bridge/server.py` and others | — | Closed 2026-11-10 (4d3fdf9, 9229fa9 and d531cec): `tests/test_gap_register.py`, REQ-REF-035 and REQ-REF-038 to REQ-REF-044 |
| F-8 | S4 | Unused import `pathlib.Path` | `tests/test_process_safety.py` | — | Closed 2026-11-10 (4d3fdf9, 9229fa9 and d531cec): import removed |
| F-9 | S3 | Cstack's vendored copy pins an older manifest | Cstack `adapters/refrigeration_stdio.py` | — | Closed 2026-11-10: repinned by Cstack PR #82; each later merge needs the usual repin |
| F-10 | S3 | `main` has no branch protection; no static analyzer in CI | GitHub settings, `.github/workflows/ci.yml` | — | Static analyzer closed 2026-11-10 (4d3fdf9, 9229fa9 and d531cec): CI `ruff` job (R-4). Branch protection open (R-3) |

### Overall assessment

The code matches its documentation after the corrections above. Behaviour is well tested for the documented tools, data content and refusals. The main remaining assurance gaps are the untested bridge error paths, the absence of a static analyzer and branch protection, and the fact that no data value has been approved by a qualified person. None changes the classification.

## Change history

| Version | Date | Commit | Change | Reviewed in |
|---|---|---|---|---|
| 1.0 | 2026-11-08 | 62764c7 | Initial baseline | PR adding the NASA-standard documentation set |
| 1.1 | 2026-11-10 | d531cec | Entry for the findings sweep; F-4, F-7, F-8, F-9 and the static-analyzer half of F-10 closed | PR from the 2026-11-10 family findings sweep |
