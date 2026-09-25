// External libjxl/Highway adapter only. The benchmark interface is C ABI.
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <new>

#include "hwy/highway.h"
#include "lib/jxl/dct-inl.h"

namespace {
constexpr std::size_t kGuardFloats = 16;
constexpr std::uint32_t kGuard = UINT32_C(0x7f8abcde);
struct Buffer {
  float* base = nullptr;
  float* data = nullptr;
  std::size_t count = 0;
  bool allocate(std::size_t n) {
    count = n;
    if (posix_memalign(reinterpret_cast<void**>(&base), 64,
                       (n + 2 * kGuardFloats) * sizeof(float))) return false;
    data = base + kGuardFloats;
    for (std::size_t i = 0; i < kGuardFloats; ++i) {
      std::memcpy(base + i, &kGuard, sizeof(kGuard));
      std::memcpy(data + n + i, &kGuard, sizeof(kGuard));
    }
    return true;
  }
  bool intact() const {
    if (!base) return false;
    for (std::size_t i = 0; i < kGuardFloats; ++i) {
      std::uint32_t a, b;
      std::memcpy(&a, base + i, sizeof(a));
      std::memcpy(&b, data + count + i, sizeof(b));
      if (a != kGuard || b != kGuard) return false;
    }
    return true;
  }
  ~Buffer() { std::free(base); }
};
struct Plan {
  int n, batch;
  std::size_t area, total;
  Buffer input, output, coefficients, scratch;
};

template <std::size_t N>
void transform(Plan* p, int mode) {
  using namespace jxl::HWY_NAMESPACE;
  float* coefficients = p->coefficients.data;
  float* scratch = p->scratch.data;
  for (int tile = 0; tile < p->batch; ++tile) {
    const float* input = p->input.data + tile * p->area;
    float* output = p->output.data + tile * p->area;
    if (mode == 1) {
      Transpose<N, N>::Run(DCTFrom(input, N), DCTTo(coefficients, N));
      for (std::size_t k = 0; k < N * N; ++k) coefficients[k] *= 1.0f / N;
      ComputeScaledIDCT<N, N>()(coefficients, DCTTo(output, N), scratch);
    } else {
      ComputeScaledDCT<N, N>()(DCTFrom(input, N), coefficients, scratch);
      if (mode == 0) {
        Transpose<N, N>::Run(DCTFrom(coefficients, N), DCTTo(output, N));
        for (std::size_t k = 0; k < N * N; ++k) output[k] *= N;
      } else {
        ComputeScaledIDCT<N, N>()(coefficients, DCTTo(output, N), scratch);
      }
    }
  }
}
}  // namespace

extern "C" {
void jx_free(void* opaque) { delete static_cast<Plan*>(opaque); }
void* jx_create(int route, int n, int batch) {
  if (route != 9 || n < 8 || n > 256 || (n & (n - 1)) ||
      (batch != 1 && batch != 4 && batch != 16)) return nullptr;
  auto* p = new (std::nothrow) Plan;
  if (!p) return nullptr;
  p->n = n; p->batch = batch;
  p->area = static_cast<std::size_t>(n) * n;
  p->total = p->area * batch;
  // Upstream rectangular tests use five areas. A guard follows each allocation.
  if (!p->input.allocate(p->total) || !p->output.allocate(p->total) ||
      !p->coefficients.allocate(p->area) || !p->scratch.allocate(5 * p->area)) {
    delete p; return nullptr;
  }
  return p;
}
const char* jx_name(int route) { return route == 9 ? "libjxl_highway" : "invalid"; }
int jx_run(void* opaque, int mode, const float* input, float* output) {
  auto* p = static_cast<Plan*>(opaque);
  if (!p || !input || mode < 0 || mode > 2) return -1;
  std::memcpy(p->input.data, input, p->total * sizeof(float));
  switch (p->n) {
    case 8: transform<8>(p, mode); break;
    case 16: transform<16>(p, mode); break;
    case 32: transform<32>(p, mode); break;
    case 64: transform<64>(p, mode); break;
    case 128: transform<128>(p, mode); break;
    case 256: transform<256>(p, mode); break;
    default: return -2;
  }
  if (output) std::memcpy(output, p->output.data, p->total * sizeof(float));
  return 0;
}
float jx_value(const void* opaque, std::size_t k) {
  const auto* p = static_cast<const Plan*>(opaque);
  return p->output.data[k % p->total];
}
int jx_check(const void* opaque) {
  const auto* p = static_cast<const Plan*>(opaque);
  return p && p->input.intact() && p->output.intact() &&
         p->coefficients.intact() && p->scratch.intact();
}
#define STRINGIFY_I(x) #x
#define STRINGIFY(x) STRINGIFY_I(x)
const char* jx_target() { return STRINGIFY(HWY_NAMESPACE); }
void jx_print(void* opaque) {
  const auto* p = static_cast<const Plan*>(opaque);
  const std::size_t lanes = hwy::HWY_NAMESPACE::Lanes(HWY_FULL(float)());
  std::fprintf(stderr, "TARGET,libjxl,%s,%zu,N=%d,B=%d,scratch_bytes=%zu\n",
               jx_target(), lanes, p->n, p->batch, 5 * p->area * sizeof(float));
}
}
