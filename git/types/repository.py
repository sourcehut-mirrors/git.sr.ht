import sqlalchemy as sa
import sqlalchemy_utils as sau
from srht.database import Base

class Repository(Base):
    __tablename__ = 'repository'
    id = sa.Column(sa.Integer, primary_key=True)
    created = sa.Column(sa.DateTime, nullable=False)
    updated = sa.Column(sa.DateTime, nullable=False)
    name = sa.Column(sa.Unicode(256), nullable=False)
    owner_id = sa.Column(sa.Integer, sa.ForeignKey('user.id'))
    owner = sa.orm.relationship('User', backref=sa.orm.backref('repos'))
    group_id = sa.Column(sa.Integer, sa.ForeignKey('group.id'))
    group = sa.orm.relationship('Group', backref=sa.orm.backref('repos'))
