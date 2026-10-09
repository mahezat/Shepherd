"""Run on the VM: python3 -u vast/check_pipeline.py [--export-if-processing]."""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlencode

sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from vast.common import ROOT,Backend,load_config,emit_receipt


def page_items(data):
    if isinstance(data,list): return data
    if isinstance(data,dict):
        for key in ['chunks','items','videos','results']:
            if isinstance(data.get(key),list): return data[key]
    return []


def indexed_uploads(items,uploads):
    found = {}
    for name,key in uploads.items():
        for item in items:
            if not isinstance(item,dict): continue
            if key in json.dumps(item):
                original = item.get('original_video')
                if isinstance(original,str) and original.startswith('s3://'):
                    found[name] = original
                    break
    return found


def check(config,uploads,backend=None):
    api = backend or Backend(config)
    result = {'checked_at_utc':datetime.now(timezone.utc).isoformat(),'team':config['USERNAME'],'expected_uploads':len(uploads),'indexed_uploads':0,'reasoned_uploads':0,'pipeline_processing_verified':False,'all_uploads_ready':False,'indexing_claim':'not_verified','export_ran':False}
    result['login_http_status'] = api.login()
    if not api.token:
        result['next_step']='Backend authentication is unavailable. Ask event staff to check this team backend/DataEngine.'
        return result
    items,offset = [],0
    while offset<10000:
        status,data = api.call('GET','/api/v1/videos/explore?'+urlencode({'scope':'mine','location':'coop','limit':100,'offset':offset}))
        result['explore_http_status'] = status
        if status!=200 or not isinstance(data,(dict,list)):
            result['next_step']='Explore is unavailable. Ask event staff to check backend readiness and DataEngine ingestion.'
            return result
        if isinstance(data,dict):
            result['table_available'] = data.get('table_available')
            if data.get('table_available') is False:
                result['next_step']='Explore responds, but the VSS table is unavailable. Ask staff to check pipeline/table readiness.'
                return result
        page = page_items(data)
        items.extend(page)
        offset += len(page)
        total = data.get('total') if isinstance(data,dict) else None
        if not page or len(page)<100 or (isinstance(total,int) and offset>=total): break
    found = indexed_uploads(items,uploads)
    result['indexed_uploads'] = len(found)
    for original in found.values():
        status,data = api.call('GET','/api/v1/tools/segments?'+urlencode({'original_video':original}))
        if status!=200: continue
        segments = data if isinstance(data,list) else next((data[k] for k in ['segments','items','results','data'] if isinstance(data,dict) and isinstance(data.get(k),list)),[])
        if segments and all(isinstance(s,dict) and any(isinstance(s.get(k),str) and s[k].strip() for k in ['reasoning_content','reasoning','caption','description','text']) for s in segments):
            result['reasoned_uploads'] += 1
    result['pipeline_processing_verified'] = result['reasoned_uploads']>0
    result['all_uploads_ready'] = bool(uploads) and result['reasoned_uploads']==len(uploads)
    result['indexing_claim'] = 'originals_and_reasoning_verified' if result['all_uploads_ready'] else 'partial' if result['reasoned_uploads'] else 'not_verified'
    result['next_step'] = 'Run the teammate export command.' if result['pipeline_processing_verified'] else 'No completed processing of these uploads is visible. Ask staff to inspect DataEngine processing for the 15:04 UTC batch.'
    return result


def pod_status(config):
    path = Path('/config')/(config['USERNAME']+'-k8s.yaml')
    if not path.is_file(): return {'available':False}
    try:
        completed = subprocess.run(['kubectl','-n',config['USERNAME'],'get','pods','-o','json'],capture_output=True,text=True,timeout=30,env={**os.environ,'KUBECONFIG':str(path)})
        if completed.returncode: return {'available':False}
        data = json.loads(completed.stdout)
        return {'available':True,'pods':[{'name':p['metadata']['name'],'phase':p.get('status',{}).get('phase'),'containers':[{'name':c['name'],'ready':c.get('ready',False),'restarts':c.get('restartCount',0),'waiting_reason':c.get('state',{}).get('waiting',{}).get('reason')} for c in p.get('status',{}).get('containerStatuses',[])]} for p in data.get('items',[])]}
    except (OSError,subprocess.TimeoutExpired,json.JSONDecodeError): return {'available':False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config',type=Path)
    parser.add_argument('--export-if-processing',action='store_true')
    parser.add_argument('--pods',action='store_true',help='Read status only in the assigned team namespace')
    args = parser.parse_args()
    config = load_config(args.config)
    uploads = json.loads((ROOT/'data/uploads.json').read_text())
    result = check(config,uploads)
    if args.pods: result['team_pods'] = pod_status(config)
    emit_receipt('vast-pipeline-check.json',result)
    if args.export_if_processing and result['pipeline_processing_verified']:
        # Keep the direct-GPU output safe: the existing exporter can replace it
        # with a partial result. Do not alter or reimplement the teammate script.
        source = ROOT/'data/segments.json'
        backup = ROOT/'out'/('segments-before-vast-export-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'.json')
        if source.exists(): backup.write_bytes(source.read_bytes())
        completed = subprocess.run([sys.executable,'-u','scripts/vm_ingest.py','--export'],cwd=ROOT)
        result = {**check(config,uploads),'export_ran':True,'export_exit_code':completed.returncode,'pre_export_backup':str(backup.relative_to(ROOT))}
        emit_receipt('vast-pipeline-check.json',result)
    if not result['all_uploads_ready']: raise SystemExit(2)


if __name__=='__main__':
    try: main()
    except (ValueError,KeyError,OSError) as error:
        print('Pipeline check unavailable ('+type(error).__name__+'). Check the assigned config, data/uploads.json and service status locally.',file=sys.stderr)
        raise SystemExit(1)
