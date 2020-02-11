from setuptools import setup, find_packages

setup(
    name='lightstep',
    version='4.4.3',
    description='LightStep Python OpenTracing Implementation',
    long_description='',
    author='LightStep',
    license='',
    install_requires=[
        'thrift>=0.13.0',
        'jsonpickle',
        'six',
        'basictracer>=3.0,<4',
        'googleapis-common-protos>=1.5.3,<2.0',
        'requests>=2.19,<3.0',
        'protobuf>=3.6.0,<4.0'
    ],
    tests_require=[
        'pytest',
        'sphinx',
        'sphinx-epytext',
        'ipdb'
    ],
    classifiers=[
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 2',
    ],

    keywords=[
        'opentracing',
        'lightstep',
        'traceguide',
        'tracing',
        'microservices',
        'distributed'
    ],
    packages=find_packages(exclude=['docs*', 'tests*', 'sample*']),
)
