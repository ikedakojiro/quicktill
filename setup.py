#!/usr/bin/env python3

from distutils.core import setup

setup(name='quicktill16',
      version='16.8',
      description='Quick till and stock control library',
      author='Stephen Early',
      author_email='steve@assorted.org.uk',
      url='https://github.com/sde1000/quicktill',
      packages=['quicktill', 'quicktill.tillweb',
                'quicktill.tillweb.migrations'],
      package_data={'quicktill.tillweb':
                    ['static/tillweb/*.js',
                     'static/tillweb/*.css',
                     'static/tillweb/multi-select/*/*',
                     'static/tillweb/select2/*',
                     'templates/tillweb/*.html',
                     'templates/tillweb/*.ajax',
                    ]},
      scripts=['runtill'],
)
