import flask_unittest
import unittest
from flask import Flask
from opcon.bosh.bosh_bp import bosh_bp
from opcon.modules import auth


def void_func(*args, **kwargs):
    pass


def login_always(*args, **kwargs):
    return True


class director(object):
    def __init__(self):
        self.deployments = []


def app_create_app():
    app = Flask('opcon')
    app.config['DIRECTOR'] = director()
    app.config['USER_AUTH_TYPE'] = 'MOD'
    app.config['USER_AUTH_DEBUG'] = True
    app.config['USER_AUTH_MOD'] = 'auth_null'
    app.config['USER_AUTH_DATA'] = ''
    app.config['DEBUG'] = True

    # set up null authentication
    user_auth = auth.user_authentication(app)
    user_auth.ua_login_manager.init_app(app)
    user_auth.ua_login_manager.login_view = 'login'
    user_auth.ua_login_manager.user_loader(user_auth.user_loader)
    app.config['USER_AUTH'] = user_auth

    # set up application basics
    app.config['SECRET_KEY'] = 'averylongstringindeed'
    app.config['JSON_AS_ASCII'] = True
    app.add_url_rule('/login', 'login', login_always)

    # load modules for test
    app.register_blueprint(bosh_bp, url_prefix='/bosh')

    # log in null user
    with app.app_context():
        user_auth.login_user('username', 'password')
    return app


class TestConfig(flask_unittest.AppTestCase):
    def create_app(self):
        return app_create_app()

    def setUp(self, app):
        pass

    def test_bosh_bp_bosh_logs(self, app):
        # note trailing slash to exactly match route
        app.config['USER_AUTH'].login_user('username', 'password')
        with app.test_client() as client:
            rv = client.get('/bosh')
            print("RV code {} is and {}".format(rv.status_code, rv))
            # should be permanent redirect
            self.assertEqual(rv.status_code, 308)

    def test_bosh_bp_get_tasks(self, app):
        with app.test_client() as client:
            rv = client.get('/bosh/tasks')
            print("RV code {} is and {}".format(rv.status_code, rv))
            # should be redirect to task job
            self.assertEqual(rv.status_code, 302)

    def test_bosh_bp_download_logs(self, app):
        with app.test_client() as client:
            rv = client.get('/bosh/tasks/42')
            print("RV code {} and {}".format(rv.status_code, rv))
            # redirect to blobstore URL
            self.assertEqual(rv.status_code, 302)

    def test_bosh_bp_get_task_output(self, app):
        with app.test_client() as client:
            rv = client.get('/bosh/tasks/42/output')
            print("RV code {} and {}".format(rv.status_code, rv))
            self.assertEqual(rv.status_code, 302)

    def test_bosh_bp_cancel_task(self, app):
        with app.test_client() as client:
            rv = client.get('/bosh/tasks/42/cancel')
            print("RV code {} and {}".format(rv.status_code, rv))
            self.assertEqual(rv.status_code, 302)

    def test_bosh_bp_get_deployment_errands(self, app):
        with app.test_client() as client:
            rv = client.get('/bosh/deployment/errands')
            print("RV code {} and {}".format(rv.status_code, rv))
            self.assertEqual(rv.status_code, 302)

    def test_bosh_bp_run_deployment_errands(self, app):
        with app.test_client() as client:
            rv = client.get('/bosh/deployment/cf/errand/smoke_test/run')
            print("RV code {} and {}".format(rv.status_code, rv))
            self.assertEqual(rv.status_code, 302)
