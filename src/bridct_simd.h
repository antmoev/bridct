#ifndef BRIDCT_SIMD_H
#define BRIDCT_SIMD_H

#if !defined(BRIDCT_USE_SIMDE) && defined(__aarch64__)
#include <arm_neon.h>
#else
#define SIMDE_ENABLE_NATIVE_ALIASES
#include <simde/arm/neon/add.h>
#include <simde/arm/neon/sub.h>
#include <simde/arm/neon/mul.h>
#include <simde/arm/neon/mul_n.h>
#include <simde/arm/neon/neg.h>
#include <simde/arm/neon/dup_n.h>
#include <simde/arm/neon/ld1.h>
#include <simde/arm/neon/st1.h>
#include <simde/arm/neon/ld4.h>
#include <simde/arm/neon/st4.h>
#include <simde/arm/neon/trn.h>
#include <simde/arm/neon/combine.h>
#include <simde/arm/neon/get_low.h>
#include <simde/arm/neon/get_high.h>
#endif

#endif
