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
        project_model = client.ProjectProject
        project_ids = project_model.search([
            ('allow_timesheets', '=', True),
            ('billable_type', '!=', 'no'),
            ])
        projects = project_model.read(project_ids, ['name'])
        return projects

    def hours(self, client, projectids, from_date=None, to_date=None):
        timesheet_model = client.AccountAnalyticLine
        # 2020-01-01: Migration date from Openerp to Odoo.
        # An imported timesheet (old one) has 'non_billable_project' value
        # in 'timesheet_invoice_type' when a timesheet is not billable
        # because in Openerp, 'timesheet_invoice_type' was required.
        # In Odoo this field is not required, so it can be empty.
        ids = timesheet_model.search([
            ('project_id', 'in', projectids),
            ('date', '>=', from_date.strftime('%Y-%m-%d')),
            ('date', '<', to_date.strftime('%Y-%m-%d')),
            '|',
            ('timesheet_invoice_type', '!=', 'non_billable_project'),
            ('timesheet_invoice_type', '=', False),
        ])
        if not ids:
            return []

        data = timesheet_model.read(ids, ['project_id', 'user_id', 'date',
                                          'name', 'timesheet_invoice_type',
                                          'unit_amount'])
        hours = []
        for item in data:
            h = {}
            h["project"] = item["project_id"]
            h["date"] = item["date"]
            h["user"] = item["user_id"][1]
            h["remark"] = item['name']
            h["time"] = int(item["unit_amount"]*60+.5)
            h["billable"] = True
            hours.append(h)

        return hours

    def userid(self, client, username):
        """Get the OpenERP userid of username"""
        ids = client.ResUsers.search(['login=%s' % username])
        if len(ids) != 1:
            return None
        return ids[0]

    def summary(self, client, userid, from_date, to_date):
        timesheet_model = client.AccountAnalyticLine

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
