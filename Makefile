.PHONY: build thrift lint docs dist inc-version publish sample-app \
	test test-util test-runtime test-opentracing \
	default

default: test

build:
	echo "Nothing to build"

lint:
	pylint -r n --disable=invalid-name,global-statement,bare-except \
		lightstep/instrument.py lightstep/constants.py lightstep/connection.py

docs:
	cd docs && make html

dist: build lint docs inc-version
	mkdir -p dist
	rm -rf dist
	python setup.py sdist      # source distribution
	python setup.py bdist_wheel

# TODO: There's inelegant dependency on Node.js here
inc-version: scripts/node_modules
	node scripts/inc_version.js

scripts/node_modules:
	cd scripts && npm update

publish: dist
	twine upload dist/*

sample-app: build
	python sample/send_spans_logs.py

test: build
	tox


# LightStep-specific: rebuilds the LightStep thrift protocol files.  Assumes
# the command is run within the LightStep development environment (i.e. the
# LIGHTSTEP_HOME environment variable is set).
thrift:
	thrift -r -gen py -out lightstep/ $(LIGHTSTEP_HOME)/go/src/crouton/crouton.thrift
	rm lightstep/crouton/ReportingService-remote
