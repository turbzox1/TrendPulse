# TrendPulse implementation plan

## Final analytics-quality audit

- [x] Trace displayed metrics, statistical assumptions, SQL and chronological boundaries.
- [x] Fix substantive weaknesses and add targeted regression tests without new product features.
- [x] Verify all 60 tests, compilation and HTTP smoke; refresh the synthetic dataset and document interview-relevant methodology decisions in `docs/analytics-audit.md`.

## Security and repository hygiene audit

- [x] Inspect code, configuration, local secret exposure, and installed dependencies.
- [x] Fix import boundaries, spreadsheet exports, staging collisions, error disclosure, cache bounds, and repository defaults.
- [x] Document trust boundaries and public deployment limitations in `docs/security-audit.md` and README.
- [x] Verify: 47 tests passed, compilation passed, HTTP smoke passed; 50 dependencies audited with no known vulnerabilities.

1. [x] Build reproducible multi-source demo data, validated import adapters, and DuckDB schema/views. Data integrity and reproducibility checks passed.
2. [x] Implement past-only momentum/lifecycle features, robust anomalies, lead/lag analysis, deterministic insights, and chronological forecast evaluation. Edge cases and leakage-boundary checks passed.
3. [x] Build six polished Streamlit views with shared filters and explicit demo provenance. All page smoke checks and real HTTP server health checks passed.
4. [x] Document methods, schema, commands, limitations, and computed demo examples. Verify CLI help, generation/export, dependencies, compilation, and short-import states. Final suite rerun after the final UI guard.

Standalone project: the supplied directory is a home directory, not a repository. Synthetic data is the default. Google Trends uses official CSV exports; Reddit uses authorized aggregate exports. No scraping. Native source units remain separate; comparisons use source-relative attention.

## Frontend redesign

- [x] Introduce a cohesive midnight/lime design system, product navigation, and responsive typography.
- [x] Redesign the overview with a signal spotlight, chart panels, interactive topic cards, and compact insight briefs.
- [x] Apply consistent chart styling and surfaces across every analytical workspace; verify navigation and existing smoke tests.
- [x] Capture desktop/mobile browser screenshots, check horizontal overflow, and document the redesigned UI.

## Usability simplification

1. [x] Replace promotional landing content with topic search and a clear starting action; use plain-language navigation.
2. [x] Put optional filters and technical explanations behind labeled expanders; add reset and recovery actions.
3. [x] Organize the topic deep dive into focused tabs, preserving all scores, source analysis, anomalies, forecasts, related topics, and downloads.
4. [x] Check topic search/navigation, filter recovery, all feature pages, and desktop/mobile rendering. All 23 tests passed; browser checks passed without horizontal overflow.

## Visual refinement: clear, colorful, smooth

- [x] Replace accumulated CSS overrides with one cohesive design system.
- [x] Keep the topic-first flow; add consistent category colors, labeled stage badges, and a compact search panel.
- [x] Use lightweight transitions with reduced-motion support; no continuous animation or added network dependencies.
- [x] Verify application flows and desktop/mobile rendering, then restart the app. Four application regression tests passed across all six pages; HTTP smoke check, reduced-motion check, sparkline rendering, and mobile Menu interaction passed.
