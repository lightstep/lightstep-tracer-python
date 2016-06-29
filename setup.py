from setuptools import setup, find_packages

setup(
    name='lightstep',
    version='2.0.8',
    description='LightStep Python OpenTracing Implementation',
    long_description='',
    author='LightStep',
    license='',
    install_requires=['thrift==0.9.2',
                      'opentracing==1.0rc3',
                      'jsonpickle',
                      'basictracer==1.0rc1'],
    tests_require=['sphinx',
                   'sphinx-epytext'],

    classifiers=[
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 2',
        # 'Programming Language :: Python :: 3',
    ],

    keywords=[ 'opentracing', 'lightstep', 'traceguide', 'tracing', 'microservices', 'distributed' ],
    packages=find_packages(exclude=['docs*', 'tests*', 'sample*']),
)
