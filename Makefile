.EXPORT_ALL_VARIABLES:
.ONESHELL:
.PHONY: default clean test

default:
	test -f pyvenv.cfg || ./create-venv.sh

clean:
	rm -rf bin include lib pyvenv.cfg

test:
	shellcheck -e SC1091 create-venv.sh
	pyflakes compare-aspaths.py
	pycodestyle --ignore=E501 compare-aspaths.py
