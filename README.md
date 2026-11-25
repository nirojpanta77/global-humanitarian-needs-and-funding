# Global Humanitarian Needs and Funding

Automated public OCHA HPC and FTS extraction across countries, plans, clusters and years (2018 through next calendar year). Countries and clusters are discovered from annual plan data.

## Refresh
[GitHub Actions](https://github.com/nirojpanta77/global-humanitarian-needs-and-funding/actions): daily at 04:37 UTC; detailed plan extraction Sundays at 02:17 UTC. Manual runs support the deep option. Schedules are best effort, not real-time.

## Outputs
Latest annual CSV partitions on the data branch after a successful run: tables/<table>/<year>.csv. CSV, Parquet, compressed raw JSON and request manifest are retained as workflow artifacts for 30 days. Git history retains published CSV snapshots.

Tables include plans, countries, plan_countries, clusters, global_clusters, cluster_mapping, caseloads, caseload_measurements, indicators, indicator_measurements, financial_totals, financial_breakdowns, organizations, entities, monitoring_periods, master_candidates and qa. Deep runs retain raw detailed plans; all runs retain plan-scoped FTS reports in artifacts.

## Run locally
```sh
pip install -r requirements.txt
python -m unittest discover -s tests
python pipeline.py --start 2026 --end 2026
```
Add --deep for detailed data. Run python analytics.py and python fts.py after extraction.

## Methodology and limitations
Initial implementation, not yet certified for reporting. Live schema and coverage must be verified. Master candidates only use unique explicit caseload links; ambiguous rows are flagged. Never sum sector PiN into overall PiN, duplicate regional plans across countries, or add independent FTS funding to HPC financial totals. Missing is not zero. Country discovery is intentionally plan-based; country-wide outside-plan FTS funding is not part of the reconciliation. Detailed transaction pagination and subnational normalization are not yet certified. Financial breakdowns are alternative dimensions, not additive. Historical/current empty years fail the run; next-year empty results are permitted. Use durable object storage for long-term raw history. Synthetic tests are not a substitute for live reconciliation.

Sources: [HPC API](https://api.hpc.tools/docs/v2/), [FTS API](https://api.hpc.tools/docs/v1/), [Summary API](https://github.com/UN-OCHA/hpc-api/wiki/HPC-Plans-Summary-API).

## Consolidated analytics
On every successful refresh, analytics.py generates tables/plan_analytics/all_years.csv and tables/global_sector_analytics/all_years.csv (plus Parquet artifacts). Plan totals use only explicit plan caseloads and financial totals. Global sector PiN/target are matched by exact availableGlobalClusterCode; financials use byGlobalCluster, not the parent country's cluster totals. Ambiguous caseloads are left null and recorded in analytics_qa. Explicit -PRO-OVE caseloads are reported separately as the Protection envelope with the matching parent cluster financials; PRO generally represents general Protection when AoRs are separated. Do not add the envelope to its constituent sectors. Unmapped/unknown funding allocations are retained. Overall plan and sector populations are not additive across overlapping plans. 2027 remains empty until published in the API. These outputs are provisional until reconciliation with OCHA publications.

### Recovery rules
When the source global caseload code is blank or n/a, use an exact normalized reference suffix corroborated by the entity mapping, or a single caseload linked exclusively to one global sector. The method is recorded in caseload_mapping_method; unresolved and ambiguous rows are recorded in analytics_qa. Financial fallback is allowed only when no direct global row exists for that metric and one country cluster maps exclusively to one global sector; financial source fields record the method. Never allocate shared Protection or multi-sector funding to each constituent sector. Multiple overlapping caseloads remain unresolved rather than being summed.

## COVID scope and plan-scoped FTS
Explicit COVID response plans and COVID-specific caseloads (including C19 cluster references) are excluded from the analytical layer, not the original source tables. Non-COVID/regular HRP records are retained. Plans containing both types retain their official reported financial totals and are flagged financial_scope=reported_plan_may_include_covid; these totals must not be presented as COVID-adjusted. Other overlapping caseloads are not summed.

Each refresh requests https://api.hpc.tools/v1/public/fts/flow?planid=ID&groupby=globalcluster&report=3&format=json&limit=1, the plan-level reporting endpoint used by OCHA-DAP's HDX FTS scraper. This is a full-plan-lifecycle report, not a calendar-year or country-wide funding report. One request is made per distinct plan ID; plan and sector reconciliations join on plan ID and, for sectors, global cluster ID. A plan reused across years is explicitly flagged; do not sum its repeated lifecycle funding. FTS paid/committed funding and pledges are separate. Shared funding is recorded separately, never allocated to all linked sectors. Raw reports remain in artifacts. Unavailable FTS plans have explicit status and null amounts, never zero. If every FTS request fails, the reconciliation step fails without publishing empty FTS tables; HPC publication can still proceed. Check the FTS extraction timestamp before comparing. HPC values remain intact; FTS values and differences are parallel columns, not additional funding. FTS tables: fts_plan_totals, fts_sector_totals, fts_plan_reconciliation, fts_sector_reconciliation, fts_status.

Reference implementation: https://github.com/OCHA-DAP/hdx-scraper-fts/blob/main/src/hdx/scraper/fts/requirements_funding_cluster.py

## Dashboard
The responsive dashboard lives in `docs/index.html`, reads published CSVs directly from the data branch, and requires no server or credentials. Enable GitHub Pages under Settings → Pages → Deploy from a branch → main → /docs → Save. The intended URL is https://nirojpanta77.github.io/global-humanitarian-needs-and-funding/. The default is GHO plans only; users can change scope and financial source, filter one global sector at a time, view historical charts, rank plans, inspect data completeness and export filtered data. FTS is plan-ID scoped and separately dated. This is an independent analytical tool, not an official UN publication.
