import tempfile
import unittest
from pathlib import Path
import pandas as pd
from analytics import build, resolve_caseloads

class AnalyticsTest(unittest.TestCase):
    def test_protection_scopes(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            sources={
                'plans':[{'plan_id':1509,'name':'DRC','iso3':'COD','country_count':1}],
                'caseloads':[
                    {'plan_id':1509,'caseloadId':1,'caseloadType':'plan','inNeed':18488689},
                    {'plan_id':1509,'caseloadId':2,'caseloadType':'cluster','availableGlobalClusterCode':'PRO','entityId':8767,'inNeed':5076852},
                    {'plan_id':1509,'caseloadId':3,'caseloadType':'cluster','availableGlobalClusterCode':'PRO-CPN','entityId':8767,'inNeed':4033807,'target':992628},
                    {'plan_id':1509,'caseloadId':4,'caseloadType':'cluster','caseloadCustomRef':'CLPRO/BF3-PRO-OVE','entityId':8767,'inNeed':6355420}],
                'global_clusters':[{'plan_id':1509,'globalClusterId':10,'globalClusterCode':'PRO'},{'plan_id':1509,'globalClusterId':12,'globalClusterCode':'PRO-CPN'}],
                'financial_breakdowns':[
                    {'plan_id':1509,'dimension':'byGlobalCluster','globalClusterId':12,'kind':'requirements','requirements':42420103},
                    {'plan_id':1509,'dimension':'byGlobalCluster','globalClusterId':12,'kind':'funding','funding':7117852},
                    {'plan_id':1509,'dimension':'byCluster','clusterId':8767,'kind':'requirements','requirements':114571455}],
                'financial_totals':[{'plan_id':1509,'kind':'requirements','totalRequirements':2132641156}]}
            for name,rows in sources.items():
                folder=root/'tables'/name
                folder.mkdir(parents=True)
                pd.DataFrame(rows).to_csv(folder/'2026.csv',index=False)
            plans,sectors,qa=build(root,2026)
            lookup={r['global_cluster_code']:r for r in sectors}
            self.assertEqual(plans[0]['pin'],18488689)
            self.assertEqual(lookup['PRO-CPN']['pin'],4033807)
            self.assertEqual(lookup['PRO-CPN']['requirements_usd'],42420103)
            self.assertEqual(lookup['PRO-CPN']['funding_usd'],7117852)
            self.assertEqual(lookup['PRO']['pin'],5076852)
            self.assertEqual(lookup['PRO-OVE']['pin'],6355420)
            self.assertEqual(lookup['PRO-OVE']['requirements_usd'],114571455)

    def test_recover_only_supported_mappings(self):
        g=[{'globalClusterCode':'PRO-CPN','planClusters':'[1, 2]'},{'globalClusterCode':'PRO','planClusters':'[1]'},{'globalClusterCode':'NUT','planClusters':'[3, 4]'}]
        r=[{'caseloadType':'cluster','entityId':1,'availableGlobalClusterCode':'n/a','caseloadCustomRef':'CLPRO/BF2-PRO -CPN'},
           {'caseloadType':'cluster','entityId':1,'caseloadCustomRef':'CLPRO/BF1-PRO-OVE'},
           {'caseloadType':'cluster','entityId':2,'caseloadCustomRef':'CLCP/BF1'},
           {'caseloadType':'cluster','entityId':3,'caseloadCustomRef':'CLNUT/BF1'},
           {'caseloadType':'cluster','entityId':3,'caseloadCustomRef':'CLNUT/BF2'},
           {'caseloadType':'cluster','entityId':4,'caseloadCustomRef':'CLNUT/BF1'}]
        result=resolve_caseloads(r,g)
        self.assertEqual([x[1] for x in result],['PRO-CPN','PRO-OVE','PRO-CPN',None,None,'NUT'])
