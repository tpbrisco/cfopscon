import flask_login
import sys
import random
import importlib
import datetime


class User(object):
    def __init__(self, name):
        self.is_authenticated = False
        self.is_active = False
        self.is_anonymous = True
        self.username = str(name).encode('unicode-escape')
        self.debug = False

    def get_id(self):
        return self.username

    def __repr__(self):
        return "[{} Anon:{} Active:{} Auth'd:{}]".format(self.username.decode("utf-8"),
                                                         self.is_anonymous,
                                                         self.is_active,
                                                         self.is_authenticated)


class user_authentication(object):
    def __init__(self, app):
        '''create user authentication object based on app.conf['USER_AUTH_*']'''
        self.ua_type = app.config['USER_AUTH_TYPE']
        self.ua_login_manager = flask_login.LoginManager()
        self.debug = app.config['USER_AUTH_DEBUG']
        if self.ua_type == 'MOD':
            mod_file = app.config['USER_AUTH_MOD']
            if self.debug:
                print("Loading module '{}'".format(
                    app.config['USER_AUTH_MOD']), file=sys.stdout)
            try:
                modlib = importlib.import_module('opcon.modules.' + mod_file,
                                                 package='UserAuth')
            except Exception as e:
                print("Issues loading {}: {}".format(mod_file, e),
                      file=sys.stderr)
                sys.exit(1)
            # loadable modules have UserAuth object defined
            if self.debug:
                print("Module {} loaded".format(app.config['USER_AUTH_MOD']))
            self.ua_lib = modlib.UserAuth(app)
        else:
            # handle "no authentication type defined"
            sys.stderr.write("No valid authentication scheme selected\n")
            sys.exit(1)
        self.flask_login_required = flask_login.login_required
        self.flask_logout_user = flask_login.logout_user
        self.flask_current_user = flask_login.current_user
        self.flask_login_user = flask_login.login_user

    def logout_user(self):
        self.flask_logout_user()

    def login_user(self, username, param):
        '''initiate user login'''
        if self.ua_lib.auth_type == 'oidc':
            if self.ua_lib.user_auth(username, param):
                ok_user = User(username)
                ok_user.is_authenticated = True
                ok_user.is_anonymous = False
                ok_user.is_active = True
                ok_user.debug = self.debug
                if self.debug:
                    print("User:{} logged in".format(ok_user))
                self.flask_login_user(ok_user,
                                    duration=datetime.timedelta(hours=1))
                return ok_user
            return None
        if self.ua_lib.auth_type == 'userpass':
            if self.ua_lib.user_auth(username, param):
                ok_user = User(username)
                ok_user.is_authenticated = True
                ok_user.is_anonymous = False
                ok_user.is_active = True
                ok_user.debug = self.debug
                if self.debug:
                    print("User: {} logged in".format(ok_user))
                self.flask_login_user(ok_user,
                                      duration=datetime.timedelta(hours=1))
                return ok_user
            return None
        return None

    def user_loader(self, id):
        username = self.ua_lib.user_loader(id)
        if username is None:
            return None
        ok_user = User(username)
        ok_user.is_authenticated = True
        ok_user.is_anonymous = False
        ok_user.is_active = True
        ok_user.debug = self.debug
        return ok_user
