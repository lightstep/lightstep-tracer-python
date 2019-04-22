<a name="4.0.4"></a>
## [4.0.2](https://github.com/lightstep/lightstep-tracer-python/compare/4.0.2...4.0.3)
* Add LightStep-Access-Token header to outgoing requests.

<a name="4.0.3"></a>
## [4.0.2](https://github.com/lightstep/lightstep-tracer-python/compare/4.0.2...4.0.3)
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
