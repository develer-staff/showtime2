#!/usr/bin/env python
# -*- encoding: utf-8 -*-

from flask import Flask, render_template, request, jsonify, url_for, \
    redirect, send_file, abort, session
from odooTimereg import OdooTimereg
from datetime import datetime, timedelta, date
from io import StringIO
import os
import csv
import itsdangerous
import requests

app = Flask(__name__)
app.config.from_envvar("SHOWTIME_SETTINGS")
app.jinja_env.add_extension('pyjade.ext.jinja.PyJadeExtension')

##############################
## Openerp response parsers ##
##############################

def parseProjects(pdict):
    projects = []
    for element in pdict:
        projects.append(element.get("name"))
    return projects

def parseHours(etree):
    hours = []
    for element in etree:
        hours.append(
            {
                "project": element.get("project"),
                "date": datetime.strptime(element.get("date"), "%Y-%m-%d").date(),
                "time": timedelta(minutes = int(element.get("time"))),
                "remark": element.get("remark"),
                "activity": element.get("activity"),
                "billable": element.get("billable"),
                "user": element.get("user"),
            }
        )
    return hours

def dvlrit(url):
    r = requests.post(app.config["DVLRIT_URL"] + "/short_url", timeout=3.0, params={
        "q": url
    })
    return r.content[14:-3]

##################################
# CSRF protection
# http://flask.pocoo.org/snippets/3/

@app.before_request
def csrf_protect():
    if request.method == "POST":
        token = session.pop('_csrf_token', None)
        if not token or token != request.json.get('_csrf_token'):
            abort(403)

def generate_csrf_token():
    if '_csrf_token' not in session:
        session['_csrf_token'] = os.urandom(16)
    return session['_csrf_token']

app.jinja_env.globals['csrf_token'] = generate_csrf_token

##################################
# Exception handler
#

class InvalidUsageJSON(Exception):
    status_code = 400

    def __init__(self, message, status_code=None, payload=None):
        Exception.__init__(self)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        rv = dict(self.payload or ())
        rv['message'] = self.message
        return rv

@app.errorhandler(InvalidUsageJSON)
def handle_invalid_usage(error):
    response = jsonify(error.to_dict())
    response.status_code = error.status_code
    return response

##################################
# Views
#

@app.route('/createlink', methods=["POST"])
def createlink():
    projects = request.json['projects']
    expire = request.json['expire']

    if not expire:
        expire = (date.today() + timedelta(365)).strftime("%Y-%m-%d")

    s = itsdangerous.URLSafeSerializer(app.config["SECRET_KEY"])
    token = s.dumps({
        'projects': projects,
        'expire': expire,
    })

    url = url_for('view', token=token, _external=True)
    try:
        url = dvlrit(url)
    except:
        pass

    return jsonify({
        'link': url
    })


class MonthDate(object):
    """
    Store and represent the couple "year+month" (without day).
    """
    def __init__(self, year, month):
        self.year = year
        self.month = month

    def prev(self):
        y = self.year
        m = self.month - 1
        if m == 0:
            y -= 1
            m = 12
        return MonthDate(y, m)

    def next(self):
        y = self.year
        m = self.month + 1
        if m == 13:
            y += 1
            m = 1
        return MonthDate(y, m)

    @staticmethod
    def fromdate(date):
        return MonthDate(date.year, date.month)

    @staticmethod
    def fromstring(s):
        parts = s.split("-")
        return MonthDate(int(parts[0]), int(parts[1]))

    @staticmethod
    def today():
        today = date.today()
        return MonthDate(today.year, today.month)

    def englishformat(self):
        return self.topython().strftime("%B %Y")

    def topython(self):
        return date(self.year, self.month, 1)

    def __str__(self):
        return "%04d-%02d" % (self.year, self.month)


@app.route('/view/<token>')
def view(token):
    s = itsdangerous.URLSafeSerializer(app.config["SECRET_KEY"])
    try:
        data = s.loads(token)
    except:
        abort(404)

    expire = datetime.strptime(data["expire"], "%Y-%m-%d")
    if expire <= datetime.today():
        return render_template("view_error.jade", error="EXPIRED"), 403

    o = OdooTimereg()
    client = o.login(
        app.config["ODOO_URI"],
        app.config["ODOO_USER"],
        app.config["ODOO_PASSWORD"],
        app.config["ODOO_DB"]
    )

    if "date" in request.args:
        from_date = MonthDate.fromstring(request.args["date"])
    else:
        from_date = MonthDate.today().prev()

    to_date = from_date.next()
    hours = o.hours(client, data["projects"], from_date.topython(), to_date.topython())
    hours = parseHours(hours)

    # Filter non billable hours
    hours = [h for h in hours if h["billable"]]

    total = 0
    for h in hours:
        s = h["time"].total_seconds()
        h["time"] = "%dh %dm" % (s // 3600, (s % 3600) // 60)
        total += s
    total = "%dh %dm" % (total // 3600, (total % 3600) // 60)

    if "csv" in request.args:
        string = StringIO()
        writer = csv.writer(string)
        writer.writerow(["Project", "Date", "User", "Remark", "Time"])
        for hour in hours:
            writer.writerow([
                hour["project"],
                hour["date"].strftime("%d %b %Y"),
                hour["user"],
                hour["remark"].encode("utf-8"),
                hour["time"]
            ])
        string.seek(0)
        fn = "develer-%s-%s.csv" % ("-".join(data["projects"]), from_date.englishformat())
        return send_file(
            string,
            attachment_filename=fn,
            as_attachment=True)

    prev_url = url_for("view", token=token, date=str(from_date.prev()))
    next_url = url_for("view", token=token, date=str(from_date.next()))
    cur_month = from_date.englishformat()

    num_projects = len(data["projects"])
    project_name = ", ".join(data["projects"])
    csv_url = url_for("view", token=token, date=from_date, csv=True)

    return render_template("view.jade",
        project_name=project_name, num_projects=num_projects,
        hours=hours, total=total, cur_month=cur_month,
        prev_url=prev_url, next_url=next_url, csv_url=csv_url)

@app.route('/create')
def create():
    o = OdooTimereg()
    client = o.login(
        app.config["ODOO_URI"],
        app.config["ODOO_USER"],
        app.config["ODOO_PASSWORD"],
        app.config["ODOO_DB"]
    )
    projects = parseProjects(o.projects(client))
    return render_template('create.jade', projects=projects)

@app.route('/summary/<user>')
def summary(user):
    o = OdooTimereg()
    client = o.login(
        app.config["ODOO_URI"],
        app.config["ODOO_USER"],
        app.config["ODOO_PASSWORD"],
        app.config["ODOO_DB"]
    )

    if "from_date" in request.args:
        from_date = datetime.strptime(request.args["from_date"], "%Y-%m-%d")
    else:
        from_date = datetime.today()

    if "to_date" in request.args:
        to_date = datetime.strptime(request.args["to_date"], "%Y-%m-%d")
    else:
        to_date = datetime.today()

    if to_date < from_date:
        raise InvalidUsageJSON("to_date is before from_date")
    if (to_date - from_date).days > 28:
        raise InvalidUsageJSON("too many days")

    uid = o.userid(client, user)
    if uid is None:
        raise InvalidUsageJSON("username unknown")

    totals = o.summary(client, user, from_date, to_date)

    return jsonify(totals)


@app.route('/')
def index():
    return redirect(url_for("create"))

if __name__ == '__main__':
    app.run(host='0.0.0.0')
