#!/usr/bin/env python3

import setuptools

import pysh
long_description = pysh.__doc__

setuptools.setup(
    name='pysh',
    version='0.1.0',
    author='Mihail Georgiev',
    author_email='misho88@gmail.com',
    description='pysh - easy-to-use subprocess.run',
    long_description=long_description,
    long_description_content_type='text/plain',
    url='https://github.com/misho88/pysh',
    packages=setuptools.find_packages(),
    python_requires='>=3.6',
    py_modules=['pysh']
)
