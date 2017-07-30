from flask_sqlalchemy import SQLAlchemy
from flask import Flask
from sweethome import db


class CmdCronInfo(db.Model):

    _tablename_ = 'cron_table'

    id = db.column(db.Integer, primary_key=True, autoincrement=True)
    toggle = db.column(db.Boolean)
    day = db.column(db.Integer)
    hour = db.column(db.Integer)
    minute = db.column(db.Integer)
    mode = db.column(db.String(20))
    degree = db.column(db.Integer)
    wind = db.column(db.Integer)

    def __init__(self, toggle, day, hour, minute):
        self.toggle = toggle
        self.day = day
        self.hour = hour
        self.minute = minute

    def set_cmd(self, mode, degree, wind):
        self.mode = mode
        self.degree = degree
        self.wind = wind

    def __repr__(self):
        return '<User %r>' % self.mode


def init_db():
    db.create_all()
