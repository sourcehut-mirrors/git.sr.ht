import sqlalchemy as sa
import sqlalchemy_utils as sau
from srht.database import Base
from enum import Enum

class AccessMode(Enum):
    ro = 'ro'
    rw = 'rw'

class Access(Base):
    __tablename__ = 'access'
    id = sa.Column(sa.Integer, primary_key=True)
    created = sa.Column(sa.DateTime, nullable=False)
    updated = sa.Column(sa.DateTime, nullable=False)
    repo_id = sa.Column(sa.Integer, sa.ForeignKey('repository.id'), nullable=False)
    repo = sa.orm.relationship('Repository', backref='access_grants')
    user_id = sa.Column(sa.Integer, sa.ForeignKey('user.id'), nullable=False)
    user = sa.orm.relationship('User', backref='access_grants')
    mode = sa.Column(sau.ChoiceType(AccessMode, impl=sa.String()),
            nullable=False, default=AccessMode.ro)

    def __repr__(self):
        return '<Access {} {}->{}:{}>'.format(
                self.id, self.user_id, self.repo_id, self.mode)
