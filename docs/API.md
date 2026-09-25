# API and numerical contract

Include `bridct.h` and link `libbridct.a` (and the system math library), or the platform's shared library. The C11 implementation uses native ARM64 NEON, selected AVX2/FMA objects on capable x86 CPUs, or the vendored SIMDe compatibility backend. See [platform scope](PLATFORMS.md) for validated targets. No Python, FFTW or Apple Accelerate call is made by the library.

## Transform and layout

For an `h` by `w` row-major float array, with orthonormal DCT-II matrices `Q_h` and `Q_w`:

- `BRIDCT_FORWARD`: `Q_h X Q_w^T`.
- `BRIDCT_INVERSE`: `Q_h^T X Q_w`.
- `BRIDCT_ROUNDTRIP`: the normalized identity composition of the two cores. It is not a Poisson solver or a spectral filter.

The normalization is `Q_n[k,j] = sqrt((k == 0 ? 1 : 2)/n) cos(pi*k*(j+1/2)/n)`. Forward and inverse outputs have the same row-major orientation as the mathematical arrays. There is no approximate matrix, coefficient truncation or implicit resizing.

Axes must be powers of two from 8 to 1024. `bridct_supported(h,w)` reports this without allocating. A length such as 26 is rejected. An unsupported input is never padded to a different DCT.

Input and output must each hold `h*w` valid floats and be disjoint. Partial overlap is rejected. In-place transforms, arbitrary leading dimensions and batched/interleaved input are not exposed by this API. Pointer validity and actual allocated lengths remain caller responsibilities. Ordinary float alignment suffices for input/output; no 16-byte input alignment is required.

## Reusable plans

`bridct_plan_create(h,w)` returns an owning plan or `NULL` for unsupported dimensions/allocation failure. It allocates scratch once and constructs scale tables for the extension. Reuse it across arrays of the same shape. `bridct_plan_apply(plan,mode,input,output)` performs no allocation. Destroy with `bridct_plan_destroy(plan)`; destroying `NULL` is harmless.

A plan contains mutable scratch and cannot be used concurrently. Use a separate plan per concurrent call/thread. The library has no mutable process-global plan cache. `bridct_plan_route(plan)` returns the static string `paper8-square` or `blocked-extension`, or `NULL` for a null plan; do not free this string. These are historical shape categories, not CPU/ISA indicators. An AVX2-enabled 256×256 plan still reports `paper8-square`; consult [platform scope](PLATFORMS.md) for backend choices.

## Caller-managed square workspace

For squares 8–256, `bridct_workspace_floats(n)` returns the required count of **floats**, not bytes, or zero for unsupported sizes. Allocate at least that many floats with 16-byte alignment and pass their count to `bridct_apply`. Input, output and the used workspace region must be pairwise disjoint. Use separate workspace for concurrent calls.

Workspace bounds are conservative, not minimum-memory claims. Query the required capacity. Plans own their workspace and can select a different backend, notably at 256×256; see [platform scope](PLATFORMS.md).

Use a matched allocation/deallocation pair for caller-owned aligned storage: C11 `aligned_alloc`/`free` on supported Unix runtimes, or `_aligned_malloc`/`_aligned_free` on Windows. The plan API handles its own platform-specific allocation internally.

## Return codes

| Code | Meaning |
|---|---|
| `BRIDCT_OK` / 0 | Transform completed |
| `BRIDCT_INVALID_ARGUMENT` / -1 | Null argument, unsupported size or invalid mode |
| `BRIDCT_WORKSPACE_TOO_SMALL` / -2 | Caller-managed square scratch is too short |
| `BRIDCT_BAD_ALIGNMENT` / -3 | Caller-managed square scratch is not 16-byte aligned |
| `BRIDCT_OVERLAPPING_BUFFERS` / -4 | Input/output or used scratch overlap |

An error return does not make an invalid pointer safe to dereference elsewhere. NaN, infinity and finite-input overflow are not argument-status checks: numerical validity must be assessed using the application’s input-range contract.

## Precision

Storage and SIMD arithmetic use float32; plan scales are evaluated in double before conversion. FMA settings are selected policies, not `fast-math`. Reassociation, alternative compilers or unsafe floating-point flags can change answers. Do not enable `-ffast-math` for a build intended to reproduce these checks.

The tested normwise threshold is `2e-5` relative to the actual input norm. It is not a mathematical error bound. Underflow, intermediate overflow and relative error of weak AC components remain limitations even when an identity check succeeds. See the dataset card and `LIMITATIONS.md`.

For the current 8×8 and 16×16 routes, `bridct_workspace_floats(n)` returns `2*n*n`: 512 and 2,048 bytes respectively. Older callers that reserved more space remain valid. Always use the query rather than hard-coding this formula. This is reserved scratch capacity, not a measurement of cache or DRAM traffic.
