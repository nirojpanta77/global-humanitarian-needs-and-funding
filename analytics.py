"""Build analysis-ready tables from native HPC annual CSVs."""
import argparse, json, re
from pathlib import Path
import pandas as pd

def read(root, name, year):
    return pd.read_csv(root/'tables'/name/f'{year}.csv',dtype='string',keep_default_na=False).replace('',pd.NA)

def key(v):
    if pd.isna(v): return None
    s=str(v)
    return s[:-2] if s.endswith('.0') and s[:-2].isdigit() else s

def num(v):
    return pd.to_numeric(v,errors='coerce')

def unique_value(rows, field):
    if len(rows)!=1 or field not in rows[0]: return None
    v=num(rows[0][field])
    return None if pd.isna(v) else v

def resolve_caseloads(cas, globals_):
    """Return source rows with explicit or narrowly supported sector mappings."""
    by_entity={}
    codes=set()
    for g in globals_:
        code=key(g.get('globalClusterCode'))
        if not code: continue
        codes.add(code)
        ids=json.loads(key(g.get('planClusters')) or '[]')
        for entity in ids: by_entity.setdefault(key(entity),set()).add(code)
    rows=[r for r in cas if key(r.get('caseloadType'))=='cluster']
    counts={}
    for r in rows:
        entity=key(r.get('entityId'))
        counts[entity]=counts.get(entity,0)+1
    resolved=[]
    for r in rows:
        explicit=key(r.get('availableGlobalClusterCode'))
        ref=re.sub(r'\s+','',key(r.get('caseloadCustomRef')) or '').upper()
        entity=key(r.get('entityId')); linked=by_entity.get(entity,set())
        if ref.endswith('-PRO-OVE'):
            code,method='PRO-OVE','explicit_protection_envelope'
        elif explicit and explicit.lower() not in ('n/a','na'):
            code,method=explicit,'source_global_code'
        else:
            suffix=[c for c in linked if ref.endswith('-'+c)]
            # Prefer the longest exact suffix, e.g. PRO-CPN over a shorter code.
            if suffix:
                code,method=max(suffix,key=len),'reference_suffix_and_entity'
            elif len(linked)==1 and entity is not None and counts[entity]==1:
                code,method=next(iter(linked)),'unique_entity_mapping'
            else:
                code,method=None,'unresolved'
        resolved.append((r,code,method))
    return resolved

def build(root,year):
    plans=read(root,'plans',year); cs=read(root,'caseloads',year); gs=read(root,'global_clusters',year); fs=read(root,'financial_breakdowns',year); totals=read(root,'financial_totals',year)
    out=[]; planout=[]; qa=[]
    def group(df,field):
        return {key(k):g.to_dict('records') for k,g in df.groupby(field)} if field in df else {}
    cg=group(cs,'plan_id'); gg=group(gs,'plan_id'); fg=group(fs,'plan_id'); tg=group(totals,'plan_id')
    for p in plans.to_dict('records'):
        pid=key(p.get('plan_id'))
        base={'year':year,'plan_id':pid,'iso3':p.get('iso3'),'country_count':p.get('country_count'),'plan_name':p.get('name'),'plan_type':p.get('planType'),'included_gho':p.get('includedGHO'),'last_published_date':p.get('lastPublishedDate')}
        cas=cg.get(pid,[]); finances=fg.get(pid,[]); total=tg.get(pid,[])
        def financial(rows,kind,field): return unique_value([r for r in rows if key(r.get('kind'))==kind],field)
        def metrics(row,candidates):
            row['caseload_count']=len(candidates)
            row['caseload_id']=candidates[0].get('caseloadId') if len(candidates)==1 else None
            for dest,src in [('population','totalPopulation'),('affected','affected'),('pin','inNeed'),('target','target'),('expected_reach','expectedReach')]: row[dest]=unique_value(candidates,src)
        def coverage(row):
            a,b=row.get('requirements_usd'),row.get('funding_usd')
            row['funding_pct']=100*b/a if a is not None and b is not None and a>0 else None
        overall={**base,'requirements_usd':financial(total,'requirements','totalRequirements'),'funding_usd':financial(total,'funding','totalFundingInsidePlan'),'outside_plan_funding_usd':financial(total,'funding','totalFundingOutsidePlan'),'pledges_usd':financial(total,'funding','totalPledges')}
        metrics(overall,[r for r in cas if key(r.get('caseloadType'))=='plan']); coverage(overall); planout.append(overall)
        # Only official global codes and direct global financial breakdowns.
        # PRO represents general protection, not the overall Protection envelope.
        sector={}
        for g in gg.get(pid,[]):
            gid=key(g.get('globalClusterId'))
            if gid: sector[gid]=g
        global_fin=[r for r in finances if key(r.get('dimension'))=='byGlobalCluster']
        for f in global_fin:
            gid=key(f.get('globalClusterId'))
            if gid and gid not in sector: sector[gid]={'globalClusterId':gid,'globalClusterName':gid if not gid.isdigit() else None}
        resolved=resolve_caseloads(cas,gg.get(pid,[]))
        for r,code,method in resolved:
            if code is None: qa.append({**base,'issue':'unmapped_caseload','caseload_id':r.get('caseloadId'),'caseload_ref':r.get('caseloadCustomRef'),'count':1})
        for gid,g in sector.items():
            code=g.get('globalClusterCode')
            matched=[(r,method) for r,mapped,method in resolved if pd.notna(code) and mapped==key(code)]
            candidates=[r for r,method in matched]
            financial_rows=[r for r in global_fin if key(r.get('globalClusterId'))==gid]
            row={**base,'global_cluster_id':gid,'global_cluster_code':code,'global_cluster_name':g.get('globalClusterName'),'global_cluster_type':g.get('globalClusterType'),'scope':'general_protection' if pd.notna(code) and code=='PRO' else 'global_sector','requirements_usd':financial(financial_rows,'requirements','requirements'),'funding_usd':financial(financial_rows,'funding','funding')}
            metrics(row,candidates); row['caseload_mapping_method']=matched[0][1] if len(matched)==1 else None; coverage(row); out.append(row)
            if len(candidates)>1: qa.append({**base,'global_cluster_id':gid,'issue':'ambiguous_caseload','count':len(candidates)})
        # Explicit overall Protection caseloads are retained separately from the
        # general Protection and AoR financial allocations. Do not sum scopes.
        envelopes=[r for r in cas if key(r.get('caseloadType'))=='cluster' and str(r.get('caseloadCustomRef','')).endswith('-PRO-OVE')]
        if envelopes:
            parent=key(envelopes[0].get('entityId')) if len(envelopes)==1 else None
            linked=[r for r in finances if parent and key(r.get('dimension'))=='byCluster' and key(r.get('clusterId'))==parent]
            row={**base,'global_cluster_id':'PRO-OVE','global_cluster_code':'PRO-OVE','global_cluster_name':'Protection (overall)','global_cluster_type':'aggregate','scope':'protection_envelope','requirements_usd':financial(linked,'requirements','requirements'),'funding_usd':financial(linked,'funding','funding')}
            metrics(row,envelopes); row['caseload_mapping_method']='explicit_protection_envelope' if len(envelopes)==1 else None; coverage(row); out.append(row)
            if len(envelopes)>1: qa.append({**base,'global_cluster_id':'PRO-OVE','issue':'ambiguous_protection_envelope','count':len(envelopes)})
    return planout,out,qa

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',default='output');args=ap.parse_args();root=Path(args.output)
    allrows={'plan_analytics':[],'global_sector_analytics':[],'analytics_qa':[]}
    for path in sorted((root/'tables'/'plans').glob('*.csv')):
        year=int(path.stem)
        for name,rows in zip(allrows,build(root,year)):
            allrows[name].extend(rows)
    for name,rows in allrows.items():
        folder=root/'tables'/name;folder.mkdir(parents=True,exist_ok=True)
        frame=pd.DataFrame(rows)
        if frame.empty: frame=pd.DataFrame(columns=['year','plan_id'])
        if name!='analytics_qa' and frame.duplicated(['year','plan_id']+(['global_cluster_id'] if name=='global_sector_analytics' else [])).any(): raise ValueError('Duplicate analytical grain: '+name)
        # Keys and metadata are text; metrics are numeric.
        for col in frame:
            if col not in ('year','country_count','caseload_count','count','population','affected','pin','target','expected_reach','requirements_usd','funding_usd','outside_plan_funding_usd','pledges_usd','funding_pct'):
                frame[col]=frame[col].astype('string')
        frame.to_csv(folder/'all_years.csv',index=False);frame.to_parquet(folder/'all_years.parquet',index=False)
        print(name,len(frame),flush=True)
if __name__=='__main__':main()
