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
