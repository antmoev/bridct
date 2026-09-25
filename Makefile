UNAME_S := $(shell uname -s)
UNAME_M := $(shell uname -m)
ifeq ($(origin CC),default)
CC := $(if $(wildcard /Library/Developer/CommandLineTools/usr/bin/clang),/Library/Developer/CommandLineTools/usr/bin/clang,cc)
endif
ifeq ($(origin AR),default)
AR := $(if $(wildcard /Library/Developer/CommandLineTools/usr/bin/ar),/Library/Developer/CommandLineTools/usr/bin/ar,ar)
endif
ARCH ?= $(UNAME_M)
BACKEND ?= auto
RUNTIME_SIMD ?= auto
ifneq ($(origin OOURA16_ALL_RUNTIME),undefined)
$(error OOURA16_ALL_RUNTIME was removed in dev.6; Ooura is a separate benchmark control)
endif
BUILD ?= build
RUNNER ?=
PYTHON ?= python3
CFLAGS ?= -O3
CC_VERSION := $(shell $(CC) --version 2>/dev/null)
ifneq ($(findstring clang,$(CC_VERSION)),)
NOVEC = -fno-vectorize -fno-slp-vectorize
else
NOVEC = -fno-tree-vectorize -fno-tree-slp-vectorize
endif
ifneq ($(filter $(BACKEND),auto neon simde portable),$(BACKEND))
$(error BACKEND must be auto, neon, simde or portable)
endif
ifeq ($(BACKEND),neon)
ifeq ($(filter arm64 aarch64,$(ARCH)),)
$(error BACKEND=neon requires ARM64)
endif
endif
ifneq ($(filter $(BACKEND),simde portable),)
BACKEND_FLAGS = -DBRIDCT_USE_SIMDE
endif
ifeq ($(BACKEND),portable)
BACKEND_FLAGS += -DSIMDE_NO_NATIVE
endif
ifneq ($(filter $(RUNTIME_SIMD),auto off),$(RUNTIME_SIMD))
$(error RUNTIME_SIMD must be auto or off)
endif
X86_64 := $(filter x86_64 amd64 AMD64,$(ARCH))
ifneq ($(X86_64),)
BASELINE_ISA = -march=x86-64 -mno-avx -mno-fma
ifneq ($(BACKEND),portable)
ifeq ($(RUNTIME_SIMD),auto)
RUNTIME_FLAGS = -DBRIDCT_COMPILED_AVX2=1
AVX2_OBJECTS = $(addprefix $(BUILD)/,small_avx2.o rect_avx2_f0.o rect_avx2_f1.o)
endif
endif
endif
BASE = -std=c11 -pedantic-errors -Wall -Wextra -Wno-unused-function -Wno-unused-variable -Wno-unused-parameter $(NOVEC) -fvisibility=hidden -fPIC -Iinclude -Isrc -isystem third_party/simde $(BACKEND_FLAGS) $(RUNTIME_FLAGS) $(CFLAGS) $(EXTRA_FLAGS) $(BASELINE_ISA)
ifeq ($(UNAME_S),Darwin)
SDKROOT ?= $(firstword $(wildcard /Library/Developer/CommandLineTools/SDKs/MacOSX.sdk))
BASE += -arch $(ARCH) $(if $(SDKROOT),-isysroot $(SDKROOT))
SHARED := $(BUILD)/libbridct.dylib
SHARED_FLAGS = -dynamiclib -Wl,-install_name,@rpath/libbridct.dylib
SHARED_LINK = $(SHARED) -Wl,-rpath,@loader_path
else ifneq ($(filter MINGW% MSYS% CYGWIN%,$(UNAME_S)),)
EXE := .exe
SHARED := $(BUILD)/bridct.dll
SHARED_FLAGS = -shared -Wl,--out-implib,$(BUILD)/libbridct.dll.a
SHARED_LINK = $(BUILD)/libbridct.dll.a
else
SHARED := $(BUILD)/libbridct.so
SHARED_FLAGS = -shared -Wl,-soname,libbridct.so
SHARED_LINK = $(SHARED) -Wl,-rpath,'$$ORIGIN'
endif
OBJECTS := $(addprefix $(BUILD)/,small.o large_f0.o large_f1.o rect_f0.o rect_f1.o api.o plan.o) $(AVX2_OBJECTS)
.PHONY: all check check-shared check-small check-runtime check-generated generate-small generate-avx2 check-small16 bench sanitize clean dataset verify-source FORCE
all: $(BUILD)/libbridct.a $(SHARED) $(BUILD)/roundtrip$(EXE) $(BUILD)/test_api$(EXE) $(BUILD)/test_runner$(EXE)
$(BUILD):
	mkdir -p $@
CONFIG_VALUE = $(CC) $(BASE) $(SHARED_FLAGS) $(CC_VERSION)
ifneq ($(shell cat $(BUILD)/config 2>/dev/null),$(CONFIG_VALUE))
.PHONY: $(OBJECTS)
endif
FORCE:
$(BUILD)/config: FORCE | $(BUILD)
	@printf '%s\n' '$(CONFIG_VALUE)' > $@.tmp
	@cmp -s $@.tmp $@ || { cp $@.tmp $@; rm -f $(OBJECTS) $(BUILD)/libbridct.a $(SHARED) $(BUILD)/libbridct.dll.a $(BUILD)/roundtrip$(EXE) $(BUILD)/test_api$(EXE) $(BUILD)/test_runner$(EXE) $(BUILD)/bench$(EXE) $(BUILD)/test_api_shared$(EXE) $(BUILD)/test_runner_shared$(EXE) $(BUILD)/test_small_optimized$(EXE) $(BUILD)/test_runtime$(EXE) $(BUILD)/test_small16$(EXE) $(BUILD)/plan_testing.o; }
	@rm $@.tmp
$(OBJECTS) $(BUILD)/plan_testing.o: $(BUILD)/config

SIMD_HEADERS := src/bridct_simd.h $(wildcard third_party/simde/simde/*.h third_party/simde/simde/arm/neon/*.h third_party/simde/simde/x86/*.h)
$(filter-out $(BUILD)/api.o $(BUILD)/plan.o,$(OBJECTS)): $(SIMD_HEADERS)

$(BUILD)/small.o: src/generated/small_optimized.c src/generated/tables.inc src/generated/sj_body.inc | $(BUILD)
	$(CC) $(BASE) -ffp-contract=fast -DNAME=bridct_small_optimized_f1 -c $< -o $@
$(BUILD)/large_f0.o: src/generated/large.c src/generated/blocked_kernels.inc | $(BUILD)
	$(CC) $(BASE) -ffp-contract=off -DNAME=bridct_large_f0 -c $< -o $@
$(BUILD)/large_f1.o: src/generated/large.c src/generated/blocked_kernels.inc | $(BUILD)
	$(CC) $(BASE) -ffp-contract=fast -DNAME=bridct_large_f1 -c $< -o $@
$(BUILD)/rect_f0.o: src/generated/rect.c src/generated/rect_generated.inc src/generated/rect_generated_meta.h | $(BUILD)
	$(CC) $(BASE) -ffp-contract=off -DNAME=bridct_rect_f0 -c $< -o $@
$(BUILD)/rect_f1.o: src/generated/rect.c src/generated/rect_generated.inc src/generated/rect_generated_meta.h | $(BUILD)
	$(CC) $(BASE) -ffp-contract=fast -DNAME=bridct_rect_f1 -c $< -o $@
$(BUILD)/small_avx2.o: src/generated/small_avx2.c src/generated/tables.inc src/generated/sj_body.inc src/bridct_avx2.h | $(BUILD)
	$(CC) $(BASE) -mavx2 -mfma -ffp-contract=fast -DNAME=bridct_small_avx2_f1 -c $< -o $@
$(BUILD)/rect_avx2_f0.o: src/generated/rect_avx2.c src/generated/rect_avx2_generated.inc src/bridct_avx2.h src/bridct_avx2_workspace.h | $(BUILD)
	$(CC) $(BASE) -mavx2 -mfma -ffp-contract=off -DNAME=bridct_rect_avx2_f0 -c $< -o $@
$(BUILD)/rect_avx2_f1.o: src/generated/rect_avx2.c src/generated/rect_avx2_generated.inc src/bridct_avx2.h src/bridct_avx2_workspace.h | $(BUILD)
	$(CC) $(BASE) -mavx2 -mfma -ffp-contract=fast -DNAME=bridct_rect_avx2_f1 -c $< -o $@
$(BUILD)/api.o: src/bridct.c src/bridct_runtime.h include/bridct.h | $(BUILD)
	$(CC) $(BASE) -DBRIDCT_BUILD -ffp-contract=off -c $< -o $@
$(BUILD)/plan.o: src/plan.c src/bridct_runtime.h src/bridct_avx2_workspace.h src/bridct_alloc.h include/bridct.h src/generated/rect_generated_meta.h src/generated/rect_policy.inc | $(BUILD)
	$(CC) $(BASE) -DBRIDCT_BUILD -ffp-contract=off -c $< -o $@
$(BUILD)/plan_testing.o: src/plan.c src/bridct_runtime.h src/bridct_avx2_workspace.h src/bridct_alloc.h include/bridct.h src/generated/rect_generated_meta.h src/generated/rect_policy.inc | $(BUILD)
	$(CC) $(BASE) -DBRIDCT_TESTING -DBRIDCT_BUILD -ffp-contract=off -c $< -o $@
$(BUILD)/test_runtime$(EXE): tests/test_runtime.c src/bridct_runtime.h src/bridct_avx2_workspace.h $(filter-out $(BUILD)/plan.o,$(OBJECTS)) $(BUILD)/plan_testing.o
	$(CC) $(BASE) -DBRIDCT_TESTING $< $(filter-out $(BUILD)/plan.o,$(OBJECTS)) $(BUILD)/plan_testing.o -lm -o $@
$(BUILD)/libbridct.a: $(OBJECTS)
	$(AR) rcs $@ $^
$(SHARED): $(OBJECTS)
	$(CC) $(BASE) $(SHARED_FLAGS) $^ -lm -o $@
$(BUILD)/roundtrip$(EXE): examples/roundtrip.c $(BUILD)/libbridct.a
	$(CC) $(BASE) $< $(BUILD)/libbridct.a -lm -o $@
$(BUILD)/test_api$(EXE): tests/test_api.c src/bridct_alloc.h $(BUILD)/libbridct.a
	$(CC) $(BASE) $< $(BUILD)/libbridct.a -lm -pthread -o $@
$(BUILD)/test_runner$(EXE): tests/test_runner.c $(BUILD)/libbridct.a
	$(CC) $(BASE) $< $(BUILD)/libbridct.a -lm -o $@
$(BUILD)/test_small_optimized$(EXE): tests/test_small_optimized.c $(BUILD)/libbridct.a
	$(CC) $(BASE) $< $(BUILD)/libbridct.a -lm -o $@
$(BUILD)/test_api_shared$(EXE): tests/test_api.c src/bridct_alloc.h $(SHARED)
	$(CC) $(BASE) $< $(SHARED_LINK) -lm -pthread -o $@
$(BUILD)/test_runner_shared$(EXE): tests/test_runner.c $(SHARED)
	$(CC) $(BASE) $< $(SHARED_LINK) -lm -o $@
bench: $(BUILD)/bench$(EXE)
$(BUILD)/bench$(EXE): bench/bench.c $(BUILD)/libbridct.a
	$(CC) $(BASE) $< $(BUILD)/libbridct.a -lm -o $@
check: all check-shared check-small check-runtime check-small16
	$(RUNNER) $(BUILD)/test_api$(EXE)
	$(RUNNER) $(BUILD)/roundtrip$(EXE) 16 32
check-shared: $(BUILD)/test_api_shared$(EXE) $(BUILD)/test_runner_shared$(EXE)
	$(RUNNER) $(BUILD)/test_api_shared$(EXE)
check-small: $(BUILD)/test_small_optimized$(EXE)
	$(RUNNER) $(BUILD)/test_small_optimized$(EXE)
check-small16: $(BUILD)/test_small16$(EXE)
	$(RUNNER) $(BUILD)/test_small16$(EXE)
$(BUILD)/test_small16$(EXE): tests/test_small16.c src/bridct_runtime.h $(BUILD)/libbridct.a
	$(CC) $(BASE) $< $(BUILD)/libbridct.a -lm -o $@
check-runtime: $(BUILD)/test_runtime$(EXE)
	$(RUNNER) $(BUILD)/test_runtime$(EXE)
generate-avx2:
	$(PYTHON) tools/generate_avx2.py
generate-small:
	$(PYTHON) tools/generate_small.py
check-generated:
	$(PYTHON) tools/generate_small.py --check
	$(PYTHON) tools/generate_avx2.py --check
sanitize:
	$(MAKE) BUILD=build-sanitize CFLAGS='-O1 -g' EXTRA_FLAGS='-fsanitize=address,undefined -fno-omit-frame-pointer' check
dataset:
	$(PYTHON) dataset/prepare.py
	$(PYTHON) dataset/verify.py
verify-source:
	$(PYTHON) tools/verify_source.py
clean:
	rm -rf build build-sanitize
