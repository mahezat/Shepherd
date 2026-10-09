"""Preview or persist the current report's events, without changing the application."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit

sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from vast.common import ROOT,load_config,require,emit_receipt

TABLE = 'shepherd_events'
# Use the existing team's VDB_SCHEMA, with a new sibling table.
COLUMNS = [('id','string'),('snapshot_id','string'),('report_sha256','string'),('segments_sha256','string'),
    ('kind','string'),('priority','string'),('title','string'),('capture_start_iso','string'),('capture_end_iso','string'),
    ('clip_count','int64'),('source_confirmed','bool'),('evidence_status','string'),('source_model','string'),('weave_trace_url','string'),
    ('event_json','string'),('provenance_json','string'),('report_text','string'),('stored_at_utc','string')]


def encode(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)


def sha(value): return hashlib.sha256(value).hexdigest()


def yes_no(value):
    first = str(value or '').strip().split(maxsplit=1)
    word = first[0].strip('.,:;').lower() if first else ''
    return True if word=='yes' else False if word=='no' else None


def pass_answers(value):
    if isinstance(value,dict):
        return [answer for child in value.values() for answer in pass_answers(child)]
    return [yes_no(value)]


def provenance(event,segments):
    linked = [s for s in segments if s.get('filename') in event['clips']]
    warnings = []
    check = 'fight' if event['kind']=='fight' else 'peck' if event['kind']=='peck' else None
    answers = [answer for s in linked for key in [check,check+'_zoom',check+'_slow'] for answer in pass_answers(s.get('checks',{}).get(key)) if answer is not None] if check else []
    status = 'model_reported_unverified'
    if True in answers and False in answers:
        status = 'conflicting_model_views'
        warnings.append('Full-frame, cropped or slowed views have conflicting model responses. Preserve those responses for review; multiple views of the same model are not independent confirmation.')
    elif check and answers and linked and len(linked)>=len(set(event['clips'])) and all(a is False for a in answers):
        status = 'contradicted_by_latest_checks'
        warnings.append('The latest saved yes/no responses contradict this reported event. Review the source before using it operationally.')
    if not linked:
        status = 'missing_source_evidence'
        warnings.append('No matching segment records were supplied for this event.')
    if event['kind']=='laying':
        warnings.append('Nest occupancy alone does not establish egg laying or production.')
    if event.get('confirmed'):
        warnings.append('source_confirmed preserves the report flag; repeated clips or YOLO bird presence do not independently confirm aggression or egg laying.')
    originals = sorted({s['original_video'] for s in linked if isinstance(s.get('original_video'),str) and s['original_video'].startswith('s3://')})
    direct = any(s.get('raw',{}).get('path')=='direct-to-GPU-endpoint' for s in linked)
    if not originals:
        warnings.append('No VAST original-video URI accompanies these source records; persisting results does not prove pipeline indexing or semantic search.')
    return status,{'source_clips':event['clips'],'source_checks':[{'filename':s.get('filename'),'checks':s.get('checks',{})} for s in linked],'original_video_uris':originals,'direct_gpu_source':direct,'capture_timezone':'unspecified_in_source_report','recording_timestamps_are_upload_timestamps':False,'warnings':warnings,'human_filename_labels_used_for_inference_by_this_writer':False}


def build_rows(report_bytes,segments_bytes=None,stored_at=None):
    report = json.loads(report_bytes)
    segments = json.loads(segments_bytes) if segments_bytes is not None else []
    if not isinstance(segments,list) or not all(isinstance(s,dict) for s in segments):
        raise ValueError('Segment source must be an array of records.')
    events = report.get('result',{}).get('events')
    if not isinstance(events,list): raise ValueError('Report result.events must be an array.')
    report_hash,segments_hash = sha(report_bytes),sha(segments_bytes) if segments_bytes is not None else ''
    snapshot = sha((report_hash+':'+segments_hash).encode())
    stamp = stored_at or datetime.now(timezone.utc).isoformat()
    trace = report.get('trace_url') or ''
    if trace and (not isinstance(trace,str) or urlsplit(trace).scheme!='https'):
        raise ValueError('Weave trace must be an HTTPS URL, not a serialized method.')
    model = report.get('report',{}).get('source') or report.get('model') or 'unspecified'
    rows = []
    for index,event in enumerate(events):
        if not isinstance(event,dict) or not all(isinstance(event.get(k),str) for k in ['kind','priority','title','start_iso','end_iso']):
            raise ValueError('Each event needs its type, priority, title and original capture timestamps.')
        if not isinstance(event.get('clips'),list) or not all(isinstance(c,str) for c in event['clips']):
            raise ValueError('Event clips must be a list of source filenames.')
        if type(event.get('clip_count')) is not int or event['clip_count']!=len(event['clips']):
            raise ValueError('Event clip_count does not match its evidence list.')
        if type(event.get('confirmed')) is not bool:
            raise ValueError('The source confirmation flag must be a boolean.')
        if datetime.fromisoformat(event['end_iso'])<datetime.fromisoformat(event['start_iso']):
            raise ValueError('Capture timestamps are reversed.')
        status,source = provenance(event,segments)
        ident = 'shepherd_'+sha((snapshot+':'+str(index)+':'+encode(event)).encode())[:32]
        rows.append({'id':ident,'snapshot_id':snapshot,'report_sha256':report_hash,'segments_sha256':segments_hash,
            'kind':event['kind'],'priority':event['priority'],'title':event['title'],'capture_start_iso':event['start_iso'],'capture_end_iso':event['end_iso'],
            'clip_count':event['clip_count'],'source_confirmed':event['confirmed'],'evidence_status':status,'source_model':model,'weave_trace_url':trace,
            'event_json':encode(event),'provenance_json':encode(source),'report_text':report.get('report',{}).get('text',''),'stored_at_utc':stamp})
    return rows


def arrow_schema():
    import pyarrow as pa
    types={'string':pa.string(),'int64':pa.int64(),'bool':pa.bool_()}
    return pa.schema([(key,types[kind]) for key,kind in COLUMNS])


def matching(table,snapshot):
    return [row for batch in table.select(predicate=table['snapshot_id']==snapshot) for row in batch.to_pylist()]


def persist(config,rows,session=None):
    require(config,('S3_ENDPOINT','ACCESS_KEY','SECRET_KEY','VASTDB_BUCKET','VDB_SCHEMA'))
    if not rows: return {'inserted_rows':0,'verified_rows':0,'storage_verified':False,'reason':'The current report has no events; no table was created.'}
    import pyarrow as pa
    import vastdb
    endpoint = config['S3_ENDPOINT']
    if urlsplit(endpoint).scheme not in {'http','https'}:
        raise ValueError('S3_ENDPOINT must be the HTTP/HTTPS data VIP from the assigned config.')
    session = session or vastdb.connect(endpoint=endpoint,access=config['ACCESS_KEY'],secret=config['SECRET_KEY'])
    expected_schema = arrow_schema()
    # No bucket override, schema creation, protected-table writes or table drops.
    with session.transaction() as tx:
        schema = tx.bucket(config['VASTDB_BUCKET']).schema(config['VDB_SCHEMA'])
        table = schema.table(TABLE,fail_if_missing=False)
        if table is None:
            table = schema.create_table(TABLE,columns=expected_schema,fail_if_exists=False)
        if not table.arrow_schema.equals(expected_schema):
            raise ValueError('Existing shepherd_events columns differ; refusing to alter or recreate the table.')
        existing = {r['id']:r for r in matching(table,rows[0]['snapshot_id'])}
        for row in rows:
            prior = existing.get(row['id'])
            if prior and any(prior[k]!=v for k,v in row.items() if k!='stored_at_utc'):
                raise ValueError('Existing event identity conflicts with the input snapshot.')
        pending = [r for r in rows if r['id'] not in existing]
        if pending: table.insert(pa.Table.from_pylist(pending,schema=expected_schema))
    # Separate committed transaction proves data survived the write.
    with session.transaction() as tx:
        table = tx.bucket(config['VASTDB_BUCKET']).schema(config['VDB_SCHEMA']).table(TABLE)
        verified = matching(table,rows[0]['snapshot_id'])
    for row in rows:
        matches = [r for r in verified if r['id']==row['id']]
        if len(matches)!=1 or any(matches[0][k]!=v for k,v in row.items() if k!='stored_at_utc'):
            raise RuntimeError('VastDB committed read-back did not match the source snapshot exactly.')
    return {'inserted_rows':len(pending),'verified_rows':len(rows),'storage_verified':True,'verified_event_ids':[r['id'] for r in rows]}


def main():
    parser = argparse.ArgumentParser(description='Persist report events to the assigned team VastDB')
    parser.add_argument('--config',type=Path)
    parser.add_argument('--report',type=Path,default=ROOT/'docs/report.json')
    parser.add_argument('--segments',type=Path,default=ROOT/'data/segments.json')
    parser.add_argument('--write',action='store_true',help='After reviewing the printed target and columns, create/insert/read back the event rows')
    args = parser.parse_args()
    report_bytes = args.report.read_bytes()
    rows = build_rows(report_bytes,args.segments.read_bytes() if args.segments.exists() else None)
    config = load_config(args.config)
    require(config,('VDB_SCHEMA','VASTDB_BUCKET'))
    plan = {'team':config['USERNAME'],'bucket':config['VASTDB_BUCKET'],'schema':config['VDB_SCHEMA'],'table':TABLE,'columns':COLUMNS,'event_count':len(rows),'snapshot_id':rows[0]['snapshot_id'] if rows else None,
        'events':[{'id':r['id'],'kind':r['kind'],'priority':r['priority'],'evidence_status':r['evidence_status']} for r in rows],
        'operation':'create new sibling table if absent; append missing snapshot rows; preserve existing tables','write_requested':args.write}
    emit_receipt('vast-write-plan.json',plan)
    if not args.write: return
    outcome = persist(config,rows)
    result = {**{k:plan[k] for k in ['team','bucket','schema','table','snapshot_id','event_count']},**outcome,'written_at_utc':datetime.now(timezone.utc).isoformat(),
        'source_report_sha256':sha(report_bytes),'pipeline_indexing_verified_by_this_write':False,'semantic_search_verified_by_this_write':False}
    emit_receipt('vast-write-receipt.json',result)


if __name__=='__main__':
    try: main()
    except Exception as error:
        # SDK/network exception messages can include service URLs and credentials.
        print('VAST write unavailable ('+type(error).__name__+'). Inspect the assigned config, permissions and table schema on the VM; no credentials were printed.',file=sys.stderr)
        raise SystemExit(1)
