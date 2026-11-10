import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def tool(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DocumentationTraceTests(unittest.TestCase):
    def test_requirements_trace_to_tests_design_and_live_links(self):
        problems, summary = tool("check_trace").check()
        self.assertEqual(problems, [])
        self.assertEqual(summary["requirements"], summary["traced"])

    def test_manifest_copy_passes_its_own_trace_check(self):
        files = json.loads((ROOT / "SOURCE-MANIFEST.json").read_text())["files"]
        with tempfile.TemporaryDirectory() as temp:
            copy = Path(temp)
            for name in [*files, "SOURCE-MANIFEST.json"]:
                (copy / name).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / name, copy / name)
            proc = subprocess.run([sys.executable, "-B", "tools/check_trace.py"], cwd=copy, capture_output=True,
                                  text=True, timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_generated_reference_documents_are_current(self):
        gen = tool("gen_docs")
        for path, text in ((gen.CATALOG, gen.catalog()), (gen.DATA, gen.reference_data())):
            with self.subTest(path=path.name):
                self.assertEqual(path.read_text(), text)
        self.check_report_verdicts()

    def check_report_verdicts(self):
        reports = tool("gen_reports")
        trace = tool("check_trace")
        ref = "tests/test_bridge.py::ReceiptTests.test_tool_errors_are_errors_not_results"

        def run(optimized, outcome="ok"):
            command = "python -B%s -m unittest discover -s tests -t ." % (" -O" if optimized else "")
            return {"command": command, "returncode": 0, "results": {ref: outcome}, "ran": 1, "seconds": "0.1",
                    "digest": "0" * 64, "tail": "OK"}

        manifest = ("`python -B tools/build_manifest.py` then `git diff --exit-code SOURCE-MANIFEST.json`",
                    "passed", "exit 0 / 0")
        docs = ("`python -B tools/gen_docs.py --check`", "passed", "exit 0")
        leaks = ("`gitleaks git --redact --no-banner --exit-code 1 --config .gitleaks.toml .`", "passed",
                 "exit 0; no leaks found")
        failed_leaks = (leaks[0], "failed", "exit 1; leaks found: 1")
        unrun_leaks = ("gitleaks", "not run", "gitleaks not installed")
        cases = (
            ("clean", (run(False), run(True)), [manifest, docs, leaks], True),
            ("gitleaks found a secret", (run(False), run(True)), [manifest, docs, failed_leaks], False),
            ("manifest changed", (run(False), run(True)), [(manifest[0], "failed", "exit 0 / 1"), docs, leaks],
             False),
            ("generated documents stale", (run(False), run(True)), [manifest, (docs[0], "failed", "exit 1"), leaks],
             False),
            ("skipped test", (run(False, "skipped"), run(True)), [manifest, docs, leaks], False),
            ("skipped optimized test", (run(False), run(True, "skipped")), [manifest, docs, leaks], False),
            ("unparsed outcome", (run(False), {**run(True), "results": {}}), [manifest, docs, leaks], False),
            ("gitleaks not installed", (run(False), run(True)), [manifest, docs, unrun_leaks], True),
        )
        original_reports, original_gh = reports.REPORTS, reports.gh
        try:
            reports.gh = lambda *args: None
            for name, runs, gates, expected in cases:
                with self.subTest(report=name), tempfile.TemporaryDirectory() as temp:
                    reports.REPORTS = Path(temp)
                    passed = reports.write_str("unreleased", "0" * 40, False, "2026-11-09", runs, trace, gates)
                    text = (Path(temp) / "STR-unreleased.md").read_text()
                    conclusion = next(line for line in text.splitlines() if line.startswith("- Conclusion:"))
                    self.assertIs(passed, expected)
                    self.assertEqual("FAILED" in conclusion, not expected)
                    self.assertEqual("gitleaks" in conclusion, gates[2] is not leaks)
        finally:
            reports.REPORTS, reports.gh = original_reports, original_gh


if __name__ == "__main__":
    unittest.main()
