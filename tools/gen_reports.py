import argparse
import datetime
import hashlib
import importlib.util
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from foundation_refrigeration import __version__
from foundation_refrigeration_bridge.schemas import tool_definitions

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "docs/verification/reports"
RELEASES = ROOT / "docs/releases"
OWNER = "Akilleez-QA"
DISCLAIMER = (
    "> Organized after [NPR 7150.2D](https://nodis3.gsfc.nasa.gov/displayAll.cfm?Internal_ID=N_PR_7150_002D_&"
    "page_name=all), [NASA-STD-8739.8B](https://standards.nasa.gov/standard/nasa/nasa-std-87398) and the [NASA "
    "Software Engineering Handbook](https://swehb.nasa.gov/display/SWEHBVD/7.18+-+Documentation+Guidance) "
    "documentation guidance. This is not a NASA compliance determination or certification. The software "
    "classification is a self-assessed analog (Class E, not safety-critical); no NASA authority, independent "
    "verification and validation, or hazard analysis is asserted. The document describes the implementation "
    "inspected at the baseline commit.")
LINE = re.compile(r"^(test_\w+) \(tests\.(test_\w+)\.(\w+)\.test_\w+\) \.\.\. (ok|FAIL|ERROR|skipped.*)$")
CONTROL_DOCS = ("docs/plan/software-management-plan.md", "docs/plan/compliance-matrix.md",
                "docs/requirements/requirements.md", "docs/architecture/architecture.md", "docs/icd/icd-cstack.md",
                "docs/data/data-dictionary.md", "docs/verification/test-plan.md",
                "docs/verification/verification-matrix.md", "docs/configuration/configuration-management.md",
                "docs/assurance/assurance-record.md", "docs/guides/SUM-MAP.md")


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()


def gh(*args):
    if shutil.which("gh") is None:
        return None
    proc = subprocess.run(["gh", *args], check=False, cwd=ROOT, capture_output=True, text=True)
    return proc.stdout if proc.returncode == 0 else None


def run_suite(optimized):
    command = [sys.executable, "-B", *(["-O"] if optimized else []), "-m", "unittest", "discover", "-s", "tests",
               "-t", ".", "-v"]
    proc = subprocess.run(command, check=False, cwd=ROOT, capture_output=True, text=True,
                          env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    results = {}
    for line in proc.stderr.splitlines():
        match = LINE.match(line)
        if match:
            name, module, cls, outcome = match.groups()
            results[f"tests/{module}.py::{cls}.{name}"] = outcome.split()[0]
    ran = re.search(r"^Ran (\d+) tests? in ([0-9.]+)s$", proc.stderr, re.MULTILINE)
    display = f'python -B{" -O" if optimized else ""} -m unittest discover -s tests -t .'
    return {"command": display, "returncode": proc.returncode, "results": results,
            "ran": int(ran.group(1)) if ran else 0, "seconds": ran.group(2) if ran else "unknown",
            "digest": hashlib.sha256(proc.stderr.encode()).hexdigest(), "tail": proc.stderr.strip().splitlines()[-1]}


def trace_module():
    spec = importlib.util.spec_from_file_location("check_trace", ROOT / "tools/check_trace.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def requirement_map(trace):
    mapping = {}
    for row in trace.table_rows(trace.VM.read_text(), "| Requirement |"):
        for ref in (f"{path}::{cls}.{name}" for path, cls, name in trace.TEST_REF.findall(row[2])):
            mapping.setdefault(ref, []).append(row[0])
    return mapping


def source_lines():
    counts = {}
    for name in git("ls-files").splitlines():
        path = ROOT / name
        if not path.is_file():
            continue
        kind = {".py": "Python", ".md": "Markdown", ".json": "JSON", ".yml": "YAML"}.get(path.suffix)
        if kind:
            counts[kind] = counts.get(kind, 0) + len(path.read_bytes().splitlines())
    return counts


def issue_counts():
    raw = gh("issue", "list", "--state", "all", "--limit", "500", "--json", "state,labels")
    if raw is None:
        return None
    issues = json.loads(raw)
    by = {}
    for issue in issues:
        labels = [label["name"] for label in issue["labels"] if re.fullmatch(r"S[1-4]", label["name"])] or ["unlabelled"]
        for label in labels:
            key = (issue["state"].lower(), label)
            by[key] = by.get(key, 0) + 1
    return issues, by


def header(doc_id, title, commit, label, today):
    applies = "main at baseline commit" if label == "unreleased" else label
    return [f"# foundation-refrigeration {title}", "", "| Field | Value |", "|---|---|",
            f"| Document ID | {doc_id} |", "| Version | 1.0 |", "| Status | Draft |", f"| Owner | {OWNER} |",
            f"| Date | {today} |", f"| Baseline commit | {commit} |",
            f"| Applies to | foundation-refrigeration {applies} |",
            "| Classification | Self-assessed Class E analog; not safety-critical (see SMP §1) |", "", DISCLAIMER, "",
            f"Generated by `python -B tools/gen_reports.py --label {label}`. Do not edit by hand; rerun the generator.",
            ""]


def footer(today, commit, change):
    return ["", "## Change history", "", "| Version | Date | Commit | Change | Reviewed in |", "|---|---|---|---|---|",
            f"| 1.0 | {today} | {commit[:7]} | {change} | PR adding the NASA-standard documentation set |"]


def verdict(runs, problems, gates):
    reasons = []
    for run in runs:
        if run["returncode"] != 0:
            reasons.append(f'`{run["command"]}` exited {run["returncode"]:d}')
        if run["ran"] == 0:
            reasons.append(f'`{run["command"]}` ran no tests')
        if len(run["results"]) != run["ran"]:
            reasons.append(f'`{run["command"]}` ran {run["ran"]:d} tests but {len(run["results"]):d} outcomes '
                           "were recorded")
        reasons += [f'`{run["command"]}`: `{ref}` {outcome}'
                    for ref, outcome in sorted(run["results"].items()) if outcome != "ok"]
    if len({frozenset(run["results"]) for run in runs}) > 1:
        reasons.append("the normal and optimized runs recorded different tests")
    if problems:
        reasons.append(f"the trace check reported {len(problems):d} problem(s)")
    unrun = []
    for name, status, detail in gates:
        if status == "not run":
            unrun.append(name)
        elif status != "passed":
            reasons.append(f"{name} failed: {detail}")
    return not reasons, reasons, unrun


def write_str(label, commit, dirty, today, runs, trace, gates):
    problems, summary = trace.check()
    mapping = requirement_map(trace)
    srs = trace.SRS.read_text()
    gaps = sorted(set(re.findall(r"GAP-REF-\d{3}", srs)))
    tbd = len(re.findall(r"\bTBD\b(?! / question)", srs))
    lines = source_lines()
    issues = issue_counts()
    merged = gh("pr", "list", "--state", "merged", "--limit", "500", "--json", "number")
    normal, optimized = runs
    passed, reasons, unrun = verdict(runs, problems, gates)
    if not passed:
        conclusion = f'FAILED: {"; ".join(reasons)}'
    elif unrun:
        conclusion = ("every test passed, every gate that ran passed and the trace check found no problems; not run, "
                      f'so not passed: {", ".join(unrun)}')
    else:
        conclusion = "every test passed, every gate passed and the trace check found no problems"
    gap_ids = ", ".join(gaps) or "none"
    out = header(f"FREFRIG-STR-{label.upper()}", f"software test report {label}", commit, label, today)
    out += ["## 1. Summary", "",
            f"- Conclusion: {conclusion}.",
            (f"- Remaining deficiencies and limitations: {len(gaps):d} untested behaviours are listed as gaps in the "
            f"[requirements](../../requirements/requirements.md#9-untested-behaviour-gaps) ({gap_ids}). No test "
            "exercises a live host; the Cstack side of the interface is verified in the Cstack repository."),
            ("- Test-environment impact: tests read only files in the repository and start the bridge as a child "
            "process. No network or external service is used."), "",
            "## 2. Test log", "", "| Item | Value |", "|---|---|",
            f'| Commit | `{commit}`{" (working tree had uncommitted changes)" if dirty else ""} |',
            f'| Date (UTC) | {datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d %H:%M")} |',
            f"| Environment | {platform.system()} {platform.machine()}, CPython {platform.python_version()} |",
            "| Run by | operator, `tools/gen_reports.py` (local run, not CI) |"]
    for run in runs:
        out.append(f'| `{run["command"]}` | exit {run["returncode"]:d}, {run["tail"]}; {run["ran"]:d} tests in '
                   f'{run["seconds"]} s; stderr SHA-256 `{run["digest"]}` |')
    out += [(f'| `python -B tools/check_trace.py` | {len(problems):d} problem(s); {summary["requirements"]:d} '
            f'requirements, {summary["traced"]:d} traced; {summary["tests"]:d} tests, {summary["tests_traced"]:d} '
            f'traced, {summary["tests_supporting"]:d} supporting; {summary["markdown_files"]:d} markdown files '
            "link-checked |")]
    for name, status, detail in gates:
        out.append(f"| {name} | {status}: {detail} |")
    out += ["", "## 3. Results", "", "| Test | Requirements | Normal | Optimized (-O) |", "|---|---|---|---|"]
    for ref in sorted(set(normal["results"]) | set(optimized["results"])):
        reqs = ", ".join(mapping.get(ref, [])) or "supporting"
        out.append(f'| `{ref}` | {reqs} | {normal["results"].get(ref, "not run")} | '
                   f'{optimized["results"].get(ref, "not run")} |')
    out += ["", "## 4. Problems and deviations", ""]
    failures = [(ref, outcome) for run in runs for ref, outcome in run["results"].items() if outcome != "ok"]
    if not passed or unrun:
        out += ["| Item | Description |", "|---|---|"]
        out += [f"| `{ref}` | {outcome} |" for ref, outcome in failures]
        out += ["| trace | " + p.replace("|", "\\|") + " |" for p in problems]
        out += ["| verdict | " + r.replace("|", "\\|") + " |" for r in reasons]
        out += [f"| {name} | not run |" for name in unrun]
    else:
        out.append("None. No test failed or was skipped, every gate passed, and the trace check reported no problems.")
    tallies = {name: (run["ran"], sum(v == "ok" for v in run["results"].values()),
                      sum(v != "ok" for v in run["results"].values()), run["command"])
               for name, run in (("normal", normal), ("optimized", optimized))}
    out += ["", "## 5. Metrics", "", "| Measure | Value | Command |", "|---|---|---|",
            *(f"| Tests run / passed / failed ({name}) | {ran:d} / {ok:d} / {failed:d} | `{command}` |"
              for name, (ran, ok, failed, command) in tallies.items()),
            (f'| Requirements total / traced to a test or inspection | {summary["requirements"]:d} / '
            f'{summary["traced"]:d} | `python -B tools/check_trace.py` |'),
            f"| Untested behaviour gaps | {len(gaps):d} | count of `GAP-REF-` IDs in the SRS |",
            f"| TBD markers in the SRS | {tbd:d} | count of `TBD` in the SRS |",
            "| Requirement changes since previous tag | no previous tag | `git tag --list` |"]
    if issues is None:
        out.append("| Issues by state and severity | not queried (gh unavailable) | `gh issue list` |")
    else:
        items, by = issues
        text = ", ".join(f"{state} {sev}: {n:d}" for (state, sev), n in sorted(by.items())) or "none"
        out.append(f"| Issues by state and severity (total {len(items):d}) | {text} | `gh issue list --state all` |")
    merged_count = "not queried" if merged is None else len(json.loads(merged))
    out.append(f"| PRs merged (all time) | {merged_count} | `gh pr list --state merged` |")
    out.append("| Coverage | not measured: no coverage tool is pinned; see test plan §5 | \u2014 |")
    line_counts = ", ".join(f"{kind} {count:d}" for kind, count in sorted(lines.items()))
    out.append(f"| Source lines by type (tracked files) | {line_counts} | `git ls-files` + line count |")
    out += ["", "## 6. Rationale for decisions", "",
            ("The report is generated from a local run on the operator's machine with the same commands CI runs. "
            "CI results for the same commit are on the pull request's checks page. Coverage is not measured because "
            "the project is standard-library only and no coverage tool is pinned.")]
    out += footer(today, commit, "Generated test report")
    (REPORTS / f"STR-{label}.md").write_text("\n".join(out) + "\n")
    return passed


def write_vdd(label, commit, today):
    manifest_raw = (ROOT / "SOURCE-MANIFEST.json").read_bytes()
    manifest = json.loads(manifest_raw)
    inventory = json.dumps(tool_definitions(), ensure_ascii=True, allow_nan=False, sort_keys=True,
                           separators=(",", ":")).encode("ascii")
    tags = git("tag", "--list").split()
    previous = tags[-1] if tags else None
    log = git("log", "--first-parent", "--format=%h %s", *([f"{previous}..{commit}"] if previous else [commit]))
    groups = {}
    for name in manifest["files"]:
        top = name.split("/")[0] if "/" in name else "(root files)"
        groups[top] = groups.get(top, 0) + 1
    out = header(f"FREFRIG-VDD-{label.upper()}", f"version description {label}", commit, label, today)
    out += ["## 1. Identification", "", "| Item | Value |", "|---|---|",
            "| Name | foundation-refrigeration |",
            f"| Version | {__version__} (`foundation_refrigeration.__version__`) |",
            f'| Tag | {label if label != "unreleased" else "none (unreleased main)"} |',
            f"| Commit | `{commit}` |", f'| Previous tag | {previous or "none"} |', f"| Date | {today} |", "",
            "## 2. Contents", "",
            ("Source tree only. There is no built package and no installer. Files covered by `SOURCE-MANIFEST.json` "
            "by top-level path:"), "", "| Path | Files |", "|---|---|"]
    out += [f"| `{top}` | {count:d} |" for top, count in sorted(groups.items())]
    out += ["", "No third-party code is vendored. The runtime uses the Python standard library only.", "",
            "## 3. Build and install", "", "```sh",
            "git clone https://github.com/Akilleez-QA/foundation-refrigeration", "cd foundation-refrigeration",
            f"git checkout {commit}", "python -B -m unittest discover -s tests -t .",
            "python -B tools/build_manifest.py", "git diff --exit-code SOURCE-MANIFEST.json", "```", "",
            ("Requires Python 3.11 or newer (CI uses 3.12). Start the bridge with "
            "`python -B -m foundation_refrigeration_bridge` from the repository root."), "",
            "## 4. Integrity", "", "| Item | Value |", "|---|---|",
            f"| `SOURCE-MANIFEST.json` SHA-256 | `{hashlib.sha256(manifest_raw).hexdigest()}` |",
            f'| Manifest file count | {len(manifest["files"]):d} |',
            f"| Canonical tool inventory SHA-256 | `{hashlib.sha256(inventory).hexdigest()}` |", "",
            ("These are the three values a host pins (see the [interface control document](../icd/icd-cstack.md)). "
            "Per-file digests are in `SOURCE-MANIFEST.json`; data-file digests are in the "
            "[reference data provenance](../data/reference-data.md) table."), "",
            "## 5. Changes since previous tag", "",
            "No previous tag exists, so this lists every first-parent commit up to the identified commit:" if not
            previous else f"First-parent commits since `{previous}`:", "", "```"]
    out += [*log.splitlines(), "```", "", "See [CHANGELOG.md](../../CHANGELOG.md) for the summarized changes.", "",
            "## 6. Open problems and workarounds", ""]
    issues = issue_counts()
    if issues is None:
        out.append("Not queried: `gh` was unavailable when this was generated.")
    else:
        open_items = [i for i in issues[0] if i["state"].lower() == "open"]
        out.append(f"Open issues at generation: {len(open_items):d} (`gh issue list --state open`).")
    out += ["", "## 7. Documentation baseline", "", "| Document | Baseline commit |", "|---|---|"]
    for name in CONTROL_DOCS:
        match = re.search(r"^\| Baseline commit \| (\S+) \|$", (ROOT / name).read_text(), re.MULTILINE)
        out.append(f'| [{name}](../../{name}) | {match.group(1) if match else "not recorded"} |')
    out += ["", "## 8. Verification and scans", "",
            (f"Test and trace results for this commit: [STR-{label}](../verification/reports/STR-{label}.md). "
            "The secret scan result is recorded in the same report's test log.")]
    out += footer(today, commit, "Generated version description")
    (RELEASES / f"VDD-{label}.md").write_text("\n".join(out) + "\n")


def gitleaks_gate():
    if shutil.which("gitleaks") is None:
        return ("gitleaks", "not run", "gitleaks not installed")
    proc = subprocess.run(["gitleaks", "git", "--redact", "--no-banner", "--exit-code", "1", "--config",
                           ".gitleaks.toml", "."], check=False, cwd=ROOT, capture_output=True, text=True)
    summary = re.sub(r"\x1b\[[0-9;]*m", "", proc.stdout + proc.stderr).strip().splitlines()
    return ("`gitleaks git --redact --no-banner --exit-code 1 --config .gitleaks.toml .`",
            "passed" if proc.returncode == 0 else "failed",
            f'exit {proc.returncode:d}; {summary[-1] if summary else "no output"}')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", default="unreleased")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9.\-]+", args.label):
        raise SystemExit("label must be lower-case letters, digits, dots or hyphens")
    commit = git("rev-parse", "HEAD")
    dirty = bool(git("status", "--porcelain"))
    today = datetime.date.today().isoformat()
    runs = (run_suite(False), run_suite(True))
    manifest = subprocess.run([sys.executable, "-B", "tools/build_manifest.py"], check=False, cwd=ROOT, capture_output=True,
                              text=True)
    diff = subprocess.run(["git", "diff", "--exit-code", "--quiet", "SOURCE-MANIFEST.json"], check=False, cwd=ROOT)
    docs = subprocess.run([sys.executable, "-B", "tools/gen_docs.py", "--check"], check=False, cwd=ROOT, capture_output=True)
    gates = [("`python -B tools/build_manifest.py` then `git diff --exit-code SOURCE-MANIFEST.json`",
              "passed" if manifest.returncode == 0 and diff.returncode == 0 else "failed",
              f"exit {manifest.returncode:d} / {diff.returncode:d}"),
             ("`python -B tools/gen_docs.py --check`", "passed" if docs.returncode == 0 else "failed",
              f"exit {docs.returncode:d}"),
             gitleaks_gate()]
    REPORTS.mkdir(parents=True, exist_ok=True)
    RELEASES.mkdir(parents=True, exist_ok=True)
    passed = write_str(args.label, commit, dirty, today, runs, trace_module(), gates)
    write_vdd(args.label, commit, today)
    print(json.dumps({"commit": commit, "dirty": dirty, "passed": passed,
                      "normal": runs[0]["returncode"], "optimized": runs[1]["returncode"],
                      "gates": {name: status for name, status, _ in gates}}))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
