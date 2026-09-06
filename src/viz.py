"""
src/viz.py — shared plotting helpers, no single owning stage.

Unlike every other new module in this stage, `viz.py` is not owned by one stage's blueprint entry
— it is shared plotting infrastructure (a module, not a package, per `PROJECT_BLUEPRINT.md`
Section 4's target tree) that multiple later stages draw on: Stage 7's gold-standard validation
maps (Overture vs. reference layer comparisons), Stage 8's SHAP/clustering figures, Stage 9's
Bias Discovery figures published to `docs/figures/`, and the deployed app's (Stage 12) Equity
Profile Explorer panels. Centralizing plotting helpers here, rather than duplicating chart-building
code across each of those stages, is the reason this module exists as its own file instead of being
folded into whichever stage happens to need a chart first.

Intentionally empty — populated incrementally starting whichever of Stages 7-12 first needs a
shared plotting helper.
"""
