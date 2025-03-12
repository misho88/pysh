PYTHON_SITE=$(shell python -c 'import sysconfig; print(sysconfig.get_path("purelib"))')
MODULE_ROOT=pysh
MODULE_FILES=$(wildcard $(MODULE_ROOT)/*.py)


GIT_BRANCH ?= "main"

checkout:
	cd funcpipes && git checkout $(GIT_BRANCH)
	git checkout $(GIT_BRANCH)

pull:
	cd funcpipes && git pull
	git pull

install:
	cd funcpipes && make install
	install -d $(PYTHON_SITE)/$(MODULE_ROOT)
	install $(MODULE_FILES) $(PYTHON_SITE)/$(MODULE_ROOT)

uninstall:
	cd $(PYTHON_SITE) && rm -f $(MODULE_FILES)
	cd $(PYTHON_SITE) && rmdir $(MODULE_ROOT)
