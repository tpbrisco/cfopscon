from flask_login import LoginManager
from werkzeug.security import generate_password_hash, check_password_hash


class user_csv(object):
    def __init__(self, csvfile):
        self.uc_csvfile = csvfile
        self.uc_hash = dict()
        self.csvfile = 'users.csv'
        self.ua_hash = dict()
        # load
        with open(self.csvfile, 'r') as f:
            line = f.readline()
            while line:
                print("line:",line)
                (user, phash) = line.split(',')
                print("caching user", user)
                self.ua_hash[user] = phash
                line = f.readline()
        return

    def verify_user(self, username, password):
        if username not in self.uc_hash:
            return False
        return check_password_hash(self.uc_hash[username], password)


class user_authentication(object):
    def __init__(self, app):
        '''create user authentication object based on app.conf['USER_AUTH_TYPE']'''
        self.ua_type = app.config['USER_AUTH_TYPE']
        self.ua_login = LoginManager()
        if self.ua_type == 'CSV':
            self.user_auth = user_csv('users.csv')

    def login_user(self, username, password):
        '''initiate user login'''
        return self.user_auth(username, password)
