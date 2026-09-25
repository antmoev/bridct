PYTHON ?= python3
CORE ?= ..
LIBRARY ?= $(CORE)/build/libbridct.a
BUILD ?= build
.PHONY: all check check-full check-hardening clean
all:
	$(PYTHON) build.py --core $(CORE) --library $(LIBRARY) --output $(BUILD)
check: all
	$(PYTHON) runtime_info.py --module-dir $(BUILD)
	$(PYTHON) test_api.py --module-dir $(BUILD)
check-full: all
	$(PYTHON) runtime_info.py --module-dir $(BUILD)
	$(PYTHON) test_api.py --module-dir $(BUILD) --all-shapes
check-hardening: all
	$(PYTHON) build_test_allocator.py --build-dir $(BUILD)
	$(PYTHON) test_hardening.py --module-dir $(BUILD)
clean:
	rm -rf $(BUILD)
