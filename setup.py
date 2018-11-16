#!/usr/bin/env python3
from setuptools import setup
import subprocess
import glob
import os
import site
import sys

site_packages = site.getsitepackages()[0]
srht_path = os.path.join(site_packages, "srht")
subp = subprocess.run(["make", "SRHT_PATH=" + srht_path])
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
      'gitsrht.alembic',
      'gitsrht.alembic.versions'
  ],
  version = ver,
  description = 'git.sr.ht website',
  author = 'Drew DeVault',
  author_email = 'sir@cmpwn.com',
  url = 'https://git.sr.ht/~sircmpwn/git.sr.ht',
  install_requires = ['srht', 'flask-login', 'redis', 'pygit2', 'pygments'],
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
      'git-srht-dispatch',
      'git-srht-keys',
      'git-srht-shell',
      'git-srht-update-hook',
      'git-srht-periodic'
  ]
)
