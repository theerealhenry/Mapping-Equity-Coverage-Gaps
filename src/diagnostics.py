"""
src/diagnostics.py — Stage 8 (Diagnostic modeling & hypothesis funnel).

Owned by Stage 8. Responsible for the two-mode clustering used to characterize and cross tracts
against vulnerability strata, training the three candidate explanatory model families (a
linear/Ridge baseline, a Random Forest, and a LightGBM gradient-boosted regressor) against the
frozen Stage 7 coverage-gap scores via repeated k-fold cross-validation, Optuna-based hyperparameter
optimization (scoped to this stage only, logged as nested MLflow runs), ensembling the tuned
explanatory models (adopting whichever wins honestly rather than defaulting to the ensemble), the
hard go/no-go gate on whether the winning model ships at all (an honest "insufficiently explanatory,
not deployed" outcome is a legitimate result, not a failure), and SHAP-based global/local
feature-importance evidence — with any transport-gap-driven SHAP finding flagged for extra scrutiny
against per-region models before being passed to Stage 9, given that component's known,
non-vulnerability-related source of cross-region variation.

Intentionally empty — populated in Stage 8.
"""
