import flask_login
import sys
import random
import importlib

class User(object):
    def __init__(self, name):
        self.is_authenticated = False
        self.is_active = False
        self.is_anonymous = True
        self.username = str(name).encode('unicode-escape')

    def get_id(self):
        return self.username

    def __repr__(self):
        return "[{} Anon:{} Active:{} Auth'd:{}]".format(self.username.decode("utf-8"),
                                                         self.is_anonymous,
                                                         self.is_active,
                                                         self.is_authenticated)


class user_uaa(object):
    def __init__(self, configstr):
        (self.client_id,
         self.client_secret,
         self.client_username,
         self.client_password,
         self.uaa_url,
         self.uaa_redirect) = configstr.split(',')
        print("user_uaa configstr", configstr)
        self.flask_login_requred = flask_login.login_required
        self.flask_logout_user = flask_login.logout_user
        self.flask_current_user = flask_login.current_user
        self.flask_login_user = flask_login.login_user
        self.uaa_url = 'http://' + self.uaa_url
        # redirect URL
        r = random.randint(0, 9999)
        state_no = "{:05d}".format(r)
        self.auth_url = self.uaa_url + \
            '/oauth/authorize?response_type=code&state=' + state_no + \
            '&client_id=login&redirect_uri=' + \
            'http://' + self.uaa_redirect + '&scope=openid'

    def logout_user(self):
        self.flask_logout_user()

    def login_user(self, username, password):
        '''initiate user login'''
        if self.ua_lib.user_auth(username, password):
            ok_user = User(username)
            ok_user.is_authenticated = True
            ok_user.is_anonymous =True
            ok_user.is_active = True
            print("User: {} logged in".format(ok_user))
            return ok_user
        return None

    def user_loader(self, id):
        ok = User(id)
        ok.is_authenticated = True
        ok.is_active = True
        ok.is_anonymous = False
        return ok


class user_authentication(object):
    def __init__(self, app):
        '''create user authentication object based on app.conf['USER_AUTH_TYPE']'''
        self.ua_type = app.config['USER_AUTH_TYPE']
        self.ua_login_manager = flask_login.LoginManager()
        if self.ua_type == 'MOD':
            mod_file = app.config['USER_AUTH_MOD']
            print("Loading module '{}'".format(app.config['USER_AUTH_MOD']), file=sys.stdout)
            try:
               modlib = importlib.import_module('opcon.modules.' + mod_file,
                                       package='UserAuth')
            except Exception as e:
                print("Issues loading {}: {}".format(mod_file, e),
                      file=sys.stderr)
                sys.exit(1)
            # loadable modules have UserAuth object defined
            print("Module {} loaded".format(app.config['USER_AUTH_MOD']))
            self.ua_lib = modlib.UserAuth(app.config['USER_AUTH_DATA'])
        elif self.ua_type == 'UAA':
            self.ua_lib = user_uaa(app.config['USER_AUTH_DATA'])
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

    def login_user(self, username, password):
        '''initiate user login'''
        if self.ua_lib.auth_type == 'oidc':
            ok_user = User(username)
            ok_user.is_authenticated = True
            ok_user.is_anonymous  = False
            ok_user.is_active = True
            print("User:{} logged in".format(ok_user))
            self.flask_login_user(ok_user)
            return ok_user
        if self.ua_lib.user_auth(username, password):
            ok_user = User(username)
            ok_user.is_authenticated = True
            ok_user.is_anonymous = False
            ok_user.is_active = True
            print("User: {} logged in".format(ok_user))
            self.flask_login_user(ok_user)
            return ok_user
        return None

    def user_loader(self, id):
        username = self.ua_lib.user_loader(id)
        ok_user = User(username)
        ok_user.is_authenticated = True
        ok_user.is_anonymous = False
        ok_user.is_active = True
        return ok_user
