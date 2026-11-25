"""Independent local review CLI; requires a separately supplied audit token."""
import os,argparse,json,urllib.request
p=argparse.ArgumentParser();p.add_argument('record_id');p.add_argument('--version',type=int,required=True);p.add_argument('--evidence',required=True);a=p.parse_args()
token=os.environ.get('BR_AUDIT_TOKEN')
if not token:raise SystemExit('Set BR_AUDIT_TOKEN from the local operator credential store. Do not use a founder token.')
body={'target':'COMPLETED_SIMULATION','version':a.version,'evidence':a.evidence}
r=urllib.request.Request('http://127.0.0.1:8000/api/records/'+a.record_id+'/transition',data=json.dumps(body).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+token})
print(urllib.request.urlopen(r).read().decode())
