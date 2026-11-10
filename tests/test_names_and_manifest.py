import ast
import hashlib
import json
from pathlib import Path
import unittest

import foundation_refrigeration
import foundation_refrigeration_bridge
from foundation_refrigeration_bridge import schemas

ROOT = Path(__file__).resolve().parents[1]


def foundation_files():
    return sorted(p for p in ROOT.rglob("*") if p.is_file() and "__pycache__" not in p.parts and ".git" not in p.parts
                  and p.relative_to(ROOT).parts[0] != ".github" and p.suffix != ".pyc" and p.name not in ("SOURCE-MANIFEST.json", "PR_BODY.md"))


class ManifestTests(unittest.TestCase):
    def test_source_manifest_is_exact(self):
        manifest = json.loads((ROOT / "SOURCE-MANIFEST.json").read_text())
        self.assertEqual(manifest["schema"], "foundation-refrigeration-source-manifest/1")
        actual = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in foundation_files()}
        self.assertEqual(manifest["files"], actual)

    def test_version_is_written_identically_everywhere(self):
        tree = ast.parse((ROOT / "tools" / "build_manifest.py").read_text(encoding="utf-8"))
        written = [value.value for node in ast.walk(tree) if isinstance(node, ast.Dict)
                   for key, value in zip(node.keys, node.values)
                   if isinstance(key, ast.Constant) and key.value == "version" and isinstance(value, ast.Constant)]
        self.assertEqual(len(written), 1)
        self.assertRegex(foundation_refrigeration.__version__, r"\A\d+\.\d+\.\d+\Z")
        self.assertEqual({foundation_refrigeration.__version__, foundation_refrigeration_bridge.__version__,
                          schemas.VERSION, written[0]}, {foundation_refrigeration.__version__})
        self.assertEqual(json.loads((ROOT / "SOURCE-MANIFEST.json").read_text())["version"],
                         foundation_refrigeration.__version__)


if __name__ == "__main__":
    unittest.main()
