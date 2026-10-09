"""Synthetic contract tests; no live VAST integration is claimed by these tests."""
import contextlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from vast.common import load_config, ROOT
from vast.check_pipeline import check,indexed_uploads
from vast.write_events import build_rows,persist,arrow_schema,provenance


def fixture():
    event={'kind':'fight','priority':'HIGH','title':'Synthetic test interaction','start_iso':'2026-10-09T06:20:00','end_iso':'2026-10-09T06:21:00','clip_count':1,'clips':['neutral.mp4'],'confirmed':False}
    report={'result':{'events':[event]},'report':{'source':'synthetic-test-model','text':'Test report'},'trace_url':'https://example.invalid/test-trace'}
    segments=[{'filename':'neutral.mp4','checks':{'fight':'YES. Synthetic fixture.'},'original_video':None,'raw':{'path':'direct-to-GPU-endpoint'}}]
    return json.dumps(report).encode(),json.dumps(segments).encode()


class FakeTable:
    def __init__(self): self.arrow_schema=arrow_schema();self.rows=[]
    def __getitem__(self,key):
        class Expression:
            def __eq__(self,other): return key,other
        return Expression()
    def select(self,predicate):
        import pyarrow as pa
        key,value=predicate
        table=pa.Table.from_pylist([r for r in self.rows if r[key]==value],schema=self.arrow_schema)
        return table.to_reader()
    def insert(self,rows): self.rows.extend(rows.to_pylist())


class FakeSchema:
    def __init__(self): self.value=None;self.creations=0
    def table(self,name,fail_if_missing=True):
        assert name=='shepherd_events'
        return self.value
    def create_table(self,name,columns,fail_if_exists):
        assert name=='shepherd_events' and fail_if_exists is False
        self.creations+=1;self.value=FakeTable()
        assert columns.equals(self.value.arrow_schema)
        return self.value


class FakeSession:
    def __init__(self): self.schema_value=FakeSchema();self.transactions=0
    @contextlib.contextmanager
    def transaction(self):
        self.transactions+=1
        yield self
    def bucket(self,name):
        assert name=='assigned-test-bucket'
        return self
    def schema(self,name):
        assert name=='existing-test-schema'
        return self.schema_value


class VastTests(unittest.TestCase):
    def test_literal_config_and_linux_username(self):
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'team.config'
            target.write_text('USERNAME=team-32\nPASSWORD="synthetic-secret"\nS3_ENDPOINT=http://fixture.invalid\n')
            with patch.dict(os.environ,{'USERNAME':'linux-user'},clear=True):
                config=load_config(target)
            self.assertEqual(config['USERNAME'],'team-32')
            self.assertEqual(config['PASSWORD'],'synthetic-secret')

    def test_current_report_can_be_preserved(self):
        rows=build_rows((ROOT/'docs/report.json').read_bytes(),(ROOT/'data/segments.json').read_bytes())
        report=json.loads((ROOT/'docs/report.json').read_text())
        self.assertEqual(len(rows),len(report['result']['events']))
        self.assertEqual([json.loads(r['event_json']) for r in rows],report['result']['events'])

    def test_snapshot_identity_and_separate_capture_times(self):
        a,b=fixture()
        first=build_rows(a,b,stored_at='2026-10-09T15:00:00+00:00')
        second=build_rows(a,b,stored_at='2026-10-09T16:00:00+00:00')
        self.assertEqual(first[0]['id'],second[0]['id'])
        self.assertNotEqual(first[0]['capture_start_iso'],first[0]['stored_at_utc'])
        self.assertNotEqual(first[0]['id'],build_rows(a,b+b' ')[0]['id'])
        self.assertEqual(first[0]['evidence_status'],'model_reported_unverified')

    def test_contradictions_and_nest_claims_are_preserved_with_warnings(self):
        a,b=fixture()
        report,segments=json.loads(a),json.loads(b)
        segments[0]['checks']['fight']='NO. No interaction.'
        rows=build_rows(a,json.dumps(segments).encode())
        self.assertEqual(rows[0]['evidence_status'],'contradicted_by_latest_checks')
        report['result']['events'][0]['kind']='laying'
        rows=build_rows(json.dumps(report).encode(),b)
        self.assertIn('does not establish egg laying',rows[0]['provenance_json'])

    def test_bad_report_rejected(self):
        a,b=fixture();report=json.loads(a)
        report['result']['events'][0]['clip_count']=2
        with self.assertRaises(ValueError):build_rows(json.dumps(report).encode(),b)

    def test_crop_positive_is_not_discarded_as_stale_full_frame_negative(self):
        a,b=fixture();segments=json.loads(b)
        segments[0]['checks']['fight']='NO'
        segments[0]['checks']['fight_zoom']={'center':'YES. Synthetic directed interaction.'}
        rows=build_rows(a,json.dumps(segments).encode())
        self.assertEqual(rows[0]['evidence_status'],'conflicting_model_views')
        self.assertIn('Synthetic directed interaction',rows[0]['provenance_json'])

    def test_idempotent_insert_and_committed_readback(self):
        a,b=fixture();rows=build_rows(a,b)
        config={'S3_ENDPOINT':'http://fixture.invalid','ACCESS_KEY':'synthetic','SECRET_KEY':'synthetic','VASTDB_BUCKET':'assigned-test-bucket','VDB_SCHEMA':'existing-test-schema'}
        session=FakeSession()
        result=persist(config,rows,session=session)
        self.assertEqual(result['inserted_rows'],1)
        self.assertTrue(result['storage_verified'])
        result=persist(config,build_rows(a,b),session=session)
        self.assertEqual(result['inserted_rows'],0)
        self.assertEqual(result['verified_rows'],1)
        self.assertEqual(session.schema_value.creations,1)
        self.assertEqual(session.transactions,4)

    def test_readback_mismatch_does_not_claim_success(self):
        a,b=fixture();rows=build_rows(a,b)
        config={'S3_ENDPOINT':'http://fixture.invalid','ACCESS_KEY':'synthetic','SECRET_KEY':'synthetic','VASTDB_BUCKET':'assigned-test-bucket','VDB_SCHEMA':'existing-test-schema'}
        session=FakeSession();table=FakeTable();session.schema_value.value=table
        def broken_insert(arrow):
            saved=arrow.to_pylist();saved[0]['title']='Corrupt synthetic value';table.rows.extend(saved)
        table.insert=broken_insert
        with self.assertRaises(RuntimeError):persist(config,rows,session=session)

    def test_zero_events_no_fake_rows(self):
        rows=build_rows(json.dumps({'result':{'events':[]}}).encode())
        self.assertEqual(rows,[])

    def test_pipeline_503_and_empty_archive_are_not_success(self):
        class Api:
            token='synthetic'
            def login(self):return 200
            def call(self,*args):return 503,None
        result=check({'USERNAME':'team-32'},{'neutral.mp4':'object-key'},Api())
        self.assertFalse(result['pipeline_processing_verified'])
        self.assertEqual(result['explore_http_status'],503)
        class Empty(Api):
            def call(self,*args):return 200,{'chunks':[],'total':0,'table_available':True}
        self.assertFalse(check({'USERNAME':'team-32'},{'neutral.mp4':'object-key'},Empty())['pipeline_processing_verified'])

    def test_pipeline_original_and_reasoning_are_required(self):
        class Api:
            token='synthetic'
            def login(self):return 200
            def call(self,method,path):
                if '/explore?' in path:return 200,{'chunks':[{'original_video':'s3://assigned/object-key'}],'total':1,'table_available':True}
                return 200,{'segments':[{'reasoning_content':'Real response would be here.'}]}
        result=check({'USERNAME':'team-32'},{'neutral.mp4':'object-key'},Api())
        self.assertTrue(result['all_uploads_ready'])
        class Invalid(Api):
            def call(self,method,path):
                if '/segments?' in path:return 200,{'segments':[{}]}
                return super().call(method,path)
        self.assertFalse(check({'USERNAME':'team-32'},{'neutral.mp4':'object-key'},Invalid())['pipeline_processing_verified'])


if __name__=='__main__':unittest.main()
