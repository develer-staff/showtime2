#!/usr/bin/env python
# -*- encoding: utf-8 -*-

from flask import Flask, render_template, request, jsonify, url_for
from remoteTimereg import RemoteTimereg
from datetime import datetime, timedelta
import itsdangerous
import requests

app = Flask(__name__)
app.config.from_envvar("SHOWTIME_SETTINGS")
app.jinja_env.add_extension('pyjade.ext.jinja.PyJadeExtension')

app.debug = True

##################################
## Achievo response XML parsers ##
##################################

## Needed only if you extract the parson module
#from xml.etree import ElementTree as ET
#import datetime

def parseProjects(etree):
    projects = []
    for element in etree:
        projects.append(element.get("name"))
    return projects

def parseHours(etree):
    hours = []
    for element in etree:
        hours.append(
            {
                "project": element.get("project"),
                "date": datetime.strptime(element.get("date"), "%Y-%m-%d"),
                "time": timedelta(minutes = int(element.get("time"))),
                "remark": element.get("remark"),
                "activity": element.get("activity"),
                "phase": element.get("phase"),
                "user": element.get("user"),
            }
        )
    return hours

def dvlrit(url):
    r = requests.get(app.config["DVLRIT_URL"] + "/short_url", timeout=3.0, params={
        "q": url
    })
    return r.data[14:-3]

##################################

@app.route('/createlink', methods=["POST"])
def createlink():
    projects = request.json['projects']
    expire = request.json['expire']

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

@app.route('/view/<token>')
def view(token):
    pass

@app.route('/')
def index():
    r = RemoteTimereg()
    r.login(
        app.config["ACHIEVO_URI"],
        app.config["ACHIEVO_USER"],
        app.config["ACHIEVO_PASSWORD"]
    )
    projects = parseProjects(r.projects())

    return render_template('index.jade', projects=projects)


if __name__ == '__main__':
    app.run()
