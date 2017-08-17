from flask import Flask, request, json, jsonify
from flask_restful import Resource, Api, reqparse, abort
import subprocess
import logging
import re

# from models import CmdCronInfo
from logging.config import fileConfig
from crontab import CronTab
from flask_sqlalchemy import SQLAlchemy

# Remove all handlers associated with the root logger object.
# for handler in logging.root.handlers[:]:
#     logging.root.removeHandler(handler)

# Reconfigure logging again, this time with a file.
logging.basicConfig(filename='log_sweet_home.log', level=logging.INFO, format='%(asctime)-15s %(filename)s:%(lineno)s %(levelname)s:%(message)s')

# fileConfig('logging_config.ini')
# logger = logging.getLogger()
logging.info('test logger start...')

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////home/benjamin/project/SweetHome/db/test.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True
api = Api(app)
db = SQLAlchemy(app)


parser = reqparse.RequestParser()
parser.add_argument('mode', type=str, required=True)
parser.add_argument('degree', type=int, required=True)
parser.add_argument('wind', type=int, required=True)

cronParser = reqparse.RequestParser()
cronParser.add_argument('id', type=int, required=False)
cronParser.add_argument('day', type=int, required=True)
cronParser.add_argument('hour', type=int, required=True)
cronParser.add_argument('minute', type=int, required=True)
cronParser.add_argument('toggle', type=bool, required=True)
cronParser.add_argument('mode', type=str, required=False)
cronParser.add_argument('degree', type=int, required=False)
cronParser.add_argument('wind', type=int, required=False)

cron = CronTab(user=True)


class CmdCronInfo(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    toggle = db.Column(db.Boolean)
    day = db.Column(db.Integer)
    hour = db.Column(db.Integer)
    minute = db.Column(db.Integer)
    mode = db.Column(db.String(20))
    degree = db.Column(db.Integer)
    wind = db.Column(db.Integer)

    def __init__(self, toggle, day, hour, minute):
        self.toggle = toggle
        self.day = day
        self.hour = hour
        self.minute = minute

    def set_cmd(self, mode='COOL', degree=25, wind=0):
        self.mode = mode
        self.degree = degree
        self.wind = wind

    def __repr__(self):
        return '<CmdCronInfo_%d>' % self.id

    @property
    def to_json(self):
        if self.toggle:
            return {
                'id': self.id,
                'toggle': self.toggle,
                'day': self.day,
                'hour': self.hour,
                'minute': self.minute,
                'mode': self.mode,
                'degree': self.degree,
                'wind': self.wind
            }
        else:
            return {
                'id': self.id,
                'toggle': self.toggle,
                'day': self.day,
                'hour': self.hour,
                'minute': self.minute
            }


def send_cmd(cmd):
    subprocess.Popen(cmd, shell=True)
    ret_data = {'notify': cmd + ' sent successfully'}
    return build_json_ret(0, ret_data)


def build_json_ret(code, data):
    if code == 0:
        return {'Code': 0,
                'Message': 'Success',
                'Data': data}
    else:
        return {'Code': code,
                'Message': data}


def add_to_crontab(cron_info: CmdCronInfo):
    if cron_info.toggle:
        cmd = 'irsend SEND_ONCE haierac HAIER_%s_%d_%d' % (cron_info.mode, cron_info.degree, cron_info.wind)
    else:
        cmd = 'irsend SEND_ONCE haierac HAIER_CLOSE'

    comment_filter = 'air_ctl no_' + str(cron_info)
    cron.remove_all(comment=comment_filter)

    job = cron.new(command=cmd, comment='air_ctl')
    cron_info.day
    if cron_info.day == 0:
        job.day.every(1)
    elif cron_info.day == 1:
        job.dow.on('MON', 'TUE', 'WED', 'THU', 'FRI')
    elif cron_info.day == 2:
        job.dow.on('SAT', 'SUN')
    else:
        job.day.every(1)

    job.hour.on(cron_info.hour)
    job.minute.on(cron_info.minute)
    job.enable()
    job.set_comment('air_ctl no_' + str(cron_info.id))
    cron.write_to_user(user=True)
    return True


def reload_from_db():
    logging.info('reloading from previous data')
    pre_iter = cron.find_comment(re.compile("^air_ctl"))
    for job in pre_iter:
        logging.info("removing job %s", job)
        cron.remove(job)
    cron.write_to_user(user=True)
    cron_iter = CmdCronInfo.query.all()
    for cron_item in cron_iter:
        add_to_crontab(cron_item)
    cron.write_to_user(user=True)


class AirCtl(Resource):
    def post(self):
        logging.info('AirCtl called')
        args = parser.parse_args()
        cmd = 'irsend SEND_ONCE haierac HAIER_%s_%d_%d' % (args['mode'], args['degree'], args['wind'])
        return send_cmd(cmd)


class AirCtlRaw(Resource):
    def get(self, ircmd):
        logging.info('AirCtlRaw called with cmd: %s', ircmd)
        cmd = 'irsend SEND_ONCE haierac ' + ircmd
        return send_cmd(cmd)


class ShutDownAirCtl(Resource):
    def get(self):
        logging.info('ShutDownAirCtl called')
        cmd = 'irsend SEND_ONCE haierac HAIER_CLOSE'
        return send_cmd(cmd)


class ScheduleJob(Resource):
    def post(self):
        logging.info('ScheduleJob called')
        args = cronParser.parse_args()

        # add to db
        cron_info = CmdCronInfo(args['toggle'], args['day'], args['hour'], args['minute'])
        cron_info.set_cmd(args['mode'], args['degree'], args['wind'])
        db.session.add(cron_info)
        db.session.commit()

        add_to_crontab(cron_info)

        json_str = json.dumps(cron_info.to_json)
        logging.info('add json_str : %s', json_str)
        ret_data = {'id': cron_info.id}
        return build_json_ret(0, ret_data)


class UpdateJob(Resource):
    def post(self):
        logging.info('UpdateJob called')
        args = cronParser.parse_args()
        cron_info = CmdCronInfo.query.filter_by(id=args['id']).first_or_404()
        cron_info.toggle = args['toggle']
        cron_info.set_cmd(args['mode'], args['degree'], args['wind'])
        cron_info.day = args['day']
        cron_info.hour = args['hour']
        cron_info.minute = args['minute']

        db.session.add(cron_info)
        json_str = json.dumps(cron_info.to_json)
        logging.info('update json_str to db : %s', json_str)
        db.session.commit()

        add_to_crontab(cron_info)

        json_str = json.dumps(cron_info.to_json)
        logging.info('update json_str : %s', json_str)
        ret_data = {'id': cron_info.id}
        return build_json_ret(0, ret_data)


class GetAllJobs(Resource):
    def get(self):
        logging.info('getting all scheduled jobs')
        cron_iter = CmdCronInfo.query.all()
        json_array = jsonify([i.to_json for i in cron_iter])
        return json_array


class ClearAllJobs(Resource):
    def get(self):
        logging.info('clearing all scheduled jobs')
        pre_iter = cron.find_comment(re.compile('^air_ctl'))
        for job in pre_iter:
            logging.info("removing job %s", job)
            cron.remove(job)
        cron.write_to_user(user=True)

        cron_iter = CmdCronInfo.query.all()
        for item in cron_iter:
            db.session.delete(item)
        db.session.commit()
        ret_data = {'notify': 'schedules all removed successfully'}
        return build_json_ret(0, ret_data)


api.add_resource(AirCtl, '/ircmd')
api.add_resource(AirCtlRaw, '/ircmd/<string:ircmd>')
api.add_resource(ShutDownAirCtl, '/air_ctl_close')
api.add_resource(ScheduleJob, '/set_cron')
api.add_resource(GetAllJobs, '/get_cron')
api.add_resource(ClearAllJobs, '/clear_cron')
api.add_resource(UpdateJob, '/update_cron')

db.create_all()
reload_from_db()


if __name__ == '__main__':
    app.debug = True
    app.run()

