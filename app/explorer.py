"""
app/explorer.py — Stage 12 (Deployment: the Presentation/Deployment Engine).

Owned by Stage 12. The deployed, interactive Streamlit app — the Coverage Gap Explorer plus the
Equity Profile Explorer panel — entirely static-data-driven: it reads only from the committed
`app/data/` bundle (the final frozen, scored tract tables and the serialized winning explanatory
model, if Stage 8's gate was passed). No live DuckDB querying, no live S3 access, no multi-GB data
loaded at request time — every number the app shows was computed upstream and frozen. The home page
narrates the pipeline (Data -> Reference Comparison -> Coverage Gap -> Equity Analysis -> Discovery)
and offers three exploration modes: by tract, by community archetype (Stage 8's clustering), and by
flagship Bias Discovery finding. The explanatory-model panel is deliberately named "Equity Profile
Explorer," not "What-If," and states its output as association ("this profile resembles tracts
where the reconstructed coverage gap tends to be higher/lower") with an out-of-distribution warning
for extrapolative inputs — never a causal claim.

Intentionally empty — populated in Stage 12.
"""
