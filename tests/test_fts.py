import unittest
from fts import parse
from analytics import covid_plan, covid_caseload

class FTSTest(unittest.TestCase):
    def test_report(self):
        payload={'status':'ok','data':{'requirements':{'totalRevisedReqs':100,'totalOrigReqs':90,'objects':[{'id':12,'name':'Child Protection','revisedRequirements':50,'origRequirements':45}]},'report3':{'fundingTotals':{'total':60,'objects':[{'totalBreakdown':{'sharedFunding':10},'objectsBreakdown':[{'id':'12','name':'Child Protection','totalFunding':40,'sharedFunding':10},{'name':'Not specified','totalFunding':10}]}]},'pledgeTotals':{'total':5}}}}
        total,rows=parse(payload)
        self.assertEqual(total['fts_funding_usd'],60)
        self.assertEqual(total['fts_shared_funding_usd'],10)
        self.assertEqual(total['fts_pledges_usd'],5)
        lookup={r['global_cluster_id']:r for r in rows}
        self.assertEqual(lookup['12']['fts_funding_usd'],40)
        self.assertEqual(lookup['12']['fts_requirements_usd'],50)
        self.assertEqual(lookup['Not specified']['fts_funding_usd'],10)
    def test_covid(self):
        self.assertTrue(covid_plan({'name':'Nepal Intersectoral COVID-19 Response Plan'}))
        self.assertFalse(covid_plan({'name':'Ukraine Humanitarian Response Plan 2020'}))
        self.assertTrue(covid_caseload({'caseloadCustomRef':'CLEDUC19/BF2-EDU','caseloadDescription':'Education'}))
        self.assertTrue(covid_caseload({'caseloadDescription':'COVID Caseload (National Level Totals)'}))
        self.assertFalse(covid_caseload({'caseloadDescription':'Non-COVID Caseload (National Level Totals)'}))
