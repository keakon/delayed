# -*- coding: utf-8 -*-

from setuptools import setup


with open('README.md', 'r') as f:
    README = f.read()

setup(
    name='delayed',
    version=__import__('delayed').__version__,
    description='a simple but robust task queue',
    long_description=README,
    long_description_content_type='text/markdown',
    author='keakon',
    author_email='keakon@gmail.com',
    url='https://github.com/keakon/delayed',
    packages=['delayed'],
    python_requires='>=2.7',
    install_requires=['hiredis', 'redis', 'msgpack'],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: MacOS :: MacOS X',
        'Operating System :: POSIX',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy',
    ],
    tests_require=['pytest', 'pytest-runner'],
)
