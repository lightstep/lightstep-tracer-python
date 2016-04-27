# LightStep OpenTracing Bindings

[![Circle CI](https://circleci.com/gh/lightstep/lightstep-tracer-python.svg?style=shield)](https://circleci.com/gh/lightstep/lightstep-tracer-python)

This library is the LightStep binding for [OpenTracing](http://opentracing.io/). See the [OpenTracing Python API](https://github.com/opentracing/opentracing-python) for additional detail.

* [Installation](#installation)
* [Getting Started](#getting-started)

## Installation

```bash
apt-get install python-dev
pip install lightstep
```

## Getting Started

Please see the [example programs](examples/) for examples of how to use this library. In particular:

* [Trivial Example](examples/trivial/main.py) shows how to use the library on a single host.
* [Context in Headers](examples/http/context_in_headers.py) shows how to pass a `TraceContext` through `HTTP` headers.

Or if your python code is already instrumented for OpenTracing, you can simply switch to LightStep's implementation with:

```python
import opentracing
import lightstep.tracer

opentracing.tracer = lightstep.tracer.init_tracer(
    group_name='your_process_type',
    access_token='{your_access_token}')
```

## License

[The MIT License](LICENSE).
