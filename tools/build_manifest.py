import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_DIRS = {"__pycache__", ".git", ".ruff_cache"}


def covered(path):
    rel = path.relative_to(ROOT)
    return (path.is_file() and not EXCLUDED_DIRS & set(rel.parts) and rel.parts[0] != ".github"
            and path.suffix != ".pyc" and path.name not in ("SOURCE-MANIFEST.json", "PR_BODY.md"))


def main():
    files = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in sorted(ROOT.rglob("*")) if covered(p)}
    raw = (json.dumps({"schema": "foundation-refrigeration-source-manifest/1", "version": "0.1.0", "files": files},
                      sort_keys=True, indent=2) + "\n").encode()
    (ROOT / "SOURCE-MANIFEST.json").write_bytes(raw)
    print(json.dumps({"files": len(files), "sha256": hashlib.sha256(raw).hexdigest()}))


if __name__ == "__main__":
    main()
