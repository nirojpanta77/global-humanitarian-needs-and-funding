"""Reconcile FTS plan-scoped totals to HPC; no country-total attribution."""
import argparse, concurrent.futures, datetime as dt, gzip, json, time
from pathlib import Path
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
URL='https://api.hpc.tools/v1/fts/flow/custom-search'

def parse(payload):
    if payload.get('status')!='ok': raise ValueError('FTS status not ok')
    d=payload['data']; req=d['requirements']; rep=d['report3']; fund=rep['fundingTotals']
    groups=fund['objects']
    if len(groups)>1: raise ValueError('Unexpected FTS grouping')
    group=groups[0] if groups else {}
    total={'fts_requirements_usd':req.get('totalRevisedReqs'),'fts_original_requirements_usd':req.get('totalOrigReqs'),'fts_funding_usd':fund.get('total'),'fts_pledges_usd':rep.get('pledgeTotals',{}).get('total'),'fts_shared_funding_usd':group.get('totalBreakdown',{}).get('sharedFunding')}
    rows={}
    for obj in req['objects']:
        gid=obj.get('id')
        if gid is None: continue
        k=str(gid)
        if k in rows: raise ValueError('Duplicate FTS requirement group')
        rows[k]={'global_cluster_id':k,'fts_cluster_name':obj.get('name'),'fts_requirements_usd':obj.get('revisedRequirements'),'fts_original_requirements_usd':obj.get('origRequirements')}
    seen=set()
    for obj in group.get('objectsBreakdown',[]):
        gid=obj.get('id'); k='Not specified' if gid in (None,'undefined') else str(gid)
        if k in seen: raise ValueError('Duplicate FTS funding group')
        seen.add(k)
        row=rows.setdefault(k,{'global_cluster_id':k,'fts_cluster_name':obj.get('name')})
        row.update(fts_funding_usd=obj.get('totalFunding'),fts_shared_associated_usd=obj.get('sharedFunding'))
    # Shared amount is retained once at plan level, not added to each sector.
    return total,list(rows.values())

def get(pid,raw):
    s=requests.Session()
    s.headers['User-Agent']='GlobalHumanitarianNeedsFunding/1.0'
    s.mount('https://',HTTPAdapter(max_retries=Retry(total=3,backoff_factor=2,status_forcelist=[429,500,502,503,504],respect_retry_after_header=True)))
    try:
        time.sleep(0.5)
        response=s.get(URL,params={'planid':pid,'groupby':'globalcluster'},timeout=(15,120))
        response.raise_for_status(); payload=response.json()
        with gzip.open(raw/f'fts_plan_{pid}.json.gz','wt',encoding='utf-8') as f: json.dump(payload,f)
        total,rows=parse(payload)
        return pid,total,rows,None
    except (requests.RequestException,ValueError,KeyError,TypeError) as e:
        return pid,{},[],str(e)
    finally: s.close()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',default='output');args=ap.parse_args();root=Path(args.output)
    plans=pd.read_csv(root/'tables/plan_analytics/all_years.csv',dtype={'plan_id':'string'})
    sectors=pd.read_csv(root/'tables/global_sector_analytics/all_years.csv',dtype={'plan_id':'string','global_cluster_id':'string'})
    raw=root/'raw';raw.mkdir(exist_ok=True)
    pids=sorted(plans.plan_id.dropna().unique())
    if not pids: raise ValueError('No plans to reconcile')
    totals=[];groups=[];status=[]
    stamp=dt.datetime.now(dt.timezone.utc).isoformat()
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        for pid,total,rows,error in pool.map(lambda p:get(p,raw),pids):
            print('FTS',pid,'error' if error else 'ok',flush=True)
            status.append({'plan_id':pid,'fts_status':'unavailable' if error else 'ok','fts_error':error,'fts_extracted_at':stamp})
            if not error:
                totals.append({'plan_id':pid,**total})
                groups.extend({'plan_id':pid,**row} for row in rows)
    if not totals: raise RuntimeError('All FTS requests failed; do not publish empty reconciliation')
    st=pd.DataFrame(status); t=pd.DataFrame(totals); g=pd.DataFrame(groups,columns=['plan_id','global_cluster_id','fts_cluster_name','fts_requirements_usd','fts_original_requirements_usd','fts_funding_usd','fts_shared_associated_usd'])
    # FTS endpoint measures full plan lifecycle. Keep usage/planning years separate.
    counts=plans.groupby('plan_id').year.nunique()
    def annotate(df):
        df['fts_scope']='full_plan_lifecycle'
        df['fts_repeated_across_years']=df.plan_id.map(counts).gt(1)
        for metric in ('requirements','funding'):
            df[metric+'_delta_usd']=df['fts_'+metric+'_usd']-df[metric+'_usd']
        return df
    pp=annotate(plans.merge(st,on='plan_id',validate='many_to_one').merge(t,on='plan_id',how='left',validate='many_to_one'))
    ss=annotate(sectors.merge(st,on='plan_id',validate='many_to_one').merge(g,on=['plan_id','global_cluster_id'],how='left',validate='many_to_one'))
    for name,frame in [('fts_plan_reconciliation',pp),('fts_sector_reconciliation',ss),('fts_plan_totals',t),('fts_sector_totals',g),('fts_status',st)]:
        dest=root/'tables'/name;dest.mkdir(parents=True,exist_ok=True)
        frame.to_csv(dest/'all_years.csv',index=False);frame.to_parquet(dest/'all_years.parquet',index=False)
if __name__=='__main__':main()
