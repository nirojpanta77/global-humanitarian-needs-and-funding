import argparse, datetime as dt, gzip, json, pathlib, time, math
from decimal import Decimal, InvalidOperation
from collections import defaultdict
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
BASE='https://api.hpc.tools'
TABLES='plans countries plan_countries clusters global_clusters cluster_mapping entities monitoring_periods organizations caseloads caseload_measurements indicators indicator_measurements financial_totals financial_breakdowns master_candidates qa fts_country_reports'.split()

NUMERIC_FIELDS = {'inNeed','target','affected','totalPopulation','population','pin','reached','requirements','funding','requirements_usd','funding_usd','funding_pct','peopleInNeed','peopleTargeted','peopleReached'}

def number(value):
    if value is None or isinstance(value, bool): return None
    try:
        d=Decimal(str(value).strip())
        if not d.is_finite(): return None
        if d == d.to_integral_value(): return int(d)
        result=float(d)
        return result if math.isfinite(result) else None
    except (InvalidOperation, ValueError, OverflowError):
        return None

def export_frame(rows, table, year):
    frame=pd.DataFrame(rows)
    if not len(frame.columns): frame=pd.DataFrame(columns=['year','plan_id'])
    for column in frame.columns:
        if column in NUMERIC_FIELDS:
            values=[number(v) for v in frame[column]]
            invalid=sum(v is not None and str(v).strip() not in ('','nan','<NA>','None') and n is None for v,n in zip(frame[column],values))
            if invalid: print(f'WARNING {year}/{table}/{column}: {invalid} invalid numeric values; original preserved in raw JSON',flush=True)
            frame[column]=pd.to_numeric(pd.Series(values,index=frame.index),errors='raise')
        elif frame[column].dtype == object:
            values=frame[column].dropna()
            kinds={type(v) for v in values}
            if len(kinds)>1 and not kinds.issubset({int,float}):
                print(f'WARNING {year}/{table}/{column}: mixed types exported as text',flush=True)
                frame[column]=frame[column].astype('string')
    return frame

def scalar(row):
    return {k:json.dumps(v,ensure_ascii=False,sort_keys=True) if isinstance(v,(dict,list)) else v for k,v in row.items()}

def normalize(payload,year):
    plans=payload['data']['planData']
    if not isinstance(plans,list): raise ValueError('Unexpected planData schema')
    t=defaultdict(list); seen=set(); countries={}
    for p in plans:
        pid=p['planId']
        if pid in seen: raise ValueError(f'Duplicate plan {pid}')
        seen.add(pid)
        def add(table,row): t[table].append({**scalar(row),'year':year,'plan_id':pid})
        pc=p.get('planCountries') or []; iso=pc[0].get('iso3') if len(pc)==1 else None
        add('plans',{**{k:v for k,v in p.items() if not isinstance(v,(list,dict))},'iso3':iso,'country_count':len(pc)})
        for c in pc:
            add('plan_countries',c); countries[c['id']]=scalar(c)
        for field,table in [('planClusters','clusters'),('planGlobalClusters','global_clusters'),('planEntities','entities'),('monitoringPeriods','monitoring_periods'),('organizations','organizations')]:
            for r in p.get(field) or []: add(table,r)
        mapping=defaultdict(set)
        for g in p.get('planGlobalClusters') or []:
            for cid in g.get('planClusters') or []:
                mapping[cid].add(g['globalClusterId']); add('cluster_mapping',{'cluster_id':cid,'global_cluster_id':g['globalClusterId']})
        for field,ident in [('caseloads','caseloadId'),('indicators','indicatorId')]:
            for r in p.get(field) or []:
                add(field,{k:v for k,v in r.items() if k!='measurements'})
                for m in r.get('measurements') or []: add(field.rstrip('s')+'_measurements',{**m,ident:r[ident]})
        indexed=defaultdict(list)
        for kind in ('requirements','funding'):
            block=(p.get('financialData') or {}).get(kind) or {}
            add('financial_totals',{'kind':kind,**{k:v for k,v in block.items() if k!='breakdown'}})
            for dim,rows in (block.get('breakdown') or {}).items():
                if isinstance(rows,dict): rows=[{**r,'organizationId':org} for org,rr in rows.items() for r in rr]
                for r in rows or []:
                    add('financial_breakdowns',{'kind':kind,'dimension':dim,**r})
                    if dim=='byCluster': indexed[kind,r.get('clusterId')].append(r.get(kind))
        for c in p.get('planClusters') or []:
            cid=c['clusterId']; req=indexed['requirements',cid]; fund=indexed['funding',cid]
            matches=[r for r in p.get('caseloads') or [] if r.get('clusterId')==cid or (r.get('caseloadType')=='cluster' and r.get('entityId')==cid)]
            if len(matches)!=1 or len(req)>1 or len(fund)>1: add('qa',{'cluster_id':cid,'caseload_count':len(matches),'requirement_count':len(req),'funding_count':len(fund)})
            r=matches[0] if len(matches)==1 else {}; a=number(req[0]) if len(req)==1 else None; b=number(fund[0]) if len(fund)==1 else None
            add('master_candidates',{'iso3':iso,'cluster_id':cid,'cluster_name':c.get('clusterName'),'global_cluster_id':next(iter(mapping[cid])) if len(mapping[cid])==1 else None,'pin':r.get('inNeed'),'target':r.get('target'),'affected':r.get('affected'),'population':r.get('totalPopulation'),'requirements_usd':a,'funding_usd':b,'funding_pct':100*b/a if isinstance(a,(int,float)) and a>0 and isinstance(b,(int,float)) else None})
    t['countries']=list(countries.values()); return t

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--start',type=int,default=2018); ap.add_argument('--end',type=int,default=dt.date.today().year+1); ap.add_argument('--deep',action='store_true'); ap.add_argument('--output',default='output'); args=ap.parse_args()
    if args.start>args.end: ap.error('Invalid years')
    root=pathlib.Path(args.output); raw=root/'raw'; raw.mkdir(parents=True,exist_ok=True)
    s=requests.Session(); s.headers['User-Agent']='GlobalHumanitarianNeedsFunding/1.0'; s.mount('https://',HTTPAdapter(max_retries=Retry(total=5,backoff_factor=2,status_forcelist=[429,500,502,503,504])))
    manifest=[]
    def get(path,params,name):
        time.sleep(.5); response=s.get(BASE+path,params=params,timeout=(20,180)); response.raise_for_status(); data=response.json()
        if not isinstance(data,dict) or data.get('status') not in (None,'ok'): raise ValueError(f'API error {name}')
        with gzip.open(raw/(name+'.json.gz'),'wt',encoding='utf-8') as f: json.dump(data,f,ensure_ascii=False)
        manifest.append({'file':name,'url':response.url,'extracted_at':dt.datetime.now(dt.timezone.utc).isoformat()}); return data
    for year in range(args.start,args.end+1):
        print(f'Extracting {year}',flush=True)
        data=get('/v2/public/planSummary',{'year':year,'includeCaseloads':'true','includeIndicators':'true','includeFinancials':'true'},f'summary_{year}')
        tables=normalize(data,year)
        if not tables['plans'] and year<=dt.date.today().year: raise ValueError(f'Empty historical/current year {year}')
        if args.deep:
            for p in tables['plans']:
                pid=p['plan_id']; get(f'/v2/public/plan/{pid}',{'content':'entities','disaggregation':'true'},f'plan_{year}_{pid}')
        for name in TABLES:
            print(f'Exporting {year}/{name}: {len(tables.get(name,[]))} rows',flush=True)
            frame=export_frame(tables.get(name,[]),name,year); folder=root/'tables'/name; folder.mkdir(parents=True,exist_ok=True)
            frame.to_csv(folder/f'{year}.csv',index=False); frame.to_parquet(folder/f'{year}.parquet',index=False)
    (root/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
if __name__=='__main__': main()
