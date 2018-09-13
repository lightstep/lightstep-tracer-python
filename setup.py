from setuptools import setup, find_packages

setup(
    name='lightstep',
    version='4.0.0',
    description='LightStep Python OpenTracing Implementation',
    long_description='',
    author='LightStep',
    license='',
    install_requires=['thrift==0.10.0',
                      'jsonpickle',
                      'six',
                      'basictracer>=3.0,<3.1',
                      'googleapis-common-protos==1.5.3',
                      'requests>=2.19,<3.0'],
    tests_require=['pytest',
                   'sphinx',
                   'sphinx-epytext'],
    classifiers=[
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 2',
    ],

    keywords=[ 'opentracing', 'lightstep', 'traceguide', 'tracing', 'microservices', 'distributed' ],
    packages=find_packages(exclude=['docs*', 'tests*', 'sample*']),
)
