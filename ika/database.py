import re
from sqlalchemy import create_engine
from sqlalchemy import Column, ForeignKey
from sqlalchemy import DateTime, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import backref, relationship, validates
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.sql import func
from sqlalchemy_utils import JSONType, PasswordType

from ika.conf import settings


Base = declarative_base()

engine = create_engine(settings.database)
session_factory = sessionmaker(bind=engine)
Session = scoped_session(session_factory)


class Account(Base):
    __tablename__ = 'account'
    id = Column(Integer, primary_key=True)
    email = Column(String(255))
    password = Column(PasswordType(max_length=128,
        schemes=['bcrypt_sha256', 'md5_crypt'], deprecated=['md5_crypt']))
    vhost = Column(String(255))
    created_on = Column(DateTime, default=func.now())
    last_login = Column(DateTime, default=func.now())

    @validates('email')
    def validate_email(self, key, value):
        assert '@' in value
        return value

    @classmethod
    def find_by_nick(cls, nick):
        nick = Nick.find_by_name(nick)
        if nick is None:
            return None
        return nick.account or nick.account_alias


class Nick(Base):
    __tablename__ = 'nick'
    id = Column(Integer, primary_key=True)
    name = Column(String(32), unique=True)
    account_id = Column(Integer, ForeignKey('account.id'))
    account = relationship('Account', foreign_keys='Nick.account_id', backref=backref('name', uselist=False))
    account_alias_id = Column(Integer, ForeignKey('account.id'))
    account_alias = relationship('Account', foreign_keys='Nick.account_alias_id', backref='aliases')
    last_use = Column(DateTime, default=func.now())

    @classmethod
    def find_by_name(cls, name):
        session = Session()
        return session.query(Nick).filter(func.lower(Nick.name) == func.lower(name)).first()


class Channel(Base):
    __tablename__ = 'channel'
    id = Column(Integer, primary_key=True)
    name = Column(String(255), unique=True)
    data = Column(JSONType, default=dict())
    created_on = Column(DateTime, default=func.now())
    flags = relationship('Flag', backref='channel', order_by='desc(Flag.type)')

    @classmethod
    def find_by_name(cls, name):
        session = Session()
        return session.query(Channel).filter(func.lower(Channel.name) == func.lower(name)).first()

    def get_flags_by_user(self, user):
        type = 0
        for flag in self.flags:
            if flag.match_mask(user.mask) or (user.account and (flag.target.lower() == user.account.name.name.lower())):
                type |= flag.type
        return type


class Flag(Base):
    __tablename__ = 'flag'
    id = Column(Integer, primary_key=True)
    channel_id = Column(Integer, ForeignKey('channel.id'))
    target = Column(String(255))
    type = Column(Integer)
    created_on = Column(DateTime, default=func.now(), onupdate=func.current_timestamp())

    @classmethod
    def flags_by_target(cls, target):
        session = Session()
        return session.query(Flag).filter(func.lower(Flag.target) == func.lower(target))

    def match_mask(self, mask):
        if ('!' not in self.target) or ('@' not in self.target):
            return False
        regex = re.escape(self.target)
        regex = regex.replace('\*', '.+?')
        regex = '^{}$'.format(regex)
        pattern = re.compile(regex, re.IGNORECASE)
        return pattern.match(mask) is not None
