.PHONY: build thrift lint docs dist inc-version publish sample-app \
	test test-util test-runtime test-opentracing


build: thrift lint

thrift:
	thrift -r -gen py -out lightstep/ $(LIGHTSTEP_HOME)/go/src/crouton/crouton.thrift
	rm lightstep/crouton/ReportingService-remote

lint:
	pylint -r n --disable=invalid-name,global-statement,bare-except \
		lightstep/instrument.py lightstep/constants.py lightstep/connection.py

docs:
	cd docs && make html

dist: build docs inc-version
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

test: build test-util test-runtime test-opentracing
	tox

test-util:
	python tests/util_test.py

test-runtme:
	python tests/runtime_test.py

test-opentracing:
	python tests/opentracing_compatibility_test.py
