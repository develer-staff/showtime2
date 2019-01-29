# -*- encoding: utf-8 -*-

###########################
## odoo remote interface ##
###########################

import erppeek
from collections import defaultdict


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
        ids = project_model.search(['use_timesheets=True', 'invoice_on_timesheets=True', 'state=("open","pending")'])
        projects = project_model.read(ids, ['name'])
        return projects

    def hours(self, client, projectids, from_date=None, to_date=None):
        # Read all billable types and differentiate between billable and non-billable
        # using the discount factor (if < 100.0, we consider it billable, since 100%
        # is non billable).
        billable = set()
        for fact in client.Hr_timesheet_invoiceFactor.read([]):
            if fact["factor"] < 100:
                billable.add(fact["id"])

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

            # to_invoice is either a boolean, or a [id, name] field.
            if type(item['to_invoice']) == bool:
                h["billable"] = bool(item['to_invoice'])
            else:
                h["billable"] = item['to_invoice'][0] in billable
            hours.append(h)

        return hours

    def userid(self, client, username):
        """Get the OpenERP userid of username"""
        ids = client.ResUsers.search(['alias_name=%s' % username])
        if len(ids) != 1:
            return None
        return ids[0]

    def summary(self, client, userid, from_date, to_date):
        timesheet_model = client.HrAnalyticTimesheet

        print [
            'user_id = %s' % userid,
            'date >= %s' % from_date,
            'date <= %s' % to_date,
        ]

        ids = timesheet_model.search([
            'user_id = %s' % userid,
            'date >= %s' % from_date,
            'date <= %s' % to_date,
        ])
        if not ids:
            return []

        totals = defaultdict(float)
        data = timesheet_model.read(ids, ['date', 'unit_amount'])
        for item in data:
            totals[item['date']] += float(item['unit_amount'])
        return totals
