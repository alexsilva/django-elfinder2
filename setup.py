# econding=utf8

import os
from setuptools import setup, find_packages

def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

README = read('README.rst')

setup(
    name = 'django-elfinder',
    version = '0.2-fsdriver',
    description = 'Django connector for elFinder 2',
    long_description = README,
    author = 'Martin Bohacek',
    author_email = 'bohacekm@gmail.com',
    url = 'https://github.com/bohyn/django-elfinder/',
    download_url = 'https://github.com/bohyn/django-elfinder/tarball/v0.2-fsdriver',
    packages = ['elfinder', 'elfinder.volume_drivers'],
    include_package_data=True,
    requires = ['django (>=1.3)', 'mptt (>=0.5.2)'],
)
