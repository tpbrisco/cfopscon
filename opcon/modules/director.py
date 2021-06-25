import requests
import urllib3
import sys
from urllib.parse import urlparse
import time
import hashlib
import json

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
        self.t_time = int(time.time())

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

    def connect(self):
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

    def __p_hash(self, key):
        return hashlib.md5(key.encode('ascii')).hexdigest()

    def refresh_token(self):
        '''refresh_token: update authorization tokens'''
        if self.debug:
            print("refreshing token hash({})".format(self.__p_hash(self.oauth['access_token'])))
        r = self.session.post(
            self.uaa_url + '/oauth/token',
            data={'refresh_token': self.oauth['refresh_token'],
                  'grant_type': 'refresh_token',
                  'client_id': 'bosh_cli'},
            auth=('bosh_cli', ''),
            verify=self.verify_tls
            )
        if not r.ok:
            print(f"oauth refresh failed request({r.status_code}) {r.content}")
            self.init_auth(self.uaa_url, self.bosh_user, self.bosh_pass)
            return
        j = r.json()
        self.oauth = j.copy()
        if self.debug:
            print("new token hash({})".format(self.__p_hash(self.oauth['access_token'])))
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
            sys.exit(1)
        j = r.json()
        self.oauth = j.copy()
        # update auth headers in persisted session
        self.session.headers.update({'Authorization': j['token_type'] + ' ' + j['access_token']})

    def get_director_stats(self):
        '''get key statistics about the system'''
        stats = dict()
        for d in self.deployments:
            stats[d] = len(self.get_deployment_jobs(d))
        return stats

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
            return r
        else:
            return list()

    def get_deployment_jobs_filtered(self, deployment, filter):
        '''return a list of jobs from the deployment, filtered according to filter prefix'''
        jobs = self.get_deployment_jobs(deployment)
        filtered = list()
        for j in jobs:
            if j.startswith(filter):
                filtered.append(j)
        return filtered

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
        if self.debug:
            print("downloading logs from blobstore", download_url)
        return download_url

    def get_job_history(self, limit):
        '''get task histories'''
        if limit:
            params = {'limit': limit,
                      'state': 'queued,processing,cancelled,cancelling,done,error,timeout'}
        else:
            params = {}
        task_h_r = self.session.get(self.bosh_url + '/tasks',
                                    params=params,
                                    verify=self.verify_tls)
        if task_h_r.ok:
            return task_h_r.json()
        else:
            return {}

    def get_deployment_errands(self, deployment):
        '''get bosh errands for this deployment'''
        if deployment not in self.deployments:
            return None
        errands_url = '%s/deployments/%s/errands' % (
            self.bosh_url, deployment)
        if self.debug:
            print("fetching deployment errands", errands_url)
        errands_resp = self.session.get(errands_url,
                                        verify=self.verify_tls)
        if not errands_resp.ok:
            print("Error {} fetching {} errands: {}".format(
                errands_resp.status_code,
                deployment,
                errands_resp.text))
            return None
        errand_dict = errands_resp.json()
        errand_ary = list()
        for e in errand_dict:
            errand_ary.append(e['name'])
        return errand_ary

    def run_deployment_errand(self, deployment, errand_name):
        '''run indicated errand for this deployment'''
        if deployment not in self.deployments:
            return None
        errand_url = '{}/deployments/{}/errands/{}/runs'.format(
            self.bosh_url,
            deployment,
            errand_name)
        # very awkward to get the data in the format acceptable by the bosh api
        errand_resp = self.session.post(errand_url,
                                        verify=self.verify_tls,
                                        allow_redirects=False,
                                        headers={'Content-Type': 'application/json'},
                                        data='{"instances": [], "keep-alive": false, "when-changed": false}')
        if not errand_resp.status_code == 302:
            print("error calling errand {} for {}: {}".format(
                errand_name, deployment, errand_resp.text))
            return False
        # we should have the URL to follow for this
        errand_results_url = urlparse(errand_resp.headers['Location']).path
        if self.debug:
            print("errand talk:", errand_results_url)
        # this doesn't seem to actually leave output cleanly
        # self.pending_tasks.append(task_logs(TASK_LOGS,
        #                                     "%s %s" % (deployment, errand_name),
        #                                     errand_results_url))
        return True

    def get_deployment_vitals(self, deployment):
        '''get bosh vms --vitals'''
        if deployment not in self.deployments:
            return None
        # deployments/<deployment>/instances?format=full
        vitals_url = '%s/deployments/%s/instances' % (
            self.bosh_url, deployment)
        if self.debug:
            print("submit for instance vitals", vitals_url)
        vitals_resp = self.session.get(vitals_url, params={'format': 'full'},
                                       allow_redirects=False,
                                       verify=self.verify_tls)
        if not vitals_resp.status_code == 302:
            print("error calling bosh:", vitals_resp.content)
            return None
        vitals_task_url = urlparse(vitals_resp.headers['Location']).path
        if self.debug:
            print("vitals task:", vitals_task_url)
        vitals_t_r = self.session.get(self.bosh_url + vitals_task_url,
                                      verify=self.verify_tls)
        task_state = vitals_t_r.json()['state']
        while task_state != 'done':
            # should "flash" a message here
            if self.debug:
                print("vitals state: sleep until job ready")
            time.sleep(1)
            vitals_t_r = self.session.get(self.bosh_url + vitals_task_url,
                                          verify=self.verify_tls)
            task_state = vitals_t_r.json()['state']
        if self.debug:
            print("vitals state: job is ready")
        # get output from task -- this is tricky
        # the output from the task is a series of json-as-text strings (one
        # object per line),  so read that, convert it into dictionary, and
        # append that to a list we can then take that list-of-dicts and return
        # it as a reasonable answer.
        # All this instead of a response.json() call - because it's not json...
        if self.debug:
            print("vitals output", self.bosh_url + vitals_task_url + '/output')
        vitals_t_r = self.session.get(self.bosh_url + vitals_task_url + '/output',
                                      params={'type': 'result'},
                                      verify=self.verify_tls)
        my_data = vitals_t_r.content.decode('ascii')  # convert \n to newline
        ary_vms = list()
        for i in my_data.splitlines():
            ary_vms.append(json.loads(i))
        if self.debug:
            print("received data dumped to /tmp/response.json")
            with open('/tmp/response.json', 'w') as f:
                f.write(json.dumps(ary_vms))
        return ary_vms
