"""Emit the selected SJ layouts without changing their arithmetic or tables."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'src/generated/small_optimized.c'

PRELUDE = '''#include <stddef.h>
#include "bridct_simd.h"
typedef float K;
typedef float32x4_t T;
static inline T zero(void) { return vdupq_n_f32(0.f); }
static inline T add(T a, T b) { return vaddq_f32(a, b); }
static inline T neg(T a) { return vnegq_f32(a); }
static inline T mul(T a, K b) { return vmulq_n_f32(a, b); }
#include "tables.inc"
#include "sj_body.inc"
#ifndef NAME
#define NAME bridct_small_optimized_f1
#endif

static inline __attribute__((always_inline)) void tr4(T a, T b, T c, T d, T *z)
{
    float32x4x2_t u = vtrnq_f32(a, b), v = vtrnq_f32(c, d);
    z[0] = vcombine_f32(vget_low_f32(u.val[0]), vget_low_f32(v.val[0]));
    z[1] = vcombine_f32(vget_low_f32(u.val[1]), vget_low_f32(v.val[1]));
    z[2] = vcombine_f32(vget_high_f32(u.val[0]), vget_high_f32(v.val[0]));
    z[3] = vcombine_f32(vget_high_f32(u.val[1]), vget_high_f32(v.val[1]));
}
'''


def verify_policy():
    policy = json.loads((ROOT / 'small_policy.json').read_text())
    expected = [(n, mode, 'registers' if n == 8 and mode == 2 else 'fused_transpose', 1 if n == 8 and mode == 2 else 2, 1)
                for n in (8, 16) for mode in range(3)]
    actual = [(p['size'], p['mode'], p['layout'], p['variant'], p['fma']) for p in policy['choices']]
    if actual != expected or policy['factorization'] != 'Shao-Johnson':
        raise ValueError('Unsupported small-kernel policy; update the generator and validation together.')
    if policy.get('arm_clang_inverse16', {}).get('loop_unroll') != 'full':
        raise ValueError('Expected the validated ARM Clang inverse16 policy')
    for name, digest in policy['arithmetic_sha256'].items():
        path = ROOT / 'src/generated' / name
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError(f'Arithmetic source changed: {name}')


def fused_pass(n, direction):
    return f'''
static inline __attribute__((always_inline)) void pass_{direction}{n}(
    const float *restrict x, float *restrict y,
    const float *scale_in, const float *scale_out, int transpose)
{{
    T u[{n}], v[{n}], z[4];
    for (int col = 0; col < {n}; col += 4) {{
        for (int k = 0; k < {n}; k++) {{
            u[k] = vld1q_f32(x + k*{n} + col);
            if (scale_in)
                u[k] = vmulq_f32(u[k], vld1q_f32(scale_in + k*{n} + col));
        }}
        one_{direction}{n}(u, v);
        if (transpose) {{
            for (int row = 0; row < {n}; row += 4) {{
                tr4(v[row], v[row+1], v[row+2], v[row+3], z);
                for (int k = 0; k < 4; k++) {{
                    T a = z[k];
                    if (scale_out)
                        a = vmulq_f32(a, vld1q_f32(scale_out + (col+k)*{n} + row));
                    vst1q_f32(y + (col+k)*{n} + row, a);
                }}
            }}
        }} else {{
            for (int k = 0; k < {n}; k++) {{
                T a = v[k];
                if (scale_out)
                    a = vmulq_f32(a, vld1q_f32(scale_out + k*{n} + col));
                vst1q_f32(y + k*{n} + col, a);
            }}
        }}
    }}
}}
'''


def fused_transform(n):
    text = f'''
static void fused{n}(int mode, const float *restrict x,
                    float *restrict y, float *restrict w)
{{
    float *a = w, *b = w + {n*n};
    if (mode == 0) {{
        pass_f{n}(x, a, NULL, NULL, 1);
        pass_f{n}(a, y, NULL, norm_sj{n}, 1);
    }} else if (mode == 1) {{
        pass_t{n}(x, a, norm_sj{n}, NULL, 1);
        pass_t{n}(a, y, NULL, NULL, 1);
    }}'''
    if n == 16:
        text += f''' else {{
        pass_f{n}(x, a, NULL, NULL, 1);
        pass_f{n}(a, b, NULL, NULL, 0);
        pass_t{n}(b, a, corr_sj{n}, NULL, 1);
        pass_t{n}(a, y, NULL, NULL, 0);
    }}'''
    return text + '\n}\n'


def register_roundtrip():
    lines = ['\nstatic void registers8_2(const float *restrict x, float *restrict y)\n',
             '{\n    T a[2][8], b[2][8], z[4];\n']
    for col in range(2):
        for row in range(8):
            lines.append(f'    a[{col}][{row}] = vld1q_f32(x + {row*8+col*4});\n')
    for stage, direction in enumerate('fftt'):
        lines.append(f'    one_{direction}8(a[0], b[0]);\n    one_{direction}8(a[1], b[1]);\n')
        if stage in (0, 2):
            for row in range(2):
                for col in range(2):
                    lines.append(f'    tr4(b[{col}][{4*row}], b[{col}][{4*row+1}], '
                                 f'b[{col}][{4*row+2}], b[{col}][{4*row+3}], z);\n')
                    for k in range(4):
                        lines.append(f'    a[{row}][{4*col+k}] = z[{k}];\n')
        else:
            for row in range(8):
                for col in range(2):
                    lines.append(f'    a[{col}][{row}] = b[{col}][{row}];\n')
        if stage == 1:
            for row in range(8):
                for col in range(2):
                    lines.append(f'    a[{col}][{row}] = vmulq_f32(a[{col}][{row}], '
                                 f'vld1q_f32(corr_sj8 + {row*8+col*4}));\n')
    for row in range(8):
        for col in range(2):
            lines.append(f'    vst1q_f32(y + {row*8+col*4}, a[{col}][{row}]);\n')
    lines.append('}\n')
    return ''.join(lines)


def specialize_inverse16(source):
    start = source.index('static inline __attribute__((always_inline)) void pass_t16(')
    end = source.index('\nstatic void fused16(', start)
    helper = source[start:end].replace('void pass_t16(', 'void pass_t16_inverse(')
    helper = helper.replace(
        '    for (int col = 0; col < 16; col += 4)',
        '    #pragma clang loop unroll(full)\n    for (int col = 0; col < 16; col += 4)')
    helper = ('#if defined(__aarch64__) && defined(__clang__)\n' + helper +
              '\n#else\n#define pass_t16_inverse pass_t16\n#endif\n')
    source = source[:end] + '\n' + helper + source[end:]
    calls = ('        pass_t16(x, a, norm_sj16, NULL, 1);\n'
             '        pass_t16(a, y, NULL, NULL, 1);')
    if source.count(calls) != 1:
        raise ValueError('Expected one inverse16 call pair')
    return source.replace(calls, calls.replace('pass_t16(', 'pass_t16_inverse('))


def generate():
    verify_policy()
    pieces = [PRELUDE]
    for n in (8, 16):
        for direction in 'ft':
            pieces.append(fused_pass(n, direction))
        pieces.append(fused_transform(n))
    pieces.append(register_roundtrip())
    pieces.append('''
/* Internal: n=8/16, mode=0..2 and variant follow the validated public dispatch.
   The caller supplies disjoint n*n input/output arrays and a 16-byte-aligned
   workspace of at least 2*n*n floats; this entry point does not validate them. */
int NAME(int n, int variant, int mode, const float *x, float *y,
         float *w, size_t count)
{
    if (n == 8 && variant == 1 && mode == 2) {
        registers8_2(x, y);
        return 0;
    }
    if (variant == 2) {
        if (n == 8 && mode != 2) {
            fused8(mode, x, y, w);
            return 0;
        }
        if (n == 16) {
            fused16(mode, x, y, w);
            return 0;
        }
    }
    return -1;
}
''')
    return specialize_inverse16(''.join(pieces)).encode('utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Compare generated bytes without writing.')
    args = parser.parse_args()
    expected = generate()
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_bytes() != expected:
            raise SystemExit('Generated small kernel differs; run make generate-small and review the change.')
        print('PASS: small policy, arithmetic hashes and generated bytes match.')
    else:
        OUTPUT.write_bytes(expected)
        print(f'Generated {OUTPUT.relative_to(ROOT)} ({len(expected)} bytes).')


if __name__ == '__main__':
    main()
