import unittest
from pipeline import normalize, export_frame
import pandas as pd
import tempfile
from pathlib import Path
class Test(unittest.TestCase):
    def test_grains(self):
        p={'planId':1,'planCountries':[{'id':1,'iso3':'AAA'},{'id':2,'iso3':'BBB'}],'planClusters':[{'clusterId':7}], 'planGlobalClusters':[{'globalClusterId':4,'planClusters':[7]},{'globalClusterId':5,'planClusters':[7]}], 'caseloads':[{'caseloadId':1,'caseloadType':'cluster','entityId':7,'inNeed':100},{'caseloadId':2,'caseloadType':'cluster','entityId':7,'inNeed':80}], 'financialData':{'requirements':{'breakdown':{'byCluster':[{'clusterId':7,'requirements':100}]}},'funding':{'breakdown':{'byCluster':[{'clusterId':7,'funding':0}]}}}}
        t=normalize({'data':{'planData':[p]}},2026); r=t['master_candidates'][0]
        self.assertIsNone(r['iso3']); self.assertIsNone(r['global_cluster_id']); self.assertIsNone(r['pin']); self.assertEqual(r['funding_pct'],0); self.assertEqual(len(t['caseloads']),2)
    def test_duplicate(self):
        with self.assertRaises(ValueError): normalize({'data':{'planData':[{'planId':1},{'planId':1}]}},2026)
    def test_mixed_numeric_parquet(self):
        frame=export_frame([{'inNeed':100,'label':'a'},{'inNeed':'','label':4},{'inNeed':'250','label':None},{'inNeed':0,'label':'b'}],'caseloads',2026)
        self.assertEqual(frame['inNeed'].iloc[0],100)
        self.assertTrue(pd.isna(frame['inNeed'].iloc[1]))
        self.assertEqual(frame['inNeed'].iloc[2],250)
        self.assertEqual(frame['inNeed'].iloc[3],0)
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'test.parquet'
            frame.to_parquet(path,index=False)
            self.assertEqual(len(pd.read_parquet(path)),4)
