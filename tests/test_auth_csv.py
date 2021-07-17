import unittest

from opcon.modules import auth


class App(object):
    config = dict()


def void_func(*args, **kwargs):
    pass


class TestConfig(unittest.TestCase):
    def setUp(self):
        app = App()
        app.config['USER_AUTH_TYPE'] = 'MOD'
        app.config['USER_AUTH_DEBUG'] = False
        app.config['USER_AUTH_MOD'] = 'auth_csv'
        app.config['USER_AUTH_DATA'] = 'tests/data/fake-users.csv'
        self.user_auth = auth.user_authentication(app)
        # overwrite flask_login hooks
        self.user_auth.flask_login_required = void_func
        self.user_auth.flask_logout_user = void_func
        self.user_auth.flask_current_user = void_func
        self.user_auth.flask_login_user = void_func

    def test_auth_csv_config_type(self):
        self.assertEqual(self.user_auth.ua_lib.auth_type, 'userpass')

    def test_auth_csv_config_brand(self):
        self.assertEqual(self.user_auth.ua_lib.auth_brand, 'CSV, FTW')

    def test_auth_csv_user_login(self):
        user = self.user_auth.login_user('fake', 'foofoo')
        self.assertEqual(user.username.decode('utf-8'), 'fake')
        user = self.user_auth.login_user('fake', 'foofoofram')
        self.assertEqual(user, None)
        user = self.user_auth.login_user('fakenotthere', 'foofoo')
        self.assertEqual(user, None)

    def test_auth_csv_user_loader(self):
        user = self.user_auth.login_user('fake', 'foofoo')
        user = self.user_auth.user_loader(b'fake')
        self.assertEqual(user.username, b'fake')
        user = self.user_auth.user_loader(b'fakenotthere')
        self.assertEqual(user, None)
