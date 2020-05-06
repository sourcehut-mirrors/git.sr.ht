#!/usr/bin/env python3
from distutils.core import setup
import subprocess
import os
import sys
import importlib.resources

with importlib.resources.path('srht', 'Makefile') as f:
    srht_path = f.parent.as_posix()

make = os.environ.get("MAKE", "make")
subp = subprocess.run([make, "SRHT_PATH=" + srht_path])
if subp.returncode != 0:
    sys.exit(subp.returncode)

ver = os.environ.get("PKGVER") or subprocess.run(['git', 'describe', '--tags'],
      stdout=subprocess.PIPE).stdout.decode().strip()

setup(
  name = 'gitsrht',
  packages = [
      'gitsrht',
      'gitsrht.types',
      'gitsrht.blueprints',
      'gitsrht.blueprints.api',
      'gitsrht.alembic',
      'gitsrht.alembic.versions'
  ],
  version = ver,
  description = 'git.sr.ht website',
  author = 'Drew DeVault',
  author_email = 'sir@cmpwn.com',
  url = 'https://git.sr.ht/~sircmpwn/git.sr.ht',
  install_requires = ['srht', 'scmsrht', 'pygit2'],
  license = 'AGPL-3.0',
  package_data={
      'gitsrht': [
          'templates/*.html',
          'static/*',
          'static/icons/*',
          'hooks/*'
      ]
  },
  scripts = [
      'gitsrht-initdb',
      'gitsrht-migrate',
      'gitsrht-periodic',
  ]
)
