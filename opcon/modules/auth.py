from flask_login import LoginManager
import flask_login
from werkzeug.security import generate_password_hash, check_password_hash
import sys


class User(object):
    def __init__(self, name):
        self.is_authenticated = False
        self.is_active = False
        self.is_anonymous = True
        self.username = str(name).encode('unicode-escape')

    def get_id(self):
        return self.username

    def __repr__(self):
        return "[{} Anon:{} Active:{} Auth'd:{}]".format(self.username,
                                                         self.is_anonymous,
                                                         self.is_active,
                                                         self.is_authenticated)


class user_csv(object):
    def __init__(self, csvfile):
        self.uc_csvfile = csvfile
        self.uc_hash = dict()
        with open(self.uc_csvfile, 'r') as f:
            for line in f:
                user, phash = line.strip().split(',')
                if user in self.uc_hash:
                    print("User ({}) already exists".format(user))
                    sys.exit(1)
                self.uc_hash[user] = phash
                print("adding {}/{}".format(user, phash))
        return

    def user_auth(self, username, password):
        if username not in self.uc_hash:
            print("no user {} found".format(username))
            return False
        try:
            if check_password_hash(self.uc_hash[username], password):
                return True
        except TypeError as e:
            print("could not check hash {}".format(self.uc_hash[username]))
            print("Error {}".format(e))
        return False

    def user_loader(self, username):
        if username not in self.uc_hash:
            return False
        return self.uc_hash[username]


class user_authentication(object):
    def __init__(self, app):
        '''create user authentication object based on app.conf['USER_AUTH_TYPE']'''
        self.ua_type = app.config['USER_AUTH_TYPE']
        self.ua_login_manager = LoginManager()
        if self.ua_type == 'CSV':
            self.user_auth = user_csv(app.config['USER_AUTH_DATA'])
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
        if self.user_auth.user_auth(username, password):
            ok_user = User(username)
            ok_user.is_authenticated = True
            ok_user.is_anonymous = False
            ok_user.is_active = True
            print("User:", ok_user)
            self.flask_login_user(ok_user)
            return User(username)
        return None

    def user_loader(self, id):
        ok = User(id)
        ok.is_authenticated = True
        ok.is_active = True
        ok.is_anonymous = False
        return ok
