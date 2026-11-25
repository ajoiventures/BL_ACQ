"""Explicit local foreground API driver. No unattended service or auto-resume of paused runs.
On transport uncertainty stop; next invocation reads durable checkpoint before advancing.
"""
import argparse,json,os,urllib.request,urllib.error


def drive(call,run_id,max_batches):
    if not 1<=max_batches<=10000:raise ValueError('Invalid batch budget')
    r=call('/'+run_id)
    advanced=0
    while advanced<max_batches and r['state'] in ('READY','RUNNING'):
        r=call('/'+run_id+'/step',{'version':r['version'],'action':'advance'})
        advanced+=1
    return {'run_id':run_id,'steps_this_invocation':advanced,'cursor':r['cursor'],'total':r['total'],'state':r['state'],'version':r['version'],'actual_backend':r['actual_backend'],'error':r['error']}


def main():
    p=argparse.ArgumentParser();p.add_argument('run_id');p.add_argument('--max-batches',type=int,default=10);a=p.parse_args()
    import uuid
    try:uuid.UUID(a.run_id)
    except ValueError:p.error('Expected run UUID')
    token=os.environ.get('BR_FOUNDER_TOKEN')
    if not token:p.error('Set BR_FOUNDER_TOKEN in environment; do not pass in command arguments')
    def call(path,body=None):
        req=urllib.request.Request('http://127.0.0.1:8000/api/acquisition-runs'+path,data=None if body is None else json.dumps(body).encode(),headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
        with urllib.request.urlopen(req,timeout=120) as response:return json.load(response)
    try:
        r=drive(call,a.run_id,a.max_batches);print(json.dumps(r,indent=2));return 2 if r['state']=='FAILED' else 0
    except (OSError,ValueError) as e:
        print(json.dumps({'state':'STOPPED_UNCERTAIN','reason':str(e),'next_action':'Read saved run before retrying; no automatic replay.'}));return 2
if __name__=='__main__':raise SystemExit(main())
