import json
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
import pandas as pd
from terrashift_ai import prepare_analysis, analyze_dataframe, AnalysisError
ROOT=Path(__file__).resolve().parents[1]
class IntegrationTests(unittest.TestCase):
 def setUp(self):
  self.x=json.loads((ROOT/'example_power.json').read_text())
  self.df=pd.DataFrame.from_dict(self.x['daily'],orient='index')
  self.df.index=pd.to_datetime(self.df.index)
  self.kw=dict(latitude=self.x['latitude'],longitude=self.x['longitude'],start=self.x['start'],end=self.x['end'])
 def prep(self,df=None,**kw):
  return prepare_analysis(self.df if df is None else df,**(self.kw|kw))
 def response(self,ref='PRECTOTCORR'):
  report=dict(summary='Resumen histórico.',observations=[dict(explanation='Precipitación disponible: 2.79 mm.',evidence_ids=[ref])],questions=[],next_steps=[],limitations=[])
  return Mock(status_code=200,json=lambda:{'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':json.dumps(report)}]}}]})
 def test_eleven_variables(self):
  r=self.prep(); self.assertEqual(len(r['climate']['facts']),11)
  self.assertEqual(r['climate']['facts'][0]['value'],2.79)
  json.dumps(r,allow_nan=False)
 def test_units(self):
  self.df.attrs['source_metadata']=self.x['source_metadata']
  r=self.prep(); self.assertEqual(r['climate']['time_standard'],'LST')
  for name in ('ALLSKY_SFC_SW_DWN','ALLSKY_SFC_PAR_TOT'):
   self.assertEqual(next(f for f in r['climate']['facts'] if f['id']==name)['unit'],'MJ/m²/day')
 def test_wrong_units(self):
  self.df.attrs['source_metadata']={'parameters':{'T2M':{'units':'F'}}}
  with self.assertRaises(ValueError): self.prep()
 def test_missing_rain(self):
  self.df['PRECTOTCORR']=-999
  self.assertIsNone(self.prep()['climate']['facts'][0]['value'])
 def test_missing_day(self):
  f=self.prep(self.df.iloc[1:])['climate']['facts'][0]
  self.assertEqual((f['valid_days'],f['expected_days']),(30,31))
 def test_duplicate_date(self):
  with self.assertRaises(ValueError): self.prep(pd.concat([self.df,self.df.iloc[:1]]))
 def test_numeric_index(self):
  with self.assertRaises(ValueError): self.prep(self.df.reset_index(drop=True))
 def test_unknown_column(self):
  self.df['NDVI_IMAGE_URL']='image'
  self.assertIn('NDVI_IMAGE_URL',' '.join(self.prep()['warnings']))
 def test_profile_changes_id(self):
  self.assertNotEqual(self.prep(profile={'water':'Riego'})['request_id'],self.prep(profile={'water':'Temporal'})['request_id'])
 def test_invalid_coordinate(self):
  with self.assertRaises(ValueError): self.prep(latitude=100)
 @patch('terrashift_ai.gemini.requests.post')
 def test_success(self,post):
  post.return_value=self.response()
  r=analyze_dataframe(self.df,**self.kw,api_key='test-secret')
  self.assertEqual(len(r['analysis']['observations']),1)
  self.assertNotIn('test-secret',json.dumps(r))
  self.assertNotIn('test-secret',json.dumps(post.call_args.kwargs['json']))
  self.assertEqual(post.call_count,1)
 @patch('terrashift_ai.gemini.requests.post')
 def test_no_key(self,post):
  with self.assertRaises(AnalysisError): analyze_dataframe(self.df,**self.kw,api_key='')
  post.assert_not_called()
 @patch('terrashift_ai.gemini.requests.post')
 def test_quota(self,post):
  post.return_value=Mock(status_code=429)
  with self.assertRaises(AnalysisError): analyze_dataframe(self.df,**self.kw,api_key='test')
  self.assertEqual(post.call_count,1)
 @patch('terrashift_ai.gemini.requests.post')
 def test_bad_reference(self,post):
  post.return_value=self.response('FAKE')
  with self.assertRaises(AnalysisError): analyze_dataframe(self.df,**self.kw,api_key='test')
 @patch('terrashift_ai.gemini.requests.post')
 def test_all_missing(self,post):
  self.df[:]=float('nan')
  with self.assertRaises(AnalysisError): analyze_dataframe(self.df,**self.kw,api_key='test')
  post.assert_not_called()
if __name__=='__main__': unittest.main()
