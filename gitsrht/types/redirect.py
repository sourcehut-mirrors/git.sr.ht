import sqlalchemy as sa
import sqlalchemy_utils as sau
from srht.database import Base
from enum import Enum

class Redirect(Base):
    __tablename__ = 'redirect'
    id = sa.Column(sa.Integer, primary_key=True)
    created = sa.Column(sa.DateTime, nullable=False)
    name = sa.Column(sa.Unicode(256), nullable=False)
    owner_id = sa.Column(sa.Integer, sa.ForeignKey('user.id'), nullable=False)
    owner = sa.orm.relationship('User')
    path = sa.Column(sa.Unicode(1024))
    new_repo_id = sa.Column(
            sa.Integer,
            sa.ForeignKey('repository.id'),
            nullable=False)
    new_repo = sa.orm.relationship('Repository')
