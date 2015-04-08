# -*- encoding: utf-8 -*-

###########################################
## Achievo remote interface (from pyuac) ##
###########################################

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
        datas = ['name']
        project_model = client.AccountAnalyticAccount
        ids = project_model.search()
        projects = project_model.read(ids, datas)
        return projects

    def hours(self, projectids, from_date=None, to_date=None):
        params = {}
        params["projectids"] = projectids
        if from_date:
            params["from_date"] = from_date.isoformat()
        if to_date:
            params["to_date"] = (to_date - timedelta(1)).isoformat()
        hours = self._urlDispatch("report", **params)
        return hours

