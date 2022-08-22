export PYTHONWARNINGS = error,ignore::DeprecationWarning:distutils,ignore::DeprecationWarning:site

regression_tests :=  $(shell ls test_tl/)

.PHONY: $(regression_tests)

SIM?=verilator

all: $(regression_tests)

$(regression_tests):
	cd test_tl/$@ && $(MAKE) SIM=$(SIM)



clean:
	$(foreach TEST, $(regression_tests), $(MAKE) -C test_tl/$(TEST) clean;)

regression:
	$(foreach TEST, $(regression_tests), $(MAKE) -C test_tl/$(TEST) regression;)
