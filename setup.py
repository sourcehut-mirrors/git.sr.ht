#!/usr/bin/env python3
from distutils.core import setup
import subprocess
import glob
import os

subprocess.call(["make"])

ver = os.environ.get("PKGVER") or subprocess.run(['git', 'describe', '--tags'],
      stdout=subprocess.PIPE).stdout.decode().strip()

setup(
  name = 'gitsrht',
  packages = [
      'gitsrht',
      'gitsrht.types',
      'gitsrht.blueprints',
      'gitsrht.alembic',
      'gitsrht.alembic.versions'
  ],
  version = ver,
  description = 'git.sr.ht website',
  author = 'Drew DeVault',
  author_email = 'sir@cmpwn.com',
  url = 'https://git.sr.ht/~sircmpwn/git.sr.ht',
  install_requires = ['srht', 'flask-login'],
  license = 'AGPL-3.0',
  package_data={
      'gitsrht': [
          'templates/*.html',
          'static/*',
          'hooks/*'
      ]
  },
  scripts = [
      'git-srht-keys',
      'git-srht-update-hook',
      'git-srht-periodic'
  ]
)
