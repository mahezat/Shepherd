import json
import os
from pathlib import Path
import re
import shlex
import ssl
from urllib.parse import urlsplit
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
KEYS = ('USERNAME','PASSWORD','INGRESS_URL','S3_ENDPOINT','ACCESS_KEY','SECRET_KEY','VASTDB_BUCKET','VDB_SCHEMA')


def load_config(path=None):
    explicit = path or os.environ.get('SHEPHERD_VAST_CONFIG')
    candidates = [Path(explicit)] if explicit else sorted(Path('/config').glob('*.config'))
    if len(candidates) != 1 or not candidates[0].is_file():
        raise ValueError('Expected one /config/*.config; use --config to select the assigned team file.')
    result = {}
    for raw in candidates[0].read_text().splitlines():
        line = raw.strip().removeprefix('export ')
        if not re.match(r'^[A-Z0-9_]+=',line):
            continue
        key,value = line.split('=',1)
        parts = shlex.split(value,comments=True)
        if len(parts)>1:
            raise ValueError('Config values must be literal, optionally quoted assignments.')
        result[key] = parts[0] if parts else ''
    # USERNAME is a Linux shell variable on some VMs; preserve the team-file value.
    for key in KEYS:
        if key!='USERNAME' and os.environ.get(key):
            result[key] = os.environ[key]
    if not re.fullmatch(r'team-\d+',result.get('USERNAME','')):
        raise ValueError('Config must identify the assigned team namespace.')
    return result


def require(config,keys):
    missing = [key for key in keys if not config.get(key)]
    if missing:
        raise ValueError('Missing configuration names: '+', '.join(missing))


class Backend:
    """Read-only service probes plus ordinary team login. Never logs tokens/URLs."""
    def __init__(self,config,opener=None):
        require(config,('INGRESS_URL','USERNAME','PASSWORD'))
        self.base = config['INGRESS_URL'].rstrip('/')
        if urlsplit(self.base).scheme not in {'http','https'}:
            raise ValueError('INGRESS_URL must be an HTTP or HTTPS service URL.')
        self.config,self.token = config,None
        self.opener = opener or urllib.request.build_opener(urllib.request.HTTPSHandler(context=ssl.create_default_context()))

    def call(self,method,path,body=None):
        headers = {'Content-Type':'application/json'}
        if self.token: headers['Authorization']='Bearer '+self.token
        request = urllib.request.Request(self.base+path, data=json.dumps(body).encode() if body is not None else None,headers=headers,method=method)
        try:
            with self.opener.open(request,timeout=30) as response:
                return response.status,json.loads(response.read())
        except urllib.error.HTTPError as error:
            return error.code,None
        except (urllib.error.URLError,TimeoutError,OSError,json.JSONDecodeError):
            return None,None

    def login(self):
        status,data = self.call('POST','/api/v1/auth/login',{'username':self.config['USERNAME'],'password':self.config['PASSWORD']})
        if status==200 and isinstance(data,dict) and data.get('access_token'):
            self.token = data['access_token']
            return status
        return status if status!=200 else None


def emit_receipt(filename,result):
    target = ROOT/'out'/filename
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,indent=2,allow_nan=False))
    print(json.dumps(result,indent=2,allow_nan=False))
    return target
