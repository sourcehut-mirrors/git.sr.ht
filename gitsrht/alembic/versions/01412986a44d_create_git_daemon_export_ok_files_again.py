"""Create git-daemon-export-ok files again

Revision ID: 01412986a44d
Revises: dacab1dcba45
Create Date: 2020-08-18 23:58:45.590223

"""

# revision identifiers, used by Alembic.
revision = '01412986a44d'
down_revision = 'dacab1dcba45'

import sys
import os
sys.path.append(os.path.dirname(__file__))
import a8ad35a0bee7_create_git_daemon_export_ok_files


upgrade   = a8ad35a0bee7_create_git_daemon_export_ok_files.upgrade
downgrade = a8ad35a0bee7_create_git_daemon_export_ok_files.downgrade
