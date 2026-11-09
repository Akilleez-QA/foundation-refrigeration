<!-- Peer-review record, SWEHB 5.03 tailored. One concern per pull request, about 400 changed lines or fewer. -->

## Change

<!-- What and why. Link issues: Fixes #, Refs #. -->

## Requirements, design and interface impact

- Requirements added/changed/deleted:
- SDD / ICD / data dictionary updated: yes / no / not needed
- Verification matrix updated: yes / not needed
- Generated pages regenerated (`python -B tools/gen_docs.py`): yes / not needed
- `SOURCE-MANIFEST.json` regenerated (`python -B tools/build_manifest.py`): yes / not needed (only `.github/` changed)

## Verification

<!-- Commands run at the head commit, Python version and result. -->

- [ ] `python -B -m unittest discover -s tests -t .`
- [ ] `python -B -O -m unittest discover -s tests -t .`
- [ ] `python -B tools/build_manifest.py` leaves no diff

## Peer review record

- Reviewers: <human approver>, <agent reviewers> (agent review is not independent)
- Review type: code / docs / requirements / design / data
- Findings: <count by severity; list or link resolved threads>
- Outcome: approved / changes requested / re-review

## Contributor checklist

- [ ] `Assisted-by:` trailer on AI-written commits
- [ ] No code comments
- [ ] No expected results or golden files edited by hand
- [ ] One concern, about 400 changed lines or fewer
- [ ] Docs whose derivation paths this PR touches are updated or confirmed still accurate (for docs PRs, paste and tick the family documentation checklist)
