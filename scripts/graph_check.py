#!/usr/bin/env python
# ruff: noqa: T201, S324, D103, PTH207, PLR2004
# CLI tool: printing IS the output; md5 here is a change fingerprint, not a security hash.
"""Reconcile PROJECT_GRAPH.md against what is actually on disk.

Run this BEFORE citing anything in the graph. A node whose fingerprint has moved is unverified,
not fact.

    python graph_check.py                        # full reconcile, exits non-zero on drift
    python graph_check.py --quiet                 # only print problems
    python graph_check.py --fast                  # skip slow project-specific checks
    python graph_check.py --fingerprint <path>... # print code_sha for paths
    python graph_check.py --tracked "src/**/*.py" "notebooks/**/*.ipynb"

Nothing here is specific to one project. Which files are expected to have nodes comes from, in
order of precedence: --tracked, then a `graph_check.json` sitting beside PROJECT_GRAPH.md, then a
generic default. Put project-specific checks in a separate copy rather than editing this one.

    graph_check.json:  {"tracked": ["notebooks/**/*.ipynb", "src/**/*.py"],
                        "skip": ["vendor", "generated"],
                        "off_repo_prefixes": ["S3:", "DRIVE:"]}

Checks performed:
  1. missing-path      a `file:` a node points at no longer exists
  2. bad-edge          a `to:` / `from:` id does not resolve to a node
  3. drift             the node's file changed since `checked: ... code_sha=`
  4. un-noded          a notebook or script on disk has no node at all
  5. missing-io        an extractor sees a path in a file that the graph does not record. Optional:
                       only runs if an `extract_io.py` exposing `analyze(path) -> {"all_paths": [...]}`
                       is found anywhere in the repo.
"""

from __future__ import annotations

import argparse
import os
import glob
import hashlib
import json
import re
import sys
from fnmatch import fnmatch
from pathlib import Path

REPO = Path(os.environ.get("GRAPH_REPO", Path.cwd()))
GRAPH = REPO / "PROJECT_GRAPH.md"

# Defaults, deliberately generic. Override per project via graph_check.json or --tracked; see the
# module docstring. Anything hardcoded to one repo's layout belongs in that repo's copy, not here.
DEFAULT_OFF_REPO = ("DRIVE:", "HF:", "EXTERNAL:", "S3:", "GCS:", "URL:")
DEFAULT_TRACKED = ("**/*.ipynb", "**/*.py")
# Directories that are never the project's own source, so they must not raise `un-noded`.
DEFAULT_SKIP = (
    ".ipynb_checkpoints", "__pycache__", ".out.ipynb", ".git/", ".venv/", "venv/", "env/",
    "node_modules/", "site-packages/", "dist-packages/", ".tox/", ".mypy_cache/", ".pytest_cache/",
    "build/", "dist/", ".eggs/", "htmlcov/",
)


def _load_config(repo: Path) -> dict:
    """Read graph_check.json beside PROJECT_GRAPH.md, if the project ships one."""
    cfg_path = repo / "graph_check.json"
    if cfg_path.exists():
        try:
            return json.loads(cfg_path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            print(f"warning: ignoring unreadable {cfg_path.name}: {exc}")
    return {}


CONFIG = _load_config(Path(os.environ.get("GRAPH_REPO", Path.cwd())))
OFF_REPO = tuple(CONFIG.get("off_repo_prefixes", DEFAULT_OFF_REPO))
TRACKED_GLOBS = tuple(CONFIG.get("tracked", DEFAULT_TRACKED))
SKIP = tuple(DEFAULT_SKIP) + tuple(CONFIG.get("skip", ()))

NODE_RE = re.compile(r"^Node\(\s*$(.*?)^\)\s*$", re.M | re.S)
FIELD_RE = re.compile(r"^\s{2}(\w+):\s*(.*)$")
SHA_RE = re.compile(r"code_sha=([0-9a-f,]+|n/a)")


# --------------------------------------------------------------------------- fingerprinting


def code_text(path: Path) -> str:
    """Notebook code cells only, so re-running a notebook is not drift; whole file otherwise."""
    if path.suffix == ".ipynb":
        nb = json.loads(path.read_text(errors="replace"))
        return "\n".join(
            "".join(c["source"]) for c in nb.get("cells", []) if c.get("cell_type") == "code"
        )
    return path.read_text(errors="replace")


def code_sha(path: Path) -> str:
    return hashlib.md5(code_text(path).encode("utf-8", "replace")).hexdigest()[:8]


# --------------------------------------------------------------------------- graph parsing


def parse_nodes(text: str) -> list[dict]:
    nodes = []
    for block in NODE_RE.findall(text):
        node: dict[str, str] = {}
        key = None
        for line in block.splitlines():
            m = FIELD_RE.match(line)
            if m:
                key = m.group(1)
                node[key] = m.group(2).strip()
            elif key and line.strip():
                node[key] += " " + line.strip()
        if "id" in node:
            nodes.append(node)
    return nodes


def edge_ids(value: str) -> list[str]:
    return [x.strip() for x in value.strip().strip("[]").split(",") if x.strip()]


def expand(spec: str) -> list[str]:
    """Turn one `file:` value into concrete candidate paths.

    Handles ` · ` separated lists, `{a,b}` brace sets, and `{placeholder}` -> `*`.
    """
    out = []
    for part in spec.split("·"):
        head = part.split("<-")[0].strip()
        if not head or head.startswith(OFF_REPO) or head == "n/a":
            continue
        variants = [head]
        while any("{" in v and "," in v.split("{", 1)[1].split("}", 1)[0] for v in variants):
            nxt = []
            for v in variants:
                if "{" in v and "," in v.split("{", 1)[1].split("}", 1)[0]:
                    pre, rest = v.split("{", 1)
                    body, post = rest.split("}", 1)
                    nxt.extend(f"{pre}{opt}{post}" for opt in body.split(","))
                else:
                    nxt.append(v)
            variants = nxt
        # remaining single-token braces are placeholders like {lo} or {first_index}
        out.extend(re.sub(r"\{[^}]*\}", "*", v) for v in variants)
    return out


# --------------------------------------------------------------------------- checks


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quiet", action="store_true", help="only print problems")
    ap.add_argument("--fingerprint", nargs="*", help="print code_sha for these paths and exit")
    ap.add_argument("--tracked", nargs="*", metavar="GLOB",
                    help="globs for files expected to have nodes; overrides graph_check.json")
    ap.add_argument("--fast", action="store_true",
                    help="skip the optional extractor cross-check, which is the slow one. Use in a "
                         "hook, where the cost is paid on every tool call.")
    args = ap.parse_args()

    global TRACKED_GLOBS  # noqa: PLW0603 - a CLI override of a module default
    if args.tracked:
        TRACKED_GLOBS = tuple(args.tracked)

    if args.fingerprint is not None:
        for p in args.fingerprint:
            path = Path(p)
            print(f"{code_sha(path)}  {p}" if path.exists() else f"MISSING   {p}")
        return 0

    if not GRAPH.exists():
        print(f"FATAL: {GRAPH} not found")
        return 2

    nodes = parse_nodes(GRAPH.read_text())
    ids = {n["id"] for n in nodes}
    problems: list[tuple[str, str]] = []

    if not args.quiet:
        print(f"{len(nodes)} nodes parsed from {GRAPH.name}\n")

    # ---- 1. missing paths, 3. drift
    noded_paths: set[str] = set()
    for n in nodes:
        spec = n.get("file", "")
        candidates = expand(spec)
        for cand in candidates:
            matches = glob.glob(str(REPO / cand), recursive=True)
            if not matches:
                problems.append(("missing-path", f"{n['id']}: no such path -> {cand}"))
                continue
            for m in matches:
                noded_paths.add(str(Path(m).resolve()))

        # drift: only for nodes naming exactly one existing code file
        declared = SHA_RE.search(n.get("checked", ""))
        if declared and declared.group(1) != "n/a":
            want = declared.group(1).split(",")
            real = []
            for cand in candidates:
                for m in sorted(glob.glob(str(REPO / cand), recursive=True)):
                    mp = Path(m)
                    if mp.suffix in (".ipynb", ".py") and mp.is_file():
                        real.append(code_sha(mp))
            if real and sorted(real) != sorted(want):
                problems.append(
                    ("drift", f"{n['id']}: code_sha recorded {','.join(want)} but file is {','.join(real)}")
                )

    # ---- 2. unresolved edges
    for n in nodes:
        for field in ("to", "from"):
            problems.extend(
                ("bad-edge", f"{n['id']}.{field} -> unknown id '{target}'")
                for target in edge_ids(n.get(field, ""))
                if target not in ids
            )

    # ---- 4. files on disk with no node
    on_disk = [m for pat in TRACKED_GLOBS for m in glob.glob(str(REPO / pat), recursive=True)]
    graph_text = GRAPH.read_text()
    for f in sorted(set(on_disk)):
        if any(s in f for s in SKIP):
            continue
        rel = str(Path(f).relative_to(REPO))
        if str(Path(f).resolve()) in noded_paths or rel in graph_text or Path(rel).name in graph_text:
            continue
        problems.append(("un-noded", f"{rel} exists on disk but no node references it"))

    # ---- 5. IO the graph does not record
    known_names = {Path(c).name for n in nodes for c in expand(n.get("file", ""))}
    try:
        if args.fast:
            raise ImportError("skipped by --fast")
        # Find the extractor wherever the project keeps it, rather than assuming a directory.
        found = [c for c in glob.glob(str(REPO / "**" / "extract_io.py"), recursive=True)
                 if not any(s in c for s in SKIP)]
        if not found:
            raise ImportError("no extract_io.py in this repo")
        sys.path.insert(0, str(Path(found[0]).parent))
        import extract_io

        for pat in TRACKED_GLOBS:
            for f in sorted(glob.glob(str(REPO / pat), recursive=True)):
                if any(s in f for s in SKIP):
                    continue
                rel = str(Path(f).relative_to(REPO))
                if rel not in graph_text and Path(rel).name not in graph_text:
                    continue  # already reported as un-noded
                try:
                    seen = extract_io.analyze(f)["all_paths"]
                except Exception:  # noqa: BLE001, S112 - a malformed notebook is not this tool's problem
                    continue
                for p in seen:
                    name = Path(p).name
                    if len(name) <= 6 or "{" in name:
                        continue
                    # the graph is allowed to write `{a,b}` sets and `{placeholder}` wildcards, so
                    # match against the expanded basenames rather than the raw markdown text
                    if name in graph_text or any(fnmatch(name, pat) for pat in known_names):
                        continue
                    problems.append(("missing-io", f"{rel} touches '{name}' — not in the graph"))
    except ImportError:
        pass  # extract_io.py is optional; the other four checks still run

    # ---- report
    order = ["missing-path", "bad-edge", "drift", "un-noded", "missing-io"]
    problems.sort(key=lambda p: order.index(p[0]) if p[0] in order else 99)
    if not problems:
        print("clean — graph agrees with disk")
        return 0
    kinds: dict[str, int] = {}
    for kind, msg in problems:
        kinds[kind] = kinds.get(kind, 0) + 1
        print(f"[{kind}] {msg}")
    print("\n" + ", ".join(f"{k}: {v}" for k, v in kinds.items()))
    print(f"{len(problems)} problem(s). Repair the affected nodes before citing the graph.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
