import sqlalchemy as sa
import sqlalchemy_utils as sau
from git.db import Base

class User(Base):
    __tablename__ = 'user'
    id = sa.Column(sa.Integer, primary_key=True)
    created = sa.Column(sa.DateTime, nullable=False)
    updated = sa.Column(sa.DateTime, nullable=False)
    email = sa.Column(sa.String(256), nullable=False)
    paid = sa.Column(sa.Boolean, nullable=False)

    def __repr__(self):
        return '<User {} {}>'.format(self.id, self.username)

    def is_authenticated(self):
        return True
    def is_active(self):
        return True
    def is_anonymous(self):
        return False
    def get_id(self):
        return self.username
