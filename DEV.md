# Development Notes

## Makefile

`Makefile`s are used to encapsulate the various tools in the toolchain:

```bash
make bootstrap		# install dependencies
make test		# test using different Python versions
make lint		# use a linter to check format
```

NOTE: To publish, see the [Release documentation](RELEASING.md).

# Architecture

For a general overview of Ligthstep Tracers, see [Lightstep Tracers Spec](https://github.com/lightstep/specs).

This Tracer supports two transports:

* **Protobuf/http** (preferred).
* **Thrift** (least preferred).

Three propagation formats are supported:

* Custom Lightstep format (see the Lightstep Tracers Spec mentioned above).
* B3.
* Custom Binary format (_very_ least preferred), based on protobuf.
