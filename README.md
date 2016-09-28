# LightStep OpenTracing Bindings

[![PyPI](https://img.shields.io/pypi/v/lightstep.svg?maxAge=2592000)]() [![Circle CI](https://circleci.com/gh/lightstep/lightstep-tracer-python.svg?style=shield)](https://circleci.com/gh/lightstep/lightstep-tracer-python) [![MIT license](http://img.shields.io/badge/license-MIT-blue.svg)](http://opensource.org/licenses/MIT)

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

if __name__ == "__main__":
  opentracing.tracer = lightstep.tracer.init_tracer(
    group_name='your_process_type',
    access_token='{your_access_token}')

  with opentracing.tracer.start_span('TestSpan') as span:
    span.log_event('test message', payload={'life': 42})

  opentracing.tracer.flush()
```

