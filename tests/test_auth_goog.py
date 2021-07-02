import unittest

import json
import time
from unittest.mock import patch
from opcon.modules import auth


class App(object):
    config = dict()


def void_func(*args, **kwargs):
    pass


class TestConfig(unittest.TestCase):
    def setUp(self):
        app = App()
        app.config['USER_AUTH_TYPE'] = 'MOD'
        app.config['USER_AUTH_DEBUG'] = True
        app.config['USER_AUTH_MOD'] = 'auth_goog'
        app.config['USER_AUTH_DATA'] = 'client_id,client_secret,https://accounts.google.com,https://base_url'
        self.user_auth = auth.user_authentication(app)
        # overwrite flask_login hooks
        self.user_auth.flask_login_required = void_func
        self.user_auth.flask_logout_user = void_func
        self.user_auth.flask_current_user = void_func
        self.user_auth.flask_login_user = void_func
        self.fakey_token_file = 'tests/data/director_oauth.json'
        with open(self.fakey_token_file, 'r') as f:
            self.fakey_token = json.load(f)

    def test_auth_goog_config_type(self):
        self.assertEqual(self.user_auth.ua_lib.auth_type, 'oidc')

    def test_auth_goog_config_brand(self):
        self.assertEqual(self.user_auth.ua_lib.auth_brand, 'Google')

    @patch('opcon.modules.director.requests.get')
    def test_auth_goog_user_login(self, mock_get):
        fakey_code = 'fakey'
        user = self.user_auth.login_user(fakey_code, self.fakey_token)
        # we're using an old token, with an ancient expiration -- fudge it up
        self.user_auth.ua_lib.ug_hash[fakey_code] += int(time.time()) + 86400
        self.assertEqual(user.username, fakey_code.encode('utf-8'))
        user = self.user_auth.user_loader('fakeynotthere'.encode('utf-8'))
        self.assertEqual(user, None)
        # user = self.user_auth.user_loader(fakey_code)
        # self.assertEqual(user, fakey_code)
        user = self.user_auth.ua_lib.get_user_from_token(self.fakey_token['id_token'])
        self.assertEqual(user, 'admin')
