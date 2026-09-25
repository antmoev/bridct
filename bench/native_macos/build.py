"""Build optional Apple Silicon native comparators from explicit dependency paths."""
from pathlib import Path
import argparse,hashlib,json,platform,subprocess,sys
R=Path(__file__).resolve().parent;P=R.parent.parent

def main():
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('--fftw-root',required=True,type=Path,help='Configured FFTW 3.3.11 tree with .libs/libfftw3f.a')
 ap.add_argument('--libjxl-root',required=True,type=Path)
 ap.add_argument('--highway-root',required=True,type=Path)
 ap.add_argument('--jpeg-library',required=True,type=Path,help='libjpeg-turbo 3.2.0 libjpeg.a')
 ap.add_argument('--cc',default=None);ap.add_argument('--cxx',default=None);ap.add_argument('--sdk',default=None);ap.add_argument('--jobs',type=int,default=2)
 a=ap.parse_args()
 if sys.platform!='darwin' or platform.machine()!='arm64':ap.error('This optional vDSP/NEON benchmark requires native Apple Silicon macOS; the BRiDCT library itself is portable.')
 if a.jobs<1:ap.error('--jobs must be positive')
 fftw=a.fftw_root.resolve();jxl=a.libjxl_root.resolve();hwy=a.highway_root.resolve();jpeg=a.jpeg_library.resolve()
 for d in (fftw,jxl,hwy,jpeg):
  if d.is_relative_to(P):ap.error('Keep optional third-party dependency trees outside the BRiDCT source folder.')
 required=[fftw/'api/fftw3.h',fftw/'.libs/libfftw3f.a',jxl/'lib/jxl/dct-inl.h',hwy/'hwy/highway.h',hwy/'hwy/abort.cc',jpeg]
 for f in required:
  if not f.is_file():ap.error('Missing dependency: '+str(f))
 cc=a.cc or subprocess.check_output(['xcrun','--find','clang'],text=True).strip()
 cxx=a.cxx or subprocess.check_output(['xcrun','--find','clang++'],text=True).strip()
 sdk=a.sdk or subprocess.check_output(['xcrun','--show-sdk-path'],text=True).strip()
 O=R/'build';O.mkdir(exist_ok=True);commands=[]
 def run(argv,cwd=R):
  command=list(map(str,argv));commands.append(dict(argv=command,cwd=str(cwd)));subprocess.run(command,cwd=cwd,check=True)
 run(['make','-j'+str(a.jobs),'BUILD='+str(O/'bridct'),'CC='+cc,'SDKROOT='+sdk,str(O/'bridct/libbridct.a')],P)
 run([sys.executable,P/'bench/build_small_controls.py','--output',O/'controls','--library',O/'bridct/libbridct.a','--cc',cc])
 flags=['-O3','-std=c11','-fPIC','-isysroot',sdk,'-ffp-contract=off']
 run([cc,*flags,'-c',R/'vendor/ooura_float.c','-o',O/'ooura.o'])
 cpp=['-O3','-std=c++17','-fPIC','-isysroot',sdk,'-ffp-contract=off','-I'+str(jxl),'-I'+str(hwy),'-DHWY_COMPILE_ONLY_STATIC','-DNDEBUG']
 run([cxx,*cpp,'-c',R/'libjxl_wrapper.cc','-o',O/'libjxl.o'])
 run([cxx,*cpp,'-c',hwy/'hwy/abort.cc','-o',O/'abort.o'])
 run([cc,*flags,'-I'+str(P/'include'),'-I'+str(fftw/'api'),'-c',R/'harness.c','-o',O/'harness.o'])
 objects=[O/'harness.o',O/'ooura.o',O/'libjxl.o',O/'abort.o',O/'controls/ooura_neon_f1.o',O/'controls/ooura_trusted_f1.o',O/'controls/ooura_public_f1.o']
 run([cxx,'-isysroot',sdk,'-dynamiclib',*objects,O/'bridct/libbridct.a',fftw/'.libs/libfftw3f.a',jpeg,'-framework','Accelerate','-o',O/'native.dylib'])
 paths=[*P.glob('src/*.c'),*P.glob('src/*.h'),*P.glob('src/generated/*'),P/'Makefile',P/'VERSION',P/'include/bridct.h',R/'harness.c',R/'libjxl_wrapper.cc',R/'run.py',Path(__file__),R/'vendor/ooura_float.c',*required,O/'native.dylib',O/'bridct/libbridct.a']
 manifest=dict(status='BUILT',version=(P/'VERSION').read_text().strip(),compiler=subprocess.check_output([cc,'--version'],text=True),commands=commands,dependencies=json.loads((R/'DEPENDENCIES.json').read_text()),sha256={str(f.relative_to(P)) if f.is_relative_to(P) else str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in paths if f.is_file()},protocol_sha256=hashlib.sha256((R/'PROTOCOL.md').read_bytes()).hexdigest())
 (O/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
if __name__=='__main__':main()
