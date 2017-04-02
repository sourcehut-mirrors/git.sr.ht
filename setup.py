#!/usr/bin/env python3
from distutils.core import setup
import subprocess
import glob

subprocess.call(["make"])

setup(
  name = 'gitsrht',
  packages = [
      'gitsrht',
      'gitsrht.types',
      'gitsrht.blueprints',
  ],
  version = subprocess.run(['git', 'describe', '--tags'],
      stdout=subprocess.PIPE).stdout.decode().strip(),
  description = 'git.sr.ht website',
  author = 'Drew DeVault',
  author_email = 'sir@cmpwn.com',
  url = 'https://git.sr.ht/~sircmpwn/git.sr.ht',
  requires = ['srht'],
  license = 'GPL-2.0',
  package_data={
      'gitsrht': [
          'templates/*.html',
          'static/*',
      ]
  },
  scripts = ['git-srht-keys']
)
