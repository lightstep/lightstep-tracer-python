# Releasing

Once all the changes for a release have been merged to master, ensure the following:

- [ ] version has been updated in `VERSION`, `lightstep/version.py` and `setup.py` 
- [ ] tests are passing
- [ ] user facing documentation has been updated

# Publishing

Publishing to [pypi](https://pypi.org/project/lightstep/) is automated via GitHub actions. Once a tag is pushed to the repo, a new GitHub Release is created and package is published  via the actions defined here: https://github.com/lightstep/lightstep-tracer-python/blob/master/.github/workflows/release.yml

```
$ git clone git@github.com:lightstep/lightstep-tracer-python && cd lightstep-tracer-python
# ensure the version matches the version beind released
$ cat VERSION
4.4.3
$ cat lightstep/version.py
LIGHTSTEP_PYTHON_TRACER_VERSION="4.4.3"
$ cat setup.py | grep version
    version='4.4.3',
$ git tag v4.4.3 && git push origin v4.4.3
```
