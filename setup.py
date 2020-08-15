# coding=utf-8
from setuptools import setup, find_packages

with open('README.rst') as f:
    long_description = ''.join(f.readlines())

setup(
    name='anidbcli',
    version='1.65',
    keywords='Anidb UDP API CLI client ed2k rename mylist',
    description='Simple CLI for managing your anime collection using AniDB UDP API.',
    long_description=long_description,
    author='Štěpán Adámek',
    author_email='adamek.stepan@gmail.com',
    license='MIT',
    url='https://github.com/adameste/anidbcli',
    zip_safe=False,
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'anidbcli = anidbcli:main',
        ]
    },
    install_requires=[
        'click',
        'pycryptodome',
        'colorama',
        'pyperclip',
        'joblib',
        'fuzzywuzzy'
    ],
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Console',
        'Intended Audience :: End Users/Desktop',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Topic :: Utilities',
        'Topic :: Multimedia :: Video'
    ],
)
