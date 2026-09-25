"""Record two fresh-process BRiDCT-only sessions without adjusting measured times."""
import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import platform
import subprocess
import sys
from datetime import datetime, timezone


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--binary',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--execution',required=True,choices=('native','translated'))
    p.add_argument('--height',type=int,default=16)
    p.add_argument('--width',type=int,default=16)
    p.add_argument('--batch',type=int,default=4)
    p.add_argument('--mode',type=int,choices=(0,1,2),default=0)
    p.add_argument('--blocks',type=int,default=21)
    p.add_argument('--target-ms',type=int,default=30)
    args=p.parse_args()
    if args.output.exists():p.error('Output directory must be new')
    args.output.mkdir(parents=True)
    binary=args.binary.resolve()
    command=[str(binary),*[str(x) for x in (args.height,args.width,args.batch,args.mode,args.blocks,args.target_ms)]]
    config=binary.parent/'config'
    meta=dict(status='INCOMPLETE',scope='BRiDCT-only warmed API timing; no library ranking.',
              execution=args.execution,host=platform.platform(),host_machine=platform.machine(),
              python=sys.version,command=command,utc=datetime.now(timezone.utc).isoformat(),
              executable_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
              build_config=config.read_text() if config.exists() else None)
    metadata=args.output/'metadata.json'
    def save():metadata.write_text(json.dumps(meta,indent=2)+'\n')
    save()
    for session in (1,2):
        result=subprocess.run(command,capture_output=True,text=True)
        (args.output/f'session{session}.csv').write_text(result.stdout)
        (args.output/f'session{session}.stderr').write_text(result.stderr)
        if result.returncode:
            meta.update(status='FAILED',returncode=result.returncode);save()
            raise RuntimeError('Benchmark failed; output retained')
        rows=list(csv.DictReader(io.StringIO(result.stdout)))
        if len(rows)!=args.blocks:raise RuntimeError('Wrong block count')
        for block,row in enumerate(rows):
            elapsed=float(row['elapsed_ns']);per=float(row['ns_per_array'])
            iterations=int(row['iterations'])
            assert int(row['height'])==args.height and int(row['width'])==args.width
            assert int(row['batch'])==args.batch and int(row['block'])==block
            assert row['mode']==('forward','inverse','roundtrip')[args.mode]
            assert iterations>0 and elapsed>0 and math.isfinite(elapsed)
            assert math.isfinite(float(row['checksum']))
            assert math.isclose(per,elapsed/(iterations*args.batch),rel_tol=1e-5,abs_tol=1e-5)
        meta[f'session{session}_short_blocks']=sum(float(r['elapsed_ns'])<args.target_ms*1e6 for r in rows)
        meta[f'session{session}_minimum_ns']=min(float(r['elapsed_ns']) for r in rows)
        save()
    meta.update(status='COMPLETE',measurements=args.blocks*2,baseline_subtracted=False)
    save();print(json.dumps(meta,indent=2))

if __name__=='__main__':main()
