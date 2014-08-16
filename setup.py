#!/usr/bin/env python

from distutils.core import setup

setup(name='spideTor',
      version='1.0',
	  description='Find misplaced files from your torrent metafiles and symlink for seeding',
	  author='Noah Crocker',
	  author_email='necrocke@umich.edu',
	  url='https://github.com/VerTiGoEtrex/spideTor',
	  packages=['spideTor'],
	  console=['spideTor/spideTor.py']
	 )