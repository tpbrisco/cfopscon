from werkzeug.security import generate_password_hash, check_password_hash
import sys
import time


# UserAuth must be defined for loadable modules to work
# Methods:
# - init("option,option,option") - comma-delimited string for parameters
# - user_auth(username, password) - potentially dummy method
# - user_loader(username) - locate user if known
class UserAuth(object):
    def __init__(self, appopt):
        self.uc_csvfile = appopt.config['USER_AUTH_DATA']
        self.uc_debug = appopt.config['USER_AUTH_DEBUG']
        self.uc_hash = dict()
        self.auth_type = 'userpass'  # for app.py:login() method
        self.auth_brand = 'CSV, FTW'  # branding info
        with open(self.uc_csvfile, 'r') as f:
            for line in f:
                try:
                    user, phash = line.strip().split(',')
                except ValueError as e:
                    print("error {} on line:\"{}\"".format(e, line))
                    continue
                if user in self.uc_hash:
                    print("User ({}) already exists".format(user))
                    continue
                self.uc_hash[user] = {"time": 0, "hash": phash}
                if self.uc_debug:
                    print("adding {}/{}".format(user, phash))
        return

    def user_auth(self, username, password):
        if self.uc_debug:
            print("user_auth(user={}, pass)".format(username))
        username = str(username)
        if username not in self.uc_hash:
            print("no user {} found".format(username))
            return False
        try:
            if check_password_hash(self.uc_hash[username]['hash'], password):
                self.uc_hash[username]['time'] = time.time() + 3600
                return True
        except TypeError as e:
            print("could not check hash {}".format(self.uc_hash[username]['hash']))
            print("Error {}".format(e))
        return False

    def user_loader(self, username):
        # username = username.decode('utf-8')
        if self.uc_debug:
            print("user_loader(user={})".format(username))
        if username not in self.uc_hash:
            if self.uc_debug:
                print("user_loader() returns None")
            return None
        if self.uc_hash[username]['time'] >= time.time():
            return username
        return None
