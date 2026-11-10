import ast
import hashlib
import importlib.util
import json
import unittest
from pathlib import Path
from unittest import mock

import foundation_refrigeration
import foundation_refrigeration_bridge
from foundation_refrigeration_bridge import schemas

ROOT = Path(__file__).resolve().parents[1]


def foundation_files():
    return sorted(p for p in ROOT.rglob("*") if p.is_file()
                  and not {"__pycache__", ".git", ".ruff_cache"} & set(p.relative_to(ROOT).parts)
                  and p.relative_to(ROOT).parts[0] != ".github" and p.suffix != ".pyc"
                  and p.name not in ("SOURCE-MANIFEST.json", "PR_BODY.md"))


def build_manifest_module():
    spec = importlib.util.spec_from_file_location("build_manifest", ROOT / "tools" / "build_manifest.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ManifestTests(unittest.TestCase):
    def test_static_analysis_cache_is_outside_the_manifest(self):
        builder = build_manifest_module()
        with mock.patch.object(Path, "is_file", return_value=True):
            self.assertFalse(builder.covered(ROOT / ".ruff_cache" / "0.17.0" / "entry"))
            self.assertFalse(builder.covered(ROOT / ".ruff_cache" / "CACHEDIR.TAG"))
            self.assertFalse(builder.covered(ROOT / "tools" / "__pycache__" / "x.cpython-312.pyc"))
            self.assertTrue(builder.covered(ROOT / "tools" / "build_manifest.py"))
            self.assertTrue(builder.covered(ROOT / "AGENTS.md"))
        self.assertFalse(any(".ruff_cache" in p.parts for p in foundation_files()))


    def test_source_manifest_is_exact(self):
        manifest = json.loads((ROOT / "SOURCE-MANIFEST.json").read_text())
        self.assertEqual(manifest["schema"], "foundation-refrigeration-source-manifest/1")
        actual = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in foundation_files()}
        self.assertEqual(manifest["files"], actual)

    def test_version_is_written_identically_everywhere(self):
        tree = ast.parse((ROOT / "tools" / "build_manifest.py").read_text(encoding="utf-8"))
        written = [value.value for node in ast.walk(tree) if isinstance(node, ast.Dict)
                   for key, value in zip(node.keys, node.values, strict=True)
                   if isinstance(key, ast.Constant) and key.value == "version" and isinstance(value, ast.Constant)]
        self.assertEqual(len(written), 1)
        self.assertRegex(foundation_refrigeration.__version__, r"\A\d+\.\d+\.\d+\Z")
        self.assertEqual({foundation_refrigeration.__version__, foundation_refrigeration_bridge.__version__,
                          schemas.VERSION, written[0]}, {foundation_refrigeration.__version__})
        self.assertEqual(json.loads((ROOT / "SOURCE-MANIFEST.json").read_text())["version"],
                         foundation_refrigeration.__version__)


if __name__ == "__main__":
    unittest.main()
