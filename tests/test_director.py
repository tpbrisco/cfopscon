import unittest
import json
import requests
from unittest.mock import patch
from opcon.modules import director


class TestDirector(unittest.TestCase):
    def setUp(self):
        # set up mocking for this director, in kind of a ugly way
        self.director = director.Director('https://192.168.0.0:25555',
                                          'admin',
                                          'nothing',
                                          debug=False,
                                          verify_tls=False)
        # set mock values
        self.director.deployments = ['cf', 'zookeeper']
        self.director.session = requests.Session()
        self.director.pending_tasks = list()
        self.director.uaa_url = 'https://192.168.0.0:8443'

    def test_director(self):
        self.assertNotEqual(self.director, None)

    @patch('opcon.modules.director.requests.get')
    def test_director_connect(self, mock_get):
        mock_get.return_value.status_code.return_value = 200
        with open('tests/data/director_info.json') as f:
            info_d = json.load(f)
        mock_get.return_value.json.return_value = info_d
        success = self.director.connect()
        self.assertEqual(self.director.uaa_url, 'https://192.168.50.6:8443')
        self.assertEqual(success, True)

        mock_get.return_value.status_code = 404
        mock_get.return_value.ok = False
        success = self.director.connect()
        self.assertEqual(success, False)

    @patch('opcon.modules.director.requests.Session.post')
    def test_director_init_auth(self, mock_post):
        mock_post.return_value.status_code.return_value = 200
        with open('tests/data/director_oauth.json') as f:
            oauth_d = json.load(f)
        mock_post.return_value.json.return_value = oauth_d.copy()
        self.director.init_auth('https://192.168.50.6:8443', 'admin', 'nothing')
        self.assertEqual(self.director.oauth['expires_in'], 119)

        self.director.login()
        self.assertEqual(self.director.oauth['expires_in'], 119)

        mock_post.return_value.json.return_value['expires_in'] = 120
        self.director.refresh_token()
        self.assertEqual(self.director.oauth['expires_in'], 120)

    @patch('opcon.modules.director.requests.Session.get')
    def test_director_deployments(self, mock_get):
        mock_get.return_value.status_code.return_value = 200
        mock_get.return_value.json.return_value = [{"name": "cf"},{"name": "zookeeper"}]
        self.director.get_deployments()
        self.assertEqual(len(self.director.deployments), 2)

        mock_get.return_value.status_code.return_value = 400
        mock_get.return_value.ok = False
        self.director.get_deployments()
        self.assertEqual(len(self.director.deployments), 0)

    @patch('opcon.modules.director.requests.Session.get')
    def test_director_deployment_jobs(self, mock_get):
        mock_get.return_value.status_code.return_value = 200
        mock_get.return_value.json.return_value = [
            {'job': 'router', 'id': 0}, {'job': 'uaa', 'id': 0}]
        jobs = self.director.get_deployment_jobs('cf')
        self.assertEqual(len(jobs), 2)

        stats = self.director.get_director_stats()
        self.assertEqual(len(stats), 2)

    @patch('opcon.modules.director.requests.Session.get')
    def test_director_deployment_jobs_filtered(self, mock_get):
        mock_get.return_value.status_code.return_value = 200
        mock_get.return_value.json.return_value = [
            {'job': 'router', 'id': 0}, {'job': 'uaa', 'id': 0}]
        jobs = self.director.get_deployment_jobs_filtered('cf', 'rout')
        self.assertEqual(len(jobs), 1)

    @patch('opcon.modules.director.requests.Session.get')
    def test_director_submit_logs_job(self, mock_get):
        mock_get.return_value.status_code = 302
        mock_get.return_value.headers = dict()
        mock_get.return_value.headers['Location'] = 'https://192.168.50.6:25555/tasks/111'
        # generates side effect of "task/111" is put on task queue
        r = self.director.submit_logs_job('cf', 'doppler/0')
        self.assertEqual(len(self.director.pending_tasks), 1)
        self.assertEqual(r, True)

        mock_get.return_value.status_code = 400
        r = self.director.submit_logs_job('cf', 'doppler/0')
        self.assertEqual(r, False)

    @patch('opcon.modules.director.requests.Session.get')
    def test_director_get_logs_job(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {'state': 'done', 'result': 'foofram'}
        download_url = self.director.get_logs_job('/task/111')
        self.assertEqual('/resources/foofram', download_url)

    @patch('opcon.modules.director.requests.Session.get')
    def test_director_get_job_history(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = [
            {'id': 63, 'description': 'snapshot'},
            {'id': 62, 'description': 'snapshot'}]
        jreturn = self.director.get_job_history(limit=4)
        self.assertEqual(len(jreturn), 2)

        mock_get.return_value.ok = False
        jreturn = self.director.get_job_history(limit=4)
        self.assertEqual(len(jreturn), 0)

    @patch('opcon.modules.director.requests.Session.get')
    def test_director_get_deployment_errands(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = [
            {'name': 'smoke-tests'}, {'name': 'rotate-database'}]
        jreturn = self.director.get_deployment_errands('cf')
        self.assertEqual(len(jreturn), 2)

        jreturn = self.director.get_deployment_errands('notthere')
        self.assertEqual(jreturn, None)

        mock_get.return_value.ok = False
        mock_get.return_value.status_code = 400
        jreturn = self.director.get_deployment_errands('cf')
        self.assertEqual(jreturn, None)

    @patch('opcon.modules.director.requests.Session.post')
    def test_director_run_deployment_errand(self, mock_post):
        mock_post.return_value.status_code = 302
        mock_post.return_value.headers = dict()
        mock_post.return_value.headers['Location'] = 'https://192.168.50.6:25555/tasks/111'
        success = self.director.run_deployment_errand('cf', 'smoke-tests')
        self.assertEqual(success, True)

        success = self.director.run_deployment_errand('notthere', 'smoke-tests')
        self.assertEqual(success, False)

        mock_post.return_value.status_code = 400
        success = self.director.run_deployment_errand('cf', 'smoke-tests')
        self.assertEqual(success, False)

    @patch('opcon.modules.director.requests.Session.get')
    def test_director_get_deployment_vitals_submit(self, mock_get):
        mock_get.return_value.status_code = 302
        mock_get.return_value.headers = dict()
        mock_get.return_value.headers['Location'] = 'https://192.168.50.6:25555/tasks/111'
        mock_get.return_value.json.return_value = {'state': 'done'}
        task_url = self.director.get_deployment_vitals_submit_task('cf')
        self.assertEqual(task_url, '/tasks/111')

        task_url = self.director.get_deployment_vitals_submit_task('notthere')
        self.assertEqual(task_url, None)

        mock_get.return_value.status_code = 400
        task_url = self.director.get_deployment_vitals_submit_task('cf')
        self.assertEqual(task_url, None)

    @patch('opcon.modules.director.requests.Session.get')
    def test_director_get_deployment_vitals_output(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.content = "\"{'agent_id': '9999-999-9999', 'job': 'router', 'cid': '888-888-face', 'state': 'running'}\"\n\"{'agent_id': '9999-999-9998', 'job': 'uaa', 'id': '888-dea-dbee', 'state': 'running'}\"".encode('utf-8')
        vitals_j = self.director.get_deployment_vitals_task_output('/task/111')
        self.assertEqual(len(vitals_j), 2)

    def test_director_oauth_expires(self):
        self.director.oauth = {'expires_in': 84600}
        self.assertEqual(84600, self.director.oauth_token_expires())


if __name__ == '__main__':
    unittest.main()
