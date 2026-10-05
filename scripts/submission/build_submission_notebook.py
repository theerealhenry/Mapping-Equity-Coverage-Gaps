"""
scripts/submission/build_submission_notebook.py — Stage 7 Step 12.

Owned by Stage 7. Generates the flattened reproduction notebook (`submission/coverage_gap_
solution.ipynb`) from the approved, frozen `src/gaps.py` scoring entry point: walks its real
`from src.X import name` dependency graph automatically (no hand-maintained symbol list to drift
from the real modules), inlines every symbol actually needed, strips every project-local import,
writes the flattened notebook, executes it end-to-end against the Step 2 golden-case fixtures
(`tests/test_gap_arithmetic.py`'s own hand-computed values, re-asserted here), and validates the
output schema. The flattened notebook is a GENERATED artifact, never hand-edited — regenerate it
by re-running this script if `src/gaps.py` (or anything it imports) changes.

Scope note (Step 12's "inline the necessary functions", read literally, not by rote): the actual
import chain starting at `score_all_regions`/`score_region` is `src.gaps` -> `src.features`
(`assert_competition_only`) -> `src.schemas` (`COMPETITION_ALLOWED_COLUMNS`) -> `src.config`
(`REGIONS`). `src/geometry.py` and `src/io.py` are Stage 6's spatial-assignment and data-loading
layer — by `gaps.py`'s own module docstring ("gaps.py owns the formula and orchestration,
geometry.py owns every spatial operation"), that layer already ran once to materialize
`data/processed/<region>-tract-features.parquet`, and the frozen *scoring* computation
(`scoring/v1/checksum.txt`'s subject) reads only those tables. So nothing from `geometry.py`/
`io.py` is ever actually imported by the scoring entry point, and the dependency walk below
correctly inlines nothing from them — not an omission, a reflection of the real, already-frozen
architecture boundary.

Run with:
  python -m scripts.submission.build_submission_notebook
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
OUT_DIR = REPO_ROOT / "submission"
OUT_NOTEBOOK = OUT_DIR / "coverage_gap_solution.ipynb"

ENTRY_MODULE = "gaps"
ENTRY_NAMES = ["score_all_regions", "score_region", "capped_ratio_gap", "coverage_gap_score"]


def _source(modname: str) -> str:
    return (SRC / f"{modname}.py").read_text()


def _node_name(node: ast.stmt) -> str | None:
    """The single name a top-level statement defines, or None for anything else (module
    docstring, bare imports) -- shared by both the collection pass and the render pass so the
    two can never disagree about which nodes count (an earlier version of this script had
    `render()` only recognize `ast.Assign`, silently dropping `COMPETITION_ALLOWED_COLUMNS`'s
    `ast.AnnAssign` declaration from the output -- this helper is the fix, used in both places)."""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return node.name
    if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
        return node.targets[0].id
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return node.target.id
    return None


def _top_level_defs(tree: ast.Module) -> dict[str, ast.stmt]:
    """name -> its top-level def/class/assign node (module docstring and bare imports excluded
    by construction -- they're never a dict value here, so they're never emitted below)."""
    defs: dict[str, ast.stmt] = {}
    for node in tree.body:
        name = _node_name(node)
        if name is not None:
            defs[name] = node
    return defs


def _cross_module_import_map(tree: ast.Module) -> dict[str, tuple[str, str]]:
    """local name -> (src submodule, original name), for every `from src.X import name[ as
    local]` anywhere in the module (module-level AND nested inside a function body -- src.gaps
    and src.features both use function-local imports deliberately, to dodge circular imports;
    see src.features.assert_competition_only's own comment)."""
    out: dict[str, tuple[str, str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("src."):
            submod = node.module.split(".", 1)[1]
            for alias in node.names:
                out[alias.asname or alias.name] = (submod, alias.name)
    return out


def collect(
    modname: str,
    names: list[str],
    collected: dict[str, list[str]],
    seen: set[tuple[str, str]],
    module_deps: dict[str, set[str]],
) -> None:
    """Recursively pull every top-level symbol `names` needs -- transitively, across both
    same-module references (e.g. schemas.COMPETITION_ALLOWED_COLUMNS referencing schemas._GAP_
    RATIO_COLUMNS) and cross-module `from src.X import ...` references -- into `collected`. Also
    records each cross-module edge in `module_deps` (modname -> the modules it reaches into), used
    by `_module_render_order` to emit dependencies before dependents -- a Python module reference
    (e.g. `score_all_regions`'s `regions: list[str] = REGIONS` default) is only resolvable at
    exec-time if the module defining it was already executed, so render order is NOT just "however
    `collect` happened to visit things" the way dict-insertion order would otherwise imply."""
    tree = ast.parse(_source(modname), filename=f"{modname}.py")
    defs = _top_level_defs(tree)
    import_map = _cross_module_import_map(tree)
    collected.setdefault(modname, [])
    module_deps.setdefault(modname, set())

    for name in names:
        key = (modname, name)
        if key in seen:
            continue
        seen.add(key)
        if name not in defs:
            raise KeyError(f"src/{modname}.py has no top-level `{name}` to inline")
        collected[modname].append(name)

        node = defs[name]
        referenced = {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}
        for ref in sorted(referenced):
            if ref in defs and ref != name:
                collect(modname, [ref], collected, seen, module_deps)
            elif ref in import_map:
                dep_mod, dep_name = import_map[ref]
                module_deps[modname].add(dep_mod)
                collect(dep_mod, [dep_name], collected, seen, module_deps)


def _module_render_order(entry_modname: str, module_deps: dict[str, set[str]]) -> list[str]:
    """Dependency-first (topological) module order via DFS postorder -- every module a given
    module reaches into is emitted before it."""
    order: list[str] = []

    def visit(modname: str) -> None:
        if modname in order:
            return
        for dep in sorted(module_deps.get(modname, ())):
            visit(dep)
        order.append(modname)

    visit(entry_modname)
    return order


def render(collected: dict[str, list[str]], module_order: list[str]) -> str:
    """Emit each collected symbol's exact source text (via `ast.get_source_segment`, not a
    re-serialization -- comments and formatting survive), grouped by source module, with every
    `from src...`/module-docstring/bare-import line excluded by construction (only matched defs
    are ever looked up from `tree.body`)."""
    lines = [
        '"""',
        "GENERATED by scripts/submission/build_submission_notebook.py from the frozen src/ "
        "modules -- do not hand-edit. Regenerate if src/gaps.py (or anything it imports) "
        "changes. Uses only public packages (pandas); no project-local imports.",
        '"""',
        "from __future__ import annotations",
        "",
        "from pathlib import Path",
        "",
        "import pandas as pd",
        "",
    ]
    for modname in module_order:
        names = collected[modname]
        source = _source(modname)
        tree = ast.parse(source, filename=f"{modname}.py")
        defs = _top_level_defs(tree)
        lines.append(f"# {'=' * 76}")
        lines.append(f"# from src/{modname}.py")
        lines.append(f"# {'=' * 76}")
        for node in tree.body:
            if _node_name(node) in names:
                lines.append(_render_node_without_local_imports(source, node))
                lines.append("")
    return "\n".join(lines)


def _render_node_without_local_imports(source: str, node: ast.stmt) -> str:
    """Same text `ast.get_source_segment` would return, minus any nested `from src.X import ...`
    line (identified by AST line range, not by text matching, so a docstring that merely *mentions*
    such an import -- e.g. `assert_competition_only`'s own docstring -- is left untouched). Safe to
    drop: the imported name is already inlined as a module-level symbol by `render()` itself, so the
    nested import (there only in the original to dodge a circular import -- see
    `src.features.assert_competition_only`'s own comment) is redundant in the flattened file."""
    skip_lines: set[int] = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.ImportFrom) and sub.module and sub.module.startswith("src."):
            skip_lines.update(range(sub.lineno, sub.end_lineno + 1))

    all_lines = source.splitlines()
    kept = [
        line
        for i, line in enumerate(all_lines[node.lineno - 1 : node.end_lineno], start=node.lineno)
        if i not in skip_lines
    ]
    return "\n".join(kept)


# -------------------------------------------------------------------------------------------
# Step 2's golden-case fixture values, re-asserted against the flattened source (not re-derived
# from tests/test_gap_arithmetic.py by import -- the whole point of this notebook is that it has
# zero project-local imports, including of the test suite itself).
# -------------------------------------------------------------------------------------------
_SELF_CHECK_CELL = '''
# --- self-check: re-run Step 2's golden-case fixtures against the flattened functions above ---
assert capped_ratio_gap(overture=0, reference=100) == 1.0
assert capped_ratio_gap(overture=100, reference=100) == 0.0
assert capped_ratio_gap(overture=150, reference=100) == 0.0  # caps at 0, never negative
assert capped_ratio_gap(overture=0, reference=0) is None      # undefined, never zeroed (R-005)
assert capped_ratio_gap(overture=30, reference=40) == 0.25

assert coverage_gap_score({"transport_gap": 0.25, "building_gap": 0.75, "poi_gap": None}) == 0.5
assert abs(coverage_gap_score({"transport_gap": 0.2, "building_gap": 0.4, "poi_gap": 0.6}) - 0.4) < 1e-9
assert coverage_gap_score({"transport_gap": None, "building_gap": None, "poi_gap": None}) is None

_synthetic = pd.DataFrame([{
    "GEOID": "12345678900",
    "region": "eastern-ok",
    "transport_gap": 0.1, "transport_defined": True,
    "building_gap_centroid": 0.3, "building_gap_centroid_defined": True,
    "building_gap_intersection": 0.9, "building_gap_intersection_defined": True,
    "poi_gap_fire": 0.5, "poi_gap_fire_defined": True,
    "poi_gap_ems": 0.5, "poi_gap_ems_defined": True,
    "poi_gap_schools": 0.5, "poi_gap_schools_defined": True,
    "poi_gap_establishments": 0.5, "poi_gap_establishments_defined": True,
}])
_scored = score_region(_synthetic)
assert abs(_scored.loc[0, "building_gap"] - 0.3) < 1e-9  # frozen default: centroid, not intersection
_scored_override = score_region(_synthetic, building_gap_column="building_gap_intersection")
assert abs(_scored_override.loc[0, "building_gap"] - 0.9) < 1e-9

_expected_output_columns = {
    "GEOID", "region", "transport_gap", "transport_defined", "building_gap", "building_defined",
    "poi_gap", "poi_defined", "poi_gap_fire", "poi_gap_fire_defined", "poi_gap_ems",
    "poi_gap_ems_defined", "poi_gap_schools", "poi_gap_schools_defined",
    "poi_gap_establishments", "poi_gap_establishments_defined", "coverage_gap_score",
}
assert set(_scored.columns) == _expected_output_columns, (
    f"score_region output schema drifted: {set(_scored.columns) ^ _expected_output_columns}"
)
print("Flattened notebook self-check: PASS (Step 2 fixtures reproduced, output schema confirmed).")
'''


def build_notebook_json(flattened_source: str) -> dict:
    def code_cell(src: str) -> dict:
        return {
            "cell_type": "code",
            "metadata": {},
            "execution_count": None,
            "outputs": [],
            "source": src,
        }

    def md_cell(src: str) -> dict:
        return {"cell_type": "markdown", "metadata": {}, "source": src}

    header = (
        "# Coverage gap solution — flattened reproduction notebook\n\n"
        "Generated from the frozen scoring logic (`scoring/v1/checksum.txt` records the exact "
        "hashes). No project-local imports: every function below is the real `src/gaps.py` "
        "source, inlined verbatim by `scripts/submission/build_submission_notebook.py`. Do not "
        "hand-edit this file — regenerate it instead."
    )
    run_header = (
        "## Run against the real Stage 6 feature tables\n\n"
        "Requires `data/processed/<region>-tract-features.parquet` (produced by Stage 6, not "
        "part of this notebook) on the local filesystem at `data/processed/`."
    )
    run_cell = (
        "# PROCESSED_DIR above is relative (\"data/processed\") -- Jupyter's default working\n"
        "# directory is wherever this .ipynb file sits (submission/), not the repo root, so\n"
        "# find and switch to the repo root first rather than requiring the user to launch\n"
        "# Jupyter from a specific directory.\n"
        "import os\n"
        "\n"
        "def _find_repo_root(start: Path) -> Path:\n"
        "    for candidate in [start, *start.parents]:\n"
        "        if (candidate / \"data\" / \"processed\").is_dir():\n"
        "            return candidate\n"
        "    raise FileNotFoundError(\n"
        "        \"No data/processed/ directory found walking up from the current working \"\n"
        "        \"directory -- run this notebook from inside the project repo.\"\n"
        "    )\n"
        "\n"
        "os.chdir(_find_repo_root(Path.cwd()))\n"
        "print(f\"Working directory: {Path.cwd()}\")\n"
        "\n"
        "scored = score_all_regions()\n"
        "print(f\"Scored {len(scored)} tracts across {scored['region'].nunique()} regions.\")\n"
        "scored.head()"
    )
    cells = [
        md_cell(header),
        code_cell(flattened_source),
        md_cell("## Self-check: Step 2 golden-case fixtures, reproduced here"),
        code_cell(_SELF_CHECK_CELL.strip() + "\n"),
        md_cell(run_header),
        code_cell(run_cell),
    ]
    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def _execute_self_check_only(flattened_source: str) -> None:
    """Executes the flattened source + the self-check cell in a clean namespace -- the part of
    "end-to-end" that doesn't require the real (large, gitignored) Stage 6 parquet files to be
    present. This is what this script actually runs every time; the notebook's final `score_all_
    regions()` cell is left for a human to run where that data exists (same split the rest of
    this project already uses between fixture-based self-checks and real-data runs)."""
    namespace: dict = {}
    exec(compile(flattened_source, "<flattened>", "exec"), namespace)
    exec(compile(_SELF_CHECK_CELL, "<self-check>", "exec"), namespace)


def main() -> None:
    collected: dict[str, list[str]] = {}
    module_deps: dict[str, set[str]] = {}
    collect(ENTRY_MODULE, ENTRY_NAMES, collected, seen=set(), module_deps=module_deps)
    module_order = _module_render_order(ENTRY_MODULE, module_deps)
    flattened_source = render(collected, module_order)

    # "no import src...anywhere in the output" -- checked via AST (a real statement), not a text
    # match, so a docstring merely mentioning "from src.schemas import ..." as documentation
    # (assert_competition_only's own docstring does exactly this) is never a false positive.
    rendered_tree = ast.parse(flattened_source, filename="<flattened>")
    leftover_imports = [
        n
        for n in ast.walk(rendered_tree)
        if (isinstance(n, ast.ImportFrom) and n.module and n.module.startswith("src"))
        or (isinstance(n, ast.Import) and any(a.name.startswith("src") for a in n.names))
    ]
    assert not leftover_imports, (
        f"flattened source still has {len(leftover_imports)} project-local import statement(s) "
        "-- dependency walk or import-stripping is incomplete"
    )

    _execute_self_check_only(flattened_source)

    notebook = build_notebook_json(flattened_source)
    OUT_DIR.mkdir(exist_ok=True)
    OUT_NOTEBOOK.write_text(json.dumps(notebook, indent=1))
    print(f"Wrote {OUT_NOTEBOOK} ({len(flattened_source.splitlines())} lines of flattened source).")
    print("Self-check: PASS (Step 2 fixtures reproduced against the flattened source).")


if __name__ == "__main__":
    main()
