"""Compile optional attributed controls with the same C compiler as BRiDCT."""
from pathlib import Path
import argparse,hashlib,json,os,platform,re,shlex,subprocess,sys
R=Path(__file__).resolve().parent;P=R.parent

def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def build(output,library,cc,extra):
    output.mkdir(parents=True,exist_ok=True);commands=[]
    version=subprocess.check_output([cc,'--version'],text=True)
    novec=['-fno-vectorize','-fno-slp-vectorize'] if 'clang' in version.lower() else ['-fno-tree-vectorize','-fno-tree-slp-vectorize']
    flags=['-std=c11','-pedantic-errors','-O3','-Wall','-Wextra','-Wno-unused-function','-Wno-unused-variable','-Wno-unused-parameter','-fPIC','-ffp-contract=fast','-I'+str(P/'include'),'-I'+str(P/'src'),'-I'+str(P/'src/generated'),'-isystem',str(P/'third_party/simde'),*shlex.split(extra)]
    suffix='.dll' if os.name=='nt' else '.dylib' if sys.platform=='darwin' else '.so'
    shared=['-dynamiclib'] if sys.platform=='darwin' else ['-shared']
    if os.name=='nt':shared+=['-Wl,--export-all-symbols']
    if sys.platform=='darwin':flags+=['-arch',platform.machine(),'-isysroot','/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk']
    def run(command):
        commands.append(command);subprocess.run(command,check=True)
    objects=[]
    def compile(source,name,options):
        obj=output/(name+'.o');run([cc,*flags,*options,'-DNAME='+name,'-c',str(source),'-o',str(obj)]);objects.append(obj)
    original=R/'controls/ooura_local.c';source=original.read_text().replace('#include <arm_neon.h>','#include "bridct_simd.h"')
    local=output/'ooura_local.c';local.write_text(source)
    condition='if(!x||!y||!w||(n!=8&&n!=16)||retain<0||retain>1||mode<0||mode>2)return -1;size_t m=(size_t)n*n;if(count<4*m)return -2;'
    assert source.count(condition)==1
    trusted=output/'ooura_trusted.c';trusted.write_text(source.replace(condition,'(void)count;size_t m=(size_t)n*n;'))
    compile(P/'src/generated/small.c','baseline_f1',novec)
    for kind,extra_flags in [('scalar',['-DEXPLICIT_NEON=0',*novec]),('auto',['-DEXPLICIT_NEON=0']),('neon',['-DEXPLICIT_NEON=1',*novec])]:compile(local,'ooura_'+kind+'_f1',extra_flags)
    compile(trusted,'ooura_trusted_f1',['-DEXPLICIT_NEON=1',*novec])
    source=(R/'controls/shrtdct_original.c').read_text().replace('double','float').replace('ddct8x8s','public8').replace('ddct16x16s','public16')
    source=re.sub(r'(?m)^(#define\s+\w+\s+)([0-9]+\.[0-9]+)\s*$',r'\1\2f',source)
    (output/'ooura_public_float.c').write_text(source)
    compile(R/'controls/public_wrapper.c','ooura_public_f1',['-I'+str(output)])
    wrapper=output/'selected_wrapper.c'
    wrapper.write_text('''#include "bridct.h"
int bridct_small_optimized_f1(int,int,int,const float*,float*,float*,size_t);
int selected_kernel(int n,int v,int m,const float*x,float*y,float*w,size_t count)
{(void)v;return bridct_small_optimized_f1(n,n==8&&m==2?1:2,m,x,y,w,count);}
int selected_api(int n,int v,int m,const float*x,float*y,float*w,size_t count)
{(void)v;return bridct_apply(n,(enum bridct_mode)m,x,y,w,count);}
''')
    compile(wrapper,'unused_wrapper_name',novec)
    lib=output/('controls'+suffix);timer=output/('kernel_timer'+suffix)
    run([cc,*flags,*shared,*map(str,objects),str(library),'-lm','-o',str(lib)])
    run([cc,*flags,*novec,*shared,str(R/'kernel_timer.c'),'-o',str(timer)])
    paths=[*objects,lib,timer,original,R/'controls/shrtdct_original.c',local,trusted,wrapper,library,R/'kernel_timer.c',Path(__file__)]
    manifest={'status':'BUILT','compiler':version,'commands':commands,'host':platform.platform(),'cpu':platform.processor(),'architecture':platform.machine(),'library':str(library),'sha256':{str(p):digest(p) for p in paths},'conversion':'Public double source mechanically converted to float; local SIMD control is attributed separately; trusted variant removes argument checks only.'}
    (output/'build.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return lib,timer

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,default=R/'build-controls');p.add_argument('--library',type=Path,default=P/'build/libbridct.a');p.add_argument('--cc',default=os.environ.get('CC','/Library/Developer/CommandLineTools/usr/bin/clang' if sys.platform=='darwin' else 'clang'));p.add_argument('--extra-flags',default='');a=p.parse_args();build(a.output.resolve(),a.library.resolve(),a.cc,a.extra_flags)
