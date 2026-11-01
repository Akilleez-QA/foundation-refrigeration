# Configuration management

- Versioning: SemVer. Current version 0.1.0, recorded in `SOURCE-MANIFEST.json`.
- Baseline: the initial commit on `main`.
- Change control: pull requests only, one concern, about 400 changed lines. Refrigeration.AI merges after checking the head SHA. Branches are kept.
- Pins: after any change run `python -B tools/build_manifest.py` and commit the new `SOURCE-MANIFEST.json`. Consumers repin from its output.
- `PR_BODY.md` is an uncommitted review handoff, excluded from the shipped-file manifest and its inventory verification.
- Releases and tags: none yet. A tag is created only with owner approval.
- Secret scanning: gitleaks and trufflehog run before every push.
- Invariant provenance: `foundation_refrigeration/invariants.py` received from `Akilleez-QA/endoforge` main at `819fa8a6b3eea9cae5f1388eb67a78556ad65727`, source `tools/invariants/refrigeration.py` and its README. Imports and hash paths are local to this package; `LIBRARY_VERSION` binds the package Python and JSON data at import. Regenerate the source manifest with the existing tool after edits; golden reference data is unchanged.
