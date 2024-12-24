import requests
import urllib3
import json

# audit_log - assumes a JSON structure should be sent, that uses basic auth
# it includes a "name" identifying this application, the client_id/client_secret are
# the basic auth parameters.


class AuditLog(object):
    def __init__(self, appopt, **kwargs):
        '''audit_log - send JSON to a URL using basic auth'''
        (self.app_name,
         self.log_name,
         self.client_id,
         self.client_secret,
         self.url) = appopt.split(',')
        self.verify_tls = True
        self.debug = False
        self.test = False   # stub for testing mode?
        self.active = True    # if audit logging is enabled, and not encountered an error
        self.extra_fields = {}

        if 'verify_tls' in kwargs:
            self.verify_tls = kwargs['verify_tls']
            if self.verify_tls is False:
                urllib3.disable_warnings()
        if 'debug' in kwargs:
            self.debug = kwargs['debug']
        if 'test' in kwargs:
            self.test = kwargs['test']
        if 'extra_fields' in kwargs and kwargs['extra_fields'] != '':
            try:
                self.extra_fields = json.loads(kwargs['extra_fields'])
            except ValueError as e:
                print("Trouble parsing json section audit item extra_fields: {} - {}".format(
                    kwargs['extra_fields'], e))
                raise ValueError

        if self.debug:
            print(f"audit log: debug={self.debug} test={self.test} vrfy_tls={self.verify_tls}")
            print(f"audit log: name={self.app_name} client_id={self.client_id} url={self.url}")

        if self.test:
            return
        # initialize session
        self.session = requests.Session()
        if len(self.client_id):
            self.session.auth = (self.client_id, self.client_secret)
        self.session.headers.update({'Content-Type': 'application/json'})
        self.session.verify = self.verify_tls
        start_msg = {'message': 'starting'}
        self.send(start_msg)

    def send(self, jobj):
        '''send a json blob to the logging endpoint'''
        if self.test or self.active is False:
            return
        jobj['application'] = self.app_name
        jobj['log_type'] = self.log_name
        log_dict = {**jobj, **self.extra_fields}
        log_list = [log_dict]
        if self.debug:
            print("send to ", self.url, type(jobj), json.dumps(log_list))
        try:
            r = self.session.post(self.url, json=log_list)
        except requests.exceptions.RequestException as e:
            print(f"audit log fail: {e}")
            return
        if not r.ok:
            print("audit log post failed", r.status_code, r.content)
            self.active = False
        elif self.debug:
            print(f"audit log post {r.status_code}")
