"""Summarize every same-session shape/task comparison without selecting sessions."""
from pathlib import Path
import argparse,csv,json,statistics
R=Path(__file__).resolve().parent
p=argparse.ArgumentParser(description=__doc__);p.add_argument('sessions',nargs='+',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(exist_ok=False)
rows=[];ratios=[];summary=[]
for session in a.sessions:
 meta=json.loads((session/'manifest.json').read_text());assert meta['status']=='COMPLETE'
 groups={}
 for x in csv.DictReader((session/'timing.csv').open()):
  key=tuple(x[k] for k in ('h','w','name','mode'));groups.setdefault(key,[]).append(float(x['ns_per_array']))
 medians={}
 for key,v in groups.items():
  assert len(v)==21,(session,key,len(v));medians[key]=statistics.median(v)
  rows.append(dict(session=meta['session'],h=int(key[0]),w=int(key[1]),name=key[2],mode=int(key[3]),median_us=medians[key]/1000,min_us=min(v)/1000,max_us=max(v)/1000,blocks=len(v)))
 for (h,w,name,mode),value in medians.items():
  if name=='bridct_dev7_plan':continue
  b=medians.get((h,w,'bridct_dev7_plan',mode))
  if b is not None:ratios.append(dict(session=meta['session'],h=int(h),w=int(w),mode=int(mode),reference=name,bridct_us=b/1000,reference_us=value/1000,reference_over_bridct=value/b,bridct_faster=b<value))
 for name in sorted({x['reference'] for x in ratios if x['session']==meta['session']}):
  v=[x for x in ratios if x['session']==meta['session'] and x['reference']==name]
  summary.append(dict(session=meta['session'],reference=name,cases=len(v),bridct_wins=sum(x['bridct_faster'] for x in v),min_ratio=min(x['reference_over_bridct'] for x in v),max_ratio=max(x['reference_over_bridct'] for x in v),scope='all supported common shapes, not only primary 8..256 squares'))
for name,data in [('medians.csv',rows),('ratios.csv',ratios)]:
 with (a.output/name).open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
(a.output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
