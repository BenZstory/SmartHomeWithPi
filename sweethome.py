from flask import Flask, request, json, jsonify
from flask_restful import Resource, Api, reqparse, abort
import subprocess
import logging

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
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////tmp/test.db'
api = Api(app)
db = SQLAlchemy(app)


parser = reqparse.RequestParser()
parser.add_argument('mode', type=str, required=True)
parser.add_argument('degree', type=int, required=True)
parser.add_argument('wind', type=int, required=True)

cronParser = reqparse.RequestParser()
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

    def set_cmd(self, mode, degree, wind):
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
    ret = cmd + ' sent successfully.'
    return {'msg': ret}


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

        toggle = args['toggle']
        if toggle:
            cmd = 'irsend SEND_ONCE haierac HAIER_%s_%d_%d' % (args['mode'], args['degree'], args['wind'])
        else:
            cmd = 'irsend SEND_ONCE haierac HAIER_CLOSE'

        new_job = cron.new(command=cmd, comment='air_ctl')

        if args['day'] == 0:
            new_job.day.every(1)
        elif args['day'] == 1:
            new_job.dow.on('MON', 'TUE', 'WED', 'THU', 'FRI')
        elif args['day'] == 2:
            new_job.dow.on('SAT', 'SUN')
        else:
            new_job.day.every(1)

        new_job.hour.on(args['hour'])
        new_job.minute.on(args['minute'])
        new_job.enable()
        cron.write_to_user(user=True)

        cron_info = CmdCronInfo(toggle, args['day'], args['hour'], args['minute'])
        cron_info.set_cmd(args['mode'], args['degree'], args['wind'])
        db.session.add(cron_info)
        db.session.commit()
        json_str = json.dumps(cron_info.to_json)
        logging.info('json_str : %s', json_str)
        return json_str + '  is scheduled'


class GetAllJobs(Resource):
    def get(self):
        logging.info('getting all scheduled jobs')
        cron_iter = CmdCronInfo.query.all()
        jsonstr = jsonify([i.to_json for i in cron_iter])
        return jsonstr


class ClearAllJobs(Resource):
    def get(self):
        logging.info('clearing all scheduled jobs')
        pre_iter = cron.find_comment('air_ctl')
        for job in pre_iter:
            logging.info("removing job %s", job)
        cron.remove_all(comment='air_ctl')
        cron.write_to_user(user=True)

        cron_iter = CmdCronInfo.query.all()
        for item in cron_iter:
            db.session.delete(item)
        db.session.commit()
        return "schedules all removed successfully"


api.add_resource(AirCtl, '/ircmd')
api.add_resource(AirCtlRaw, '/ircmd/<string:ircmd>')
api.add_resource(ShutDownAirCtl, '/air_ctl_close')
api.add_resource(ScheduleJob, '/set_cron')
api.add_resource(GetAllJobs, '/get_cron')
api.add_resource(ClearAllJobs, '/clear_cron')
db.create_all()


if __name__ == '__main__':
    app.debug = True
    app.run()

