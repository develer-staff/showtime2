# -*- encoding: utf-8 -*-

###########################
## odoo remote interface ##
###########################

import urllib, urllib2, urlparse
import erppeek
from xml.etree import ElementTree as ET
from xml.parsers.expat import ExpatError
from datetime import timedelta


class AccessDenied(Exception):
    pass


class OdooTimereg:

    def login(self, odoouri, user, password, db):
        self.user = user
        self.password = password
        self.db = db
        self._odoouri = odoouri
        return erppeek.Client(
            self._odoouri,
            db=self.db,
            user=self.user,
            password=self.password)

    def projects(self, client):
        project_model = client.AccountAnalyticAccount
        ids = project_model.search(['use_timesheets=True', 'invoice_on_timesheets=True', 'state=open'])
        projects = project_model.read(ids, ['name'])
        return projects

    def hours(self, client, projectids, from_date=None, to_date=None):
        timesheet_model = client.HrAnalyticTimesheet
        ids = timesheet_model.search([
            'account_name=%s' % ",".join(['"'+p+'"' for p in projectids]),
            'date >= %s' % from_date,
            'date < %s' % to_date,
        ])
        if not ids:
            return []

        data = timesheet_model.read(ids, ['account_name', 'user_id', 'date', 'line_id', 'to_invoice', 'unit_amount'])

        hours = []
        for item in data:
            if not item['to_invoice']:
                continue
            h = {}
            h["project"] = item["account_name"]
            h["date"] = item["date"]
            h["user"] = item["user_id"][1]
            h["remark"] = item["line_id"][1]
            h["time"] = int(item["unit_amount"]*60+.5)
            h["billable"] = bool(item['to_invoice'])
            hours.append(h)

        return hours

