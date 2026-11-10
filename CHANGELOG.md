# Changelog

Format: Keep a Changelog 1.1, SemVer.

## [Unreleased]

### Documentation

- Records for the 2026-11-10 family findings sweep: requirements REQ-REF-038 to REQ-REF-045 (output limit, internal-error containment, envelope and id validation, `ping`, projection-loader refusals, load-time data validation, issuer/vocabulary/term errors, single version identity), REQ-REF-035 extended to exit 2 on `OSError` and REQ-REF-008 to the `.ruff_cache/` exclusion; verification-matrix rows for every new test; gap register GAP-REF-001 to GAP-REF-008 closed; findings F-4, F-7, F-8, F-9 and the static-analyzer half of F-10 closed in the assurance record (branch protection stays open); the interface document's `-32603` row covers non-JSON result types; the configuration-management plan describes the ruff job and the manifest exclusion.
- NASA-standard documentation set (self-assessed Class E analog, not safety-critical): software management plan with classification statement, compliance matrix, requirements in record format (REQ-REF-001 to REQ-REF-036, untested behaviour listed as GAP-REF-001 to GAP-REF-008), design description, interface control document, data dictionary with the source, edition and units of every table, test plan, verification matrix, configuration management plan, assurance record, user manual map, tutorial, how-to guides and the "Limitations and safety-relevant use" page.
- Corrected REQ-REF-010: tool errors carry an empty Evidence list, as the code and tests always did.
- Corrected the interface document: `tools/build_manifest.py` does not print the inventory digest.
- Problem-report and change-request issue templates replace the bug template; the pull request template records peer review.

### Added

- `tests/test_gap_register.py`: 36 tests covering GAP-REF-001 to GAP-REF-008, and tests that the five version strings agree (F-4) and that `.ruff_cache/` stays outside the manifest.
- CI `ruff` job running `uvx ruff@0.17.0 check .` with ruff's default rules (F-10, static-analyzer half). The package, tests and tools were cleaned to pass it with no behaviour change.
- `tools/check_trace.py` (requirement trace and link check), `tools/gen_docs.py` (generated tool catalog and reference data pages), `tools/gen_reports.py` (generated test report and version description) and `tests/test_docs_trace.py`, which runs the trace check and the generated-page check in the test suite.

### Removed

- Unused `pathlib.Path` import in `tests/test_process_safety.py` (F-8).

### Fixed

- The bridge answers `-32603` "Result cannot be represented; evidence withheld" when a result holds a value of a non-JSON type such as a set or bytes. Before, `encode_response` did not catch the resulting `TypeError` and the session ended without a reply. Found by the GAP-REF-002 test in the 2026-11-10 findings sweep.
- The source manifest and its inventory test exclude the `.ruff_cache/` directory that `ruff check` writes, so running ruff before the tests no longer changes the manifest inventory. `.ruff_cache/` is also in `.gitignore`.
- `tools/gen_reports.py` fails the report ("FAILED" conclusion, exit 1) when the manifest, generated-docs or Gitleaks gate fails, or when any test is skipped or unrecorded in the normal or optimized run; before, only unittest exit codes and trace problems counted. New requirement REQ-REF-037. Found by the 2026-11-09 backfill review.
- Exclude the root `.github/` automation and repository metadata tree from the source manifest so CI-only changes do not invalidate source pins.

### Added

- Initial release: Foundation package, stdio bridge, tests, and NASA-style docs under `docs/`.
