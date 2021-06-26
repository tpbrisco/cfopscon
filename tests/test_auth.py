import unittest
from opcon.modules import auth


class App(object):
    config = dict()


class TestConfig(unittest.TestCase):
    def setUp(self):
        app = App()
        app.config['USER_AUTH_TYPE'] = 'MOD'
        app.config['USER_AUTH_DEBUG'] = False
        app.config['USER_AUTH_MOD'] = 'auth_null'
        app.config['USER_AUTH_DATA'] = ''
        self.user_auth = auth.user_authentication(app)

    def test_auth_config_type(self):
        self.assertEqual(self.user_auth.ua_lib.auth_type, 'null')

    def test_auth_config_brand(self):
        self.assertEqual(self.user_auth.ua_lib.auth_brand, 'Null and/or Void')

    def test_auth_user_login(self):
        succeed = self.user_auth.login_user('username', 'password')
        not_succeed = self.user_auth.login_user('username', 'notpassword')
        self.assertNotEqual(succeed, True)
        self.assertEqual(not_succeed, None)

    def test_auth_user_loader(self):
        self.assertNotEqual(None, self.user_auth.user_loader("username"))
        self.assertEqual(None, self.user_auth.user_loader("doesnotwork"))
