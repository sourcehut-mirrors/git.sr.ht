import sqlalchemy as sa
import sqlalchemy_utils as sau
from srht.database import Base

class SSHKey(Base):
    __tablename__ = 'sshkey'
    id = sa.Column(sa.Integer, primary_key=True)
    user_id = sa.Column(sa.Integer, sa.ForeignKey('user.id'), nullable=False)
    user = sa.orm.relationship('User', backref=sa.orm.backref('ssh_keys'))
    meta_id = sa.Column(sa.Integer, nullable=False, unique=True, index=True)
    key = sa.Column(sa.String(4096), nullable=False, index=True)
    fingerprint = sa.Column(sa.String(512), nullable=False)

    def __repr__(self):
        return '<SSHKey {} {}>'.format(self.id, self.fingerprint)
