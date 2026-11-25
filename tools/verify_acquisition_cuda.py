"""Run on the actual NVIDIA workstation. No silent CPU fallback or install.
Parity is exact for integer/boolean results, not a proof of upstream data quality.
"""
import argparse, hashlib, json, platform, subprocess, sys, time
from pathlib import Path
import numpy as np
from backend.core.acquisition_batch import backend, screen, BackendUnavailable, MAX_BATCH
from tools.run_acquisition_batch import synthetic_batch


def compare(reference, candidate):
    if set(reference)!=set(candidate):raise ValueError('Output fields differ')
    return [k for k in sorted(reference) if reference[k].shape!=candidate[k].shape or reference[k].dtype!=candidate[k].dtype or not np.array_equal(reference[k],candidate[k])]


def verify(records,batch_size):
    if records<1 or not 1<=batch_size<=MAX_BATCH:raise ValueError('Invalid batch size or count')
    report={'records_requested':records,'batch_size':batch_size,'actual_backend':None,'gpu_records_compared':0,'status':'BACKEND_UNAVAILABLE','python':sys.version.split()[0],'platform':platform.platform(),'numpy':np.__version__,'synthetic':True}
    try:
        p=subprocess.run(['nvidia-smi','--query-gpu=name,memory.total,driver_version','--format=csv,noheader'],capture_output=True,text=True,timeout=15,check=True)
        report['nvidia_smi']=p.stdout.strip()
    except (OSError,subprocess.SubprocessError) as e:report['nvidia_smi_error']=type(e).__name__
    try:cp=backend('cuda')
    except BackendUnavailable as e:report['error']=str(e);return report
    report['device']={'id':cp.cuda.Device().id,'cupy':cp.__version__,'driver_version':cp.cuda.runtime.driverGetVersion(),'runtime_version':cp.cuda.runtime.runtimeGetVersion()}
    report['device']['free_total_bytes_before']=list(cp.cuda.runtime.memGetInfo())
    report['actual_backend']='cuda';report['status']='RUNNING';cpu_s=gpu_s=0;mem=[];receipts=[]
    for start in range(0,records,batch_size):
        a=synthetic_batch(start,min(batch_size,records-start))
        t=time.perf_counter();ref,_=screen(a,'cpu_reference');cpu_s+=time.perf_counter()-t
        try:
            t=time.perf_counter();gpu,timing=screen(a,'cuda');gpu_s+=time.perf_counter()-t
        except Exception as e:
            report.update(status='CUDA_EXECUTION_FAILED',error=f'{type(e).__name__}: {e}',receipts=receipts);return report
        mismatch=compare(ref,gpu)
        if mismatch:
            report.update(status='PARITY_FAILED',mismatch_fields=mismatch,first_failed_batch_start=start,receipts=receipts);return report
        report['gpu_records_compared']+=len(a['legal_units']);mem.append(cp.get_default_memory_pool().total_bytes());receipts.append({'start':start,'end_exclusive':report['gpu_records_compared'],'timing':timing,'output_sha256':hashlib.sha256(b''.join(gpu[k].tobytes() for k in sorted(gpu))).hexdigest()})
    report.update(status='EXACT_PARITY_PASSED',cpu_wall_s=cpu_s,cuda_wall_s=gpu_s,cupy_pool_reserved_bytes_max_observed=max(mem),receipts=receipts)
    report['limitations']=['Synthetic numerical workload only.','CuPy reserved pool size sampled after each batch is not measured peak device usage.','No geographic joins, persistent pipeline, property evidence or investment approval.']
    return report


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--records',type=int,default=2_400_000);p.add_argument('--batch',type=int,default=100_000);a=p.parse_args()
    result=verify(a.records,a.batch)
    with a.output.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k!='receipts'},indent=2))
    return 0 if result['status']=='EXACT_PARITY_PASSED' else 2
if __name__=='__main__':raise SystemExit(main())
