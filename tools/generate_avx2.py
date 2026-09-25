#!/usr/bin/env python3
"""Reproduce the measured eight-lane kernels without changing their graphs."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = Path(__file__).resolve().parent / "avx2"
SUBSTITUTIONS = {
    '"bridct_simd.h"': '"bridct_avx2.h"',
    "float32x4_t": "W8",
    "vaddq_f32": "w8_add",
    "vsubq_f32": "w8_sub",
    "vmulq_f32": "w8_mul",
    "vmulq_n_f32": "w8_mul_scalar",
    "vnegq_f32": "w8_neg",
    "vdupq_n_f32": "w8_splat",
    "vld1q_f32": "w8_load",
    "vst1q_f32": "w8_store",
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def replace_once(text, before, after):
    if text.count(before) != 1:
        raise ValueError(f"Expected one occurrence of {before!r}")
    return text.replace(before, after)


def generate(source_root):
    origin = json.loads((TEMPLATES / "ORIGIN.json").read_text())
    for name, expected in origin["templates_sha256"].items():
        if sha((TEMPLATES / name).read_bytes()) != expected:
            raise ValueError(f"Frozen template changed: {name}")
    for name, expected in origin["graph_dependencies_sha256"].items():
        if sha((source_root / name).read_bytes()) != expected:
            raise ValueError(f"Frozen graph dependency changed: {name}")
    source = (source_root / "src/generated/rect_generated.inc").read_text()
    wide = source
    for before, after in SUBSTITUTIONS.items():
        wide = wide.replace(before, after)
    reverse = wide
    for before, after in reversed(tuple(SUBSTITUTIONS.items())):
        reverse = reverse.replace(after, before)
    if reverse != source:
        raise ValueError("Primitive substitutions are not reversible")
    original_wide = wide.replace('"bridct_avx2.h"', '"wide8_ops.h"')
    if sha(original_wide.encode()) != origin["measured_rect_graph_sha256"]:
        raise ValueError("Generated graph differs from the timed wide8 graph")
    small = (TEMPLATES / "wide_small.c").read_text()
    small = replace_once(small, '"wide8_ops.h"', '"bridct_avx2.h"')
    rect = (TEMPLATES / "rect_wide.c").read_text()
    rect = replace_once(rect, '"rect_wide_generated.inc"', '"rect_avx2_generated.inc"')
    rect = replace_once(rect, '"workspace.h"', '"bridct_avx2_workspace.h"')
    output = {
        "src/generated/small_avx2.c": small.encode(),
        "src/generated/rect_avx2.c": rect.encode(),
        "src/generated/rect_avx2_generated.inc": wide.encode(),
        "src/bridct_avx2.h": (TEMPLATES / "wide8_ops.h").read_bytes(),
        "src/bridct_avx2_workspace.h": (TEMPLATES / "workspace.h").read_bytes(),
    }
    proof = {
        "schema": 1,
        "status": "SOURCE_REPRODUCED",
        "origin": origin,
        "primitive_substitutions": SUBSTITUTIONS,
        "reversed_substitutions_exact": True,
        "measured_rect_graph_exact_after_header_rename": True,
        "small_changes": {"wide8_ops.h": "bridct_avx2.h"},
        "rect_wrapper_changes": {
            "rect_wide_generated.inc": "rect_avx2_generated.inc",
            "workspace.h": "bridct_avx2_workspace.h",
        },
        "generated_sha256": {name: sha(data) for name, data in output.items()},
        "runtime_scope": {"legacy": [8], "plan": [[256, 256], [512, 512],
                         [512, 1024], [1024, 512], [1024, 1024]]},
        "fma": "small8 on; plan256 on for every mode; other plan policies unchanged",
        "validation": "Source identity only; integrated runtime must be tested separately",
    }
    output["avx2_sources.json"] = (json.dumps(proof, indent=2) + "\n").encode()
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=ROOT)
    parser.add_argument("--output-root", type=Path, default=ROOT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    output = generate(args.source_root.resolve())
    for name, data in output.items():
        path = args.output_root / name
        if args.check:
            if not path.is_file() or path.read_bytes() != data:
                raise SystemExit(f"Generated source differs: {path}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    print(f"AVX2 sources {'match' if args.check else 'generated'}: {len(output)} files")


if __name__ == "__main__":
    main()
