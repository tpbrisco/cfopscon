import requests
import urllib3
import sys
import json
from urllib.parse import urlparse
import time

TASK_LOGS = 1
task_index = {
    TASK_LOGS: 'TASK_LOGS'
}


class task_logs(object):
    '''object for tracking "bosh logs" requests'''
    def __init__(self, task_type, query, task_url):
        self.t_type = task_type
        self.t_state = 0
        self.t_query = query
        self.t_url = task_url
        self.t_try_count = 0
        self.t_results_code = 0

    def __repr__(self):
        return "%s:%s" % (task_index[self.t_type], self.t_url)


class Director(object):
    '''Director(bosh url, bosh username, bosh password) - generate an object to talk to BOSH'''
    def __init__(self, url, user, password, **kwargs):
        self.debug = False
        self.verify_tls = True
        if 'debug' in kwargs:
            self.debug = kwargs['debug']
        if 'verify_tls' in kwargs:
            self.verify_tls = kwargs['verify_tls']
            if self.verify_tls is False:
                urllib3.disable_warnings()
        self.bosh_url = url
        self.bosh_user = user
        self.bosh_pass = password
        # get BOSH session initialization info
        init_r = requests.get(self.bosh_url + "/info",
                              verify=self.verify_tls)
        if not init_r.ok:
            print("error initializing", self.bosh_url)
            sys.exit(1)
        init_json = init_r.json()
        # cache key URLs
        self.uaa_url = init_json['user_authentication']['options']['url']
        # set up internal cached data structures
        self.init_auth(self.uaa_url, self.bosh_user, self.bosh_pass)
        self.get_deployments()
        self.pending_tasks = list()

    def oauth_token_expires(self):
        '''oauth_token_expires() - return number of seconds until current key expires'''
        return int(self.oauth['expires_in'])

    def refresh_token(self):
        '''refresh_token: update authorization tokens'''
        if self.debug:
            print("refreshing token", self.oauth['access_token'][:20], "...")
        r = self.session.post(
            self.uaa_url + '/oauth/token',
            data={'refresh_token': self.oauth['refresh_token'],
                  'grant_type': 'refresh_token',
                  'client_id': 'bosh_cli'},
            auth=('bosh_cli', ''),
            verify=self.verify_tls
            )
        if not r.ok:
            print(f"oauth request({r.status_code}) {r.content}")
            return
        j = r.json()
        self.oauth = j.copy()
        if self.debug:
            print("new token", self.oauth['access_token'][:20], "...")
        self.session.headers.update(
            {'Authorization': j['token_type'] + ' ' + j['access_token']})

    def init_auth(self, auth_url, username, password):
        '''init_auth(oauth url, username, password): initial login to BOSH director'''
        self.session = requests.Session()
        r = self.session.post(
            auth_url + '/oauth/token',
            data={'username': username,
                  'password': password,
                  'grant_type': 'password',
                  'client_id': 'bosh_cli'},
            auth=('bosh_cli', ''),
            verify=self.verify_tls)
        if not r.ok:
            print(f"oauth request({r.status_code}) {r.content}")
        j = r.json()
        self.oauth = j.copy()
        # update auth headers in persisted session
        self.session.headers.update({'Authorization': j['token_type'] + ' ' + j['access_token']})

    def get_deployments(self):
        '''get a list of deployments on this director'''
        d_r = self.session.get(self.bosh_url + "/deployments",
                               verify=self.verify_tls)
        if d_r.ok:
            self.deployments = list()
            for d in d_r.json():
                self.deployments.append(d['name'])
            if self.debug:
                print("deployments", self.deployments)
        else:
            print("error getting deployments: ", d_r.content)
            sys.exit(1)

    def get_deployment_jobs(self, deployment):
        '''return a list of jobs associated with this deployment'''
        j_r = self.session.get(self.bosh_url + "/deployments/" + deployment + "/vms",
                               params={
                                   'exclude_configs': True,
                                   'exclude_releases': True,
                                   'exclude_stemcells': True},
                               verify=self.verify_tls)
        r = list()
        if j_r.ok:
            for j in j_r.json():
                r.append("{}/{}".format(j['job'], j['id']))
            return json.dumps(r, indent=2)
        else:
            return list()

    def submit_logs_job(self, deployment, jobs):
        '''Submit a job to BOSH to fetch logs'''
        logs_url = "%s/deployments/%s/jobs/%s/logs" % (
            self.bosh_url, deployment, jobs)
        if self.debug:
            print("submit for logs", logs_url)
        # expect a 302 back, showing the location for download, once completed
        logs_resp = self.session.get(logs_url, params={'type': 'job'},
                                     allow_redirects=False,
                                     verify=self.verify_tls)
        if not logs_resp.status_code == 302:
            print("error calling bosh:", logs_resp.content)
            return False    # we need the location
        logs_task = urlparse(logs_resp.headers['Location']).path
        if self.debug:
            print("logs task:", logs_task)
        # add to director's job queue -- director.TASK_LOGS type
        self.pending_tasks.append(task_logs(TASK_LOGS,
                                            "%s %s" % (deployment, jobs),
                                            logs_task))
        if self.debug:
            print("pending tasks:", self.pending_tasks)
        return True

    def get_logs_job(self, link):
        '''get download URL for a bosh logs command'''
        logs_t_r = self.session.get(self.bosh_url + link,
                                    verify=self.verify_tls)
        task_state = logs_t_r.json()['state']
        while task_state != 'done':
            if self.debug:
                print("download logs: sleep until job ready")
            time.sleep(1)
            logs_t_r = self.session.get(self.bosh_url + link,
                                        verify=self.verify_tls)
            task_state = logs_t_r.json()['state']
        # check on job succeed/fail
        # task_result_r = self.session.get(self.bosh_url + link + '/output',
        #                                  params={'type': 'query'},
        #                                  verify=self.verify_tls)
        # get blobstore ID from 'result' field
        download_url = "/resources/{}".format(logs_t_r.json()['result'])
        return download_url
