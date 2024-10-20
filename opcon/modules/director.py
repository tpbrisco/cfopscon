import requests
import urllib3
import sys
from urllib.parse import urlparse
import time
import hashlib
import json
import re

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
        self.testing = False
        self.verify_tls = True
        self.errands_acls = None
        self.readonly = False
        if 'testing' in kwargs:
            self.testing = kwargs['testing']
        if 'debug' in kwargs:
            self.debug = kwargs['debug']
        if 'verify_tls' in kwargs:
            self.verify_tls = kwargs['verify_tls']
            if self.verify_tls is False:
                urllib3.disable_warnings()
        if 'readonly' in kwargs:
            self.readonly = kwargs['readonly']
        if 'errands' in kwargs:
            self.errands_acls = kwargs['errands']
        self.bosh_url = url
        self.bosh_user = user
        self.bosh_pass = password
        self.uaa_url = ''
        self.pending_tasks = list()

    def connect(self):
        # get BOSH session initialization info
        try:
            init_r = requests.get(self.bosh_url + "/info",
                                  verify=self.verify_tls)
        except (requests.exceptions.ConnectionError,
                requests.exceptions.HTTPError,
                requests.exceptions.SSLError,
                requests.exceptions.Timeout) as e:
            print("Error getting bosh /info {}: {}".format(self.bosh_url + "/info", e), file=sys.stderr)
            return False
        if not init_r.ok:
            print("error initializing", self.bosh_url)
            self.uaa_url = 'http://127.0.0.1'
            return False
        init_json = init_r.json()
        # cache key URLs
        self.uaa_url = init_json['user_authentication']['options']['url']
        # set up internal cached data structures
        return True

    def login(self):
        self.init_auth(self.uaa_url, self.bosh_user, self.bosh_pass)

    def oauth_token_expires(self):
        '''oauth_token_expires() - return number of seconds until current key expires'''
        if self.testing:
            return 86400
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
            print(f"director oauth refresh failed request({r.status_code}) {r.content}")
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
            print(f"director login: oauth request({r.status_code}) {r.content}")
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
        if self.testing:
            return ['cf', 'zookeeper']
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
            self.deployments = list()

    def add_job_wildcards(self, jobs):
        '''Enrich the list of deployment jobs with wildcards'''
        # a list like
        #   api/<guid1>
        #   diego_cell/<guid2>
        #   diego_cell/<guid3>
        # becomes
        #   api/<guid1>
        #   diego_cell/*
        #   diego_cell/<guid2>
        #   diego_cell/<guid3>
        #
        job_groups = dict()
        for j in jobs:
            group = j.split('/')[0]
            if group not in job_groups:
                job_groups[group] = list()
            job_groups[group].append(j)
        # should have a full dictionary of the job groups now, with jobs listed in it
        r_jobs = list()
        for g in sorted(job_groups.keys()):  # maintain sorting
            if len(job_groups[g]) > 1:
                r_jobs.append(g + "/*")
            r_jobs.extend(job_groups[g])
        return r_jobs

    def get_deployment_jobs(self, deployment, groups=False):
        '''return a list of jobs associated with this deployment'''
        j_r = self.session.get(self.bosh_url + "/deployments/" + deployment + "/vms",
                               params={
                                   'exclude_configs': True,
                                   'exclude_releases': True,
                                   'exclude_stemcells': True},
                               verify=self.verify_tls)
        if j_r.ok:
            r = list()
            for j in sorted(j_r.json(), key=lambda k: k['job']):
                r.append("{}/{}".format(j['job'], j['id']))
            if groups:
                r = self.add_job_wildcards(r)
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
        logs_t_r = self.task_wait_ready(link)
        # get blobstore ID from 'result' field
        download_url = "/resources/{}".format(logs_t_r.json()['result'])
        if self.debug:
            print("downloading logs from blobstore", download_url)
        return download_url

    def get_job_history(self, limit):
        '''get task histories'''
        params = {'verbose': '1'}
        if limit:
            params['limit'] = limit
        task_h_r = self.session.get(self.bosh_url + '/tasks',
                                    params=params,
                                    verify=self.verify_tls)
        if task_h_r.ok:
            return task_h_r.json()
        else:
            return {}

    def __filter_errands(self, deployment, errand_list):
        '''filter_errands(deployment_name, list of errands) - return allowed errands'''
        def deployment_errands_acl(deployment):
            for key in self.errands_acls.keys():
                if deployment.startswith(key):
                    return self.errands_acls[key]
            if '*' in self.errands_acls.keys():
                # "wildcard" default if no explict prefix match
                return self.errands_acls['*']
            return None
        # find allow list in self
        if self.errands_acls is None:
            # allow all if no allow-lists are specified
            return errand_list
        # for this deployment, look at our allow-lists, and return the relevant one
        errands_allowed = deployment_errands_acl(deployment)
        if errands_allowed is None:
            # allow all if no allow-lists specified for this deployment
            return errand_list
        valid_errands = list()
        if 'allow' not in errands_allowed:
            # if no "allow" section exists, nothing is allowed
            return valid_errands
        for k in errand_list:
            for allowed_errand_re in errands_allowed['allow']:
                if re.match(allowed_errand_re, k):
                    valid_errands.append(k)
        return valid_errands

    def get_deployment_errands(self, deployment):
        '''get bosh errands for this deployment'''
        if deployment not in self.deployments:
            return None
        errands_url = '%s/deployments/%s/errands' % (
            self.bosh_url, deployment)
        if self.debug:
            print("fetching deployment errands from", errands_url)
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
        # convert dictionary of names into simple list
        for e in errand_dict:
            errand_ary.append(e['name'])
        if self.debug:
            print("Got errands: {}".format(errand_ary))
        errand_ary = self.__filter_errands(deployment, errand_ary)
        if self.debug:
            print("Allowed errands: {}".format(errand_ary))
        return errand_ary

    def run_deployment_errand(self, deployment, errand_name):
        '''run indicated errand for this deployment'''
        if deployment not in self.deployments:
            return False, ''
        allowed_errands = self.__filter_errands(deployment, [errand_name])
        if self.debug:
            print("allowed errands:", allowed_errands)
        if errand_name not in allowed_errands:
            return False, ''
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
            return False, ''
        # we should have the URL to follow for this
        errand_results_url = urlparse(errand_resp.headers['Location']).path
        if self.debug:
            print("errand task:", errand_results_url)
            print("errand status", errand_resp.status_code, "content:", errand_resp.content)
        # this doesn't seem to actually leave output cleanly
        # self.pending_tasks.append(task_logs(TASK_LOGS,
        #                                     "%s %s" % (deployment, errand_name),
        #                                     errand_results_url))
        return True, errand_results_url

    def get_deployment_vitals_submit_task(self, deployment):
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
        return vitals_task_url

    def get_deployment_vitals_task_output(self, task_url):
        # this is unnecessarily tricky -
        # the output from the task is a series of json-as-text strings (one
        # object per line),  so read that, convert it into dictionary, and
        # append that to a list we can then take that list-of-dicts and return
        # it as a reasonable answer.
        # All this instead of a response.json() call - because it's not json...
        if self.debug:
            print("vitals output", self.bosh_url + task_url + '/output')
        task_r = self.session.get(self.bosh_url + task_url + '/output',
                                  params={'type': 'result'},
                                  verify=self.verify_tls)
        my_data = task_r.content.decode('ascii')  # convert \n to newline
        ary_vms = list()
        for i in my_data.splitlines():
            ary_vms.append(json.loads(i))
            if self.debug:
                print("received data dumped to /tmp/response.json")
            with open('/tmp/response.json', 'w') as f:
                f.write(json.dumps(ary_vms))
        return ary_vms

    def task_wait_ready(self, task_url):
        task_r = self.session.get(self.bosh_url + task_url,
                                  verify=self.verify_tls)
        task_state = task_r.json()['state']
        while task_state != 'done':
            # should "flash" a message here
            if self.debug:
                print("task state: sleep until job ready")
            time.sleep(1)
            task_r = self.session.get(self.bosh_url + task_url,
                                      verify=self.verify_tls)
            task_state = task_r.json()['state']
        return task_r

    def get_deployment_vitals(self, deployment):
        '''get bosh vms --vitals'''
        vitals_task_url = self.get_deployment_vitals_submit_task(deployment)
        task_w_r = self.task_wait_ready(vitals_task_url)
        if self.debug:
            print("vitals state: job is \"{}\"".format(task_w_r.json()['state']))
        # get output from task -- this is tricky
        ary_vms = self.get_deployment_vitals_task_output(vitals_task_url)
        return ary_vms
