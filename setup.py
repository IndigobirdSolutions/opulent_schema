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
        "voluptuous>=0.9.3",
    ],
    extras_require={
        'schemalchemy': [
            'Delorean>=0.5.0',
            'sqlalchemy',
        ],    
    },
)
