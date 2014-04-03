# -*- encoding: utf-8 -*-

###########################################
## Achievo remote interface (from pyuac) ##
###########################################

import urllib, urllib2, urlparse
from xml.etree import ElementTree as ET
from xml.parsers.expat import ExpatError
from datetime import timedelta

ACHIEVO_ENCODING = "ISO-8859-15"

class AccessDenied(Exception):
    pass

class RemoteTimereg:
    """
    RemoteTimereg si interfaccia (in modo sincrono) con il modulo Achievo "remote".
    Sia server che client sono fondamentalmente stateles, l'unico stato è
    l'aver fatto login, condizione obbligatoria per compiere qualsiasi funzione.
    I metodi accettano parametri standard e restituiscono un oggetto ElementTree.
    """

    actions = {"login": "Log into an Achievo server (uri, user, pwd)",
               "query": "Search the project matching the smartquery",
               "whoami": "Returns login info",
               "timereg": "Register worked time",
               "delete": "Delete the timered by id",
               "timereport": "Report time registered in the provided date[s]"}

    def __init__(self):
        self._projects = ET.fromstring("<response />")
        self._login_done = False
        self._auth_done = False

    def login(self, achievouri, user, password):
        """
        Classe di interfaccia per il modulo Achievo "remote"
        Fornire la path di achievo, username e password
        Restituisce il nome utente e rinfresca la sessione di Achievo
        """
        self.user = user
        self.userid = 0
        self.version = None
        self.password = password
        self._achievouri = achievouri
        self._loginurl = urllib.basejoin(self._achievouri, "index.php")
        self._dispatchurl = urllib.basejoin(self._achievouri, "dispatch.php")
        self._keepalive()
        self._login_done = True
        return self.whoami()

    def _keepalive(self):
        """
        Restituisce il nome utente e rinfresca la sessione di Achievo
        """
        # Renew Achievo login to keep the session alive
        auth = urllib.urlencode({"auth_user": self.user,
                                 "auth_pw": self.password})
        if not self._auth_done:
            self._setupAuth()
        # refresh Achievo session
        urllib2.urlopen(self._loginurl, auth).read()

    def _setupAuth(self):
        """
        Imposta l'autenticazione http e la gestione dei cookies
        """
        passman = urllib2.HTTPPasswordMgrWithDefaultRealm()
        # WARN: basic-auth using a URI which is not a pure hostname is
        # broken in Python 2.4.[0123]. This patch fixed it:
        # http://svn.python.org/view/python/trunk/Lib/urllib2.py?rev=45815&r1=43556&r2=45815
        host = urlparse.urlparse(self._achievouri)[1]
        passman.add_password(None, host, self.user, self.password)
        auth_handler = urllib2.HTTPBasicAuthHandler(passman)
        cookie_handler = urllib2.HTTPCookieProcessor()
        opener = urllib2.build_opener(auth_handler, cookie_handler)
        urllib2.install_opener(opener)
        self._auth_done = True

    def _urlDispatch(self, node, action="search", **kwargs):
        """
        Invoca il dispatch.php di Achievo
        """
        params = {"atknodetype": "remote.%s" % node,
                  "atkaction": action}
        # This is the way PHP accepts arrays,
        # without [] it gets only the last value.
        for key, val in kwargs.items():
            if type(val) == list:
                del kwargs[key]
                kwargs[key+"[]"] = [v.encode(ACHIEVO_ENCODING, "replace") for v in val]
            else:
                kwargs[key] = val.encode(ACHIEVO_ENCODING, "replace")
        qstring = urllib.urlencode(params.items() + kwargs.items(), doseq=True)
        page = urllib2.urlopen(self._dispatchurl, qstring).read().strip()
        try:
            return ET.fromstring(page)
        except ExpatError:
            if 'Access denied' in page:
                raise AccessDenied()
            raise

    def whoami(self):
        """
        Restituisce il nome utente della sessione attiva
        """
        elogin = self._urlDispatch("whoami")
        if self.userid == 0:
            self.userid = elogin[0].get("id")
        if self.version == None:
            self.version = elogin[0].get("version", "1.2.1")
        return elogin

    def projects(self):
        projects = self._urlDispatch("report")
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

