GIT_BRANCH ?= "main"

checkout:
	cd funcpipes && git checkout $(GIT_BRANCH)
	git checkout $(GIT_BRANCH)

pull:
	cd funcpipes && git pull
	git pull

install:
	cd funcpipes && make install
	./setup.py install

uninstall:
	pip3 uninstall pysh
