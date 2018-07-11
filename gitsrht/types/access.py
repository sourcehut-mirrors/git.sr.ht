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
    mode = sa.Column(sau.ChoiceType(AccessMode, impl=sa.String()),
            nullable=False, default=AccessMode.ro)

    user_id = sa.Column(sa.Integer, sa.ForeignKey('user.id'), nullable=False)
    user = sa.orm.relationship('User', backref='access_grants')

    repo_id = sa.Column(sa.Integer,
            sa.ForeignKey('repository.id', ondelete="CASCADE"),
            nullable=False)
    repo = sa.orm.relationship('Repository',
            backref=sa.orm.backref('access_grants', cascade="all, delete"))

    def __repr__(self):
        return '<Access {} {}->{}:{}>'.format(
                self.id, self.user_id, self.repo_id, self.mode)
