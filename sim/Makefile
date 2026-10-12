# sim/Makefile - every simulation entry point. See CLAUDE.md "Make targets".
# Works from any directory (make -C sim ...), in the container and on the host.
#
# ---- Project settings: edit these --------------------------------------------
# Directed testbench top names; each is built from rtl.f + directed.f
DIRECTED_TOPS ?=
# UVM top module and test names; regress runs every test with every seed
UVM_TOP   ?=
UVM_TESTS ?=
SEEDS     ?= 1 2 3
# Image tests (scripts/run_images.py): testbench top, built from rtl.f + directed.f;
# frames per single-image test; output bit depth (empty = same as input);
# allowed |rtl - golden| per pixel (0 = bit-exact; must match docs/spec.md)
IMAGE_TOP       ?=
IMAGE_FRAMES    ?= 1
IMAGE_OUT_BITS  ?=
IMAGE_TOLERANCE ?= 0
# Extra xvhdl options, e.g. --2008
VHDL_OPTS ?=
# ------------------------------------------------------------------------------

SIM    := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
ROOT   := $(abspath $(SIM)/..)
BUILD  := $(ROOT)/build
RUN    := $(SIM)/run_xsim.sh
PYTHON ?= python3
SEED   ?= 1
export ROOT BUILD VHDL_OPTS IMAGE_FRAMES IMAGE_OUT_BITS IMAGE_TOLERANCE

.PHONY: help directed uvm uvm-all images report regress clean

help:
	@echo "make -C sim directed                  directed testbenches: $(or $(DIRECTED_TOPS),<none set>)"
	@echo "make -C sim uvm TEST=<t> [SEED=<n>]   one UVM test"
	@echo "make -C sim uvm-all                   all UVM tests x seeds ($(SEEDS))"
	@echo "make -C sim images                    image tests -> build/images/"
	@echo "make -C sim report                    build/report/index.html"
	@echo "make -C sim regress                   everything + summary table (non-zero exit on failure)"
	@echo "make -C sim clean                     remove build/"
	@echo "Options: WAVES=1 (save .wdb)  SIM_TIMEOUT=<s>  VHDL_OPTS=--2008"

directed:
ifeq ($(strip $(DIRECTED_TOPS)),)
	@$(RUN) skip directed "DIRECTED_TOPS is empty in sim/Makefile"
else
	@fail=0; for t in $(DIRECTED_TOPS); do \
	  { $(RUN) build directed_$$t $$t rtl.f directed.f && $(RUN) run directed_$$t $$t; } || fail=1; \
	done; exit $$fail
endif

uvm:
	@[ -n "$(UVM_TOP)" ] || { echo "sim: UVM_TOP is empty in sim/Makefile"; exit 1; }
	@[ -n "$(TEST)" ]    || { echo "usage: make -C sim uvm TEST=<test> [SEED=<n>]"; exit 1; }
	@UVM=1 $(RUN) build uvm $(UVM_TOP) rtl.f uvm.f && \
	  $(RUN) run uvm $(TEST)_seed$(SEED) -testplusarg UVM_TESTNAME=$(TEST) -sv_seed $(SEED)

uvm-all:
ifeq ($(strip $(UVM_TOP)$(UVM_TESTS)),)
	@$(RUN) skip uvm "UVM_TOP/UVM_TESTS empty in sim/Makefile"
else
	@UVM=1 $(RUN) build uvm $(UVM_TOP) rtl.f uvm.f || exit 1; \
	fail=0; for t in $(UVM_TESTS); do for s in $(SEEDS); do \
	  $(RUN) run uvm $${t}_seed$$s -testplusarg UVM_TESTNAME=$$t -sv_seed $$s || fail=1; \
	done; done; exit $$fail
endif

images:
ifeq ($(strip $(IMAGE_TOP)),)
	@$(RUN) skip images "IMAGE_TOP is empty in sim/Makefile"
else
	@[ -f "$(ROOT)/scripts/run_images.py" ] || $(RUN) fail images "scripts/run_images.py not found"
	@$(RUN) build images $(IMAGE_TOP) rtl.f directed.f && \
	  $(PYTHON) "$(ROOT)/scripts/run_images.py"
endif

report:
	@$(PYTHON) "$(ROOT)/scripts/make_report.py" && echo "Report: build/report/index.html"

regress:
	@mkdir -p "$(BUILD)" && rm -f "$(BUILD)/results.txt"
	@-$(MAKE) --no-print-directory directed
	@-$(MAKE) --no-print-directory uvm-all
	@-$(MAKE) --no-print-directory images
	@$(RUN) summary; rc=$$?; \
	  $(PYTHON) "$(ROOT)/scripts/make_report.py" && echo "Report: build/report/index.html"; \
	  exit $$rc

clean:
	rm -rf "$(BUILD)"
