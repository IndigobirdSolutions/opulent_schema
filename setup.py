import sys
import os
import atexit

from setuptools import setup

version = "0.1.0"

setup(
    name='opulent_schema',
    url='https://github.com/4SmartIT/opulent_schema',
    version=version,
    license='BSD',
    platforms=['any'],
    packages=['opulent_schema'],
    install_requires=[
        "voluptuous",    
    ],
    extra_require={
        'schemalchemy': [
            'delorean',
            'sqlalchemy',
        ],    
    },
)
