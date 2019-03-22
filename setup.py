from setuptools import setup

version = "0.1.0"

setup(
    name='opulent_schema',
    url='https://github.com/4SmartIT/opulent_schema',
    version=version,
    license='BSD',
    platforms=['any'],
    python_requires=">=3.5",
    packages=['opulent_schema'],
    install_requires=[
        "voluptuous>=0.9.3",
    ],
    extras_require={
        'schemalchemy': [
            'Delorean>=0.5.0',
            'sqlalchemy>=1.1.9,<1.3.0',
        ],
    },
)
