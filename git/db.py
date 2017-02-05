from sqlalchemy import create_engine, event
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
from git.config import cfg

engine = create_engine(cfg('git.sr.ht', 'connection-string'))
db = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))

Base = declarative_base()
Base.query = db.query_property()

def init_db():
    #import git.types

    @event.listens_for(Base, 'before_insert', propagate=True)
    def before_insert(mapper, connection, target):
        if hasattr(target, 'created'):
            target.created = datetime.utcnow()
        if hasattr(target, 'updated'):
            target.updated = datetime.utcnow()

    @event.listens_for(Base, 'before_update', propagate=True)
    def before_update(mapper, connection, target):
        if hasattr(target, 'updated'):
            target.updated = datetime.utcnow()

    Base.metadata.create_all(bind=engine)
