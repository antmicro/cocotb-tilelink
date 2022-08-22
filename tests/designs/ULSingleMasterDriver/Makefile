TOPLEVEL_LANG ?= verilog

ifneq ($(TOPLEVEL_LANG),verilog)

all:
	@echo "Skipping test due to TOPLEVEL_LANG=$(TOPLEVEL_LANG) not being verilog"
clean::

else

TOPLEVEL := top

PWD=$(shell pwd)

COCOTB?=$(PWD)/../../..

VERILOG_SOURCES += $(COCOTB)/tests/designs/ULSingleMasterDriver/TLUL_ram.sv
VERILOG_SOURCES += $(COCOTB)/tests/designs/ULSingleMasterDriver/TLUL_default.sv
VERILOG_SOURCES += $(COCOTB)/tests/designs/ULSingleMasterDriver/top.sv

include $(shell cocotb-config --makefiles)/Makefile.sim

endif
