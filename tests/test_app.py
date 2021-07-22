
import unittest
import json
import requests
import uuid
import flask_unittest
import os
# from flask import Flask, request
from unittest.mock import patch
from opcon.modules import auth
from opcon.modules import config
from urllib.parse import quote


def void_func(*args, **kwargs):
    pass


class TestConfig(flask_unittest.ClientTestCase):
    os.environ["CONFIG_FILE"] = 'tests/data/test_config.ini'
    from opcon.app import app
    config = config.config(config_file='tests/data/test_config.ini')
    app.config['JSON_AS_ASCII'] = True
    app.config['SECRET_KEY'] = uuid.uuid4().hex
    app.config['USER_AUTH_TYPE'] = config.get('o_auth_type')
    app.config['USER_AUTH_DATA'] = config.get('o_auth_data')
    app.config['USER_AUTH_MOD'] = config.get('o_auth_mod')
    app.config['USER_AUTH_DEBUG'] = config.get('o_auth_debug')
    app.config['DEPLOYMENT_ACTOR'] = 'nobody'
    app.config['DEPLOYMENT_DATE'] = '00-00-00'
    app.config['DEPLOYMENT_GITHASH'] = '000000000'
    user_auth = auth.user_authentication(app)

    def setUp(self, client):
        pass

    def test_app_config(self, client):
        self.assertEqual(self.user_auth.ua_lib.auth_type, 'null')
        self.assertEqual(self.config['o_auth_type'], 'MOD')

    def test_app_deployment(self, client):
        r = client.get('/deployment')
        self.assertEqual(r.json['git_hash'], '000000000')
        self.assertEqual(r.json['deployment_date'], '00-00-00')
        self.assertEqual(r.json['deployment_actor'], 'nobody')
        # with self.app.test_request_context('/deployment'):
        #     self.assertEqual(request.path, '/deployment')
        #     self.assertEqual(request.method, 'GET')

    @patch('opcon.app.requests.post')
    def test_app_callback(self, client, mock_post):
        mock_post.return_value.status_code.return_value = 200
        with open('tests/data/director_oauth.json') as f:
            oauth_d = json.load(f)
        mock_post.return_value.json.return_value = oauth_d.copy()
        r = client.get('/_callback?code=0000', data={'code': '0000'})
        self.assertEqual(r.status_code, 401)  # we're not a OIDC auth
        self.app.config['AUTH'].ua_lib.auth_type = 'oidc'
        self.app.config['AUTH'].ua_lib.client_id = 'CLIENT_ID'
        self.app.config['AUTH'].ua_lib.client_secret = 'CLIENT_SECRET'
        r = client.get('/_callback?code=0000', data={'code': '0000'})
        self.assertEqual(r.status_code, 302)
        # self.assertEqual(r.headers['Location'], 'http://localhost/')

    def test_app_login(self, client):
        # mock_post.return_value.status_code.return_value = 200
        r = client.get('/login?next=' + quote('http://localhost'))
        # should get back a copy of "login_csv.html" - since "null" is not a recognized auth_type
        self.assertEqual(r.status_code, 200)
        # self.assertInResponse(r, 'Login')
        self.app.config['AUTH'].ua_lib.auth_type = 'userpass'
        r = client.post('/login', data={'username': 'username',
                                        'password': 'password',
                                        'next': 'http://127.0.0.1'})
        self.assertEqual(r.status_code, 302)  # redirect to index
        self.assertEqual(r.headers['Location'], 'http://localhost/None')

    def test_app_login_redirect(self, client):
        r = client.get('/login_redirect')
        self.assertEqual(r.status_code, 200)
        r = client.post('/login_redirect')
        self.assertEqual(r.status_code, 200)

