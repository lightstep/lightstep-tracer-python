CHANGELOG.md

<a name="4.4.6"></a>
## [4.4.6](https://github.com/lightstep/lightstep-tracer-python/compare/4.4.5...4.4.6)
* Format tracebacks with cause

<a name="4.4.5"></a>
## [4.4.5](https://github.com/lightstep/lightstep-tracer-python/compare/4.4.4...4.4.5)
* Revert: Format tracebacks with cause

<a name="4.4.4"></a>
## [4.4.4](https://github.com/lightstep/lightstep-tracer-python/compare/4.4.3...4.4.4)
* Format tracebacks with cause
* Add lightstep.hostname tag

<a name="4.4.3"></a>
## [4.4.3](https://github.com/lightstep/lightstep-tracer-python/compare/4.4.1...4.4.3)
* Update version of Thrift to 0.13.0

<a name="4.4.1"></a>
## [4.4.1](https://github.com/lightstep/lightstep-tracer-python/compare/4.4.0...4.4.1)
* Truncate LSb
* Add contributing guide

<a name="4.4.0"></a>
## [4.4.0](https://github.com/lightstep/lightstep-tracer-python/compare/4.3.0...4.4.0)
* Add support for B3 headers
* Truncate trace_id for specific LightStep requirements

<a name="4.3.0"></a>
## [4.3.0](https://github.com/lightstep/lightstep-tracer-python/compare/4.2.1...4.3.0)
* Add support for B3 headers

<a name="4.2.1"></a>
## [4.2.1](https://github.com/lightstep/lightstep-tracer-python/compare/4.2.0...4.2.1)
* Properly format OpenTracing error logs
* Properly set logging timestamp for the HTTP converter

<a name="4.2.0"></a>
## [4.2.0](https://github.com/lightstep/lightstep-tracer-python/compare/4.1.1...4.2.0)
* Update version of basictracer

<a name="4.1.1"></a>
## [4.1.1](https://github.com/lightstep/lightstep-tracer-python/compare/4.1.0...4.1.1)
* Add LightStep-Access-Token header to outgoing requests.

<a name="4.1.0"></a>
## [4.1.0](https://github.com/lightstep/lightstep-tracer-python/compare/4.0.3...4.1.0)
* Support access token passing via headers

<a name="4.0.3"></a>
## [4.0.3](https://github.com/lightstep/lightstep-tracer-python/compare/4.0.2...4.0.3)
* Better handle non-success status codes in the Thrift response path.

<a name="4.0.2"></a>
## [4.0.2](https://github.com/lightstep/lightstep-tracer-python/compare/4.0.1...4.0.2)
* Declare protobuf as a dependency

<a name="4.0.1"></a>
## [4.0.1](https://github.com/lightstep/lightstep-tracer-python/compare/4.0.0...4.0.1)
* Calculate and set seconds and nanos for Span's Timestamp proto

<a name="4.0.0"></a>
## [4.0.0](https://github.com/lightstep/lightstep-tracer-python/compare/3.0.11...4.0.0)
### BREAKING CHANGES
* Integrate the OpenTracing 2.0.0 updates which implements the ScopeManager for in-process propagation (OT changelog can be found [here](https://medium.com/opentracing/announcing-python-opentracing-2-0-0-fa4e4c9395a))
