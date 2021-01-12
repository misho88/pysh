pull:
	cd funcpipes && git pull
	git pull

install:
	cd funcpipes && make install
	./setup.py install
