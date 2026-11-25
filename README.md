# Global Humanitarian Needs and Funding

Automated public OCHA HPC and FTS extraction across countries, plans, clusters and years (2018 through next calendar year). Countries and clusters are discovered from annual plan data.

## Refresh
[GitHub Actions](https://github.com/nirojpanta77/global-humanitarian-needs-and-funding/actions): daily at 04:37 UTC; detailed plan and country FTS extraction Sundays at 02:17 UTC. Manual runs support the deep option. Schedules are best effort, not real-time.

## Outputs
Latest annual CSV partitions on the data branch after a successful run: tables/<table>/<year>.csv. CSV, Parquet, compressed raw JSON and request manifest are retained as workflow artifacts for 30 days. Git history retains published CSV snapshots.

Tables include plans, countries, plan_countries, clusters, global_clusters, cluster_mapping, caseloads, caseload_measurements, indicators, indicator_measurements, financial_totals, financial_breakdowns, organizations, entities, monitoring_periods, master_candidates and qa. Deep runs retain raw detailed plans and FTS reports in artifacts.

## Run locally
```sh
pip install -r requirements.txt
python -m unittest discover -s tests
python pipeline.py --start 2026 --end 2026
```
Add --deep for detailed data.

## Methodology and limitations
Initial implementation, not yet certified for reporting. Live schema and coverage must be verified. Master candidates only use unique explicit caseload links; ambiguous rows are flagged. Never sum sector PiN into overall PiN, duplicate regional plans across countries, or add independent FTS funding to HPC financial totals. Missing is not zero. Country discovery is plan-based; FTS-only destinations are not yet covered. Detailed FTS pagination, completeness and subnational normalization are not yet certified. Financial breakdowns are alternative dimensions, not additive. Historical/current empty years fail the run; next-year empty results are permitted. Use durable object storage for long-term raw history. Synthetic tests are not a substitute for live reconciliation.

Sources: [HPC API](https://api.hpc.tools/docs/v2/), [FTS API](https://api.hpc.tools/docs/v1/), [Summary API](https://github.com/UN-OCHA/hpc-api/wiki/HPC-Plans-Summary-API).

## Consolidated analytics
On every successful refresh, analytics.py generates tables/plan_analytics/all_years.csv and tables/global_sector_analytics/all_years.csv (plus Parquet artifacts). Plan totals use only explicit plan caseloads and financial totals. Global sector PiN/target are matched by exact availableGlobalClusterCode; financials use byGlobalCluster, not the parent country's cluster totals. Ambiguous caseloads are left null and recorded in analytics_qa. Explicit -PRO-OVE caseloads are reported separately as the Protection envelope with the matching parent cluster financials; PRO generally represents general Protection when AoRs are separated. Do not add the envelope to its constituent sectors. Unmapped/unknown funding allocations are retained. Overall plan and sector populations are not additive across overlapping plans. 2027 remains empty until published in the API. These outputs are provisional until reconciliation with OCHA publications.
