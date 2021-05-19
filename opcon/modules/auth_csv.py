from werkzeug.security import generate_password_hash, check_password_hash
import sys

# UserAuth must be defined for loadable modules to work
# Methods:
# - init("option,option,option") - takes a comma-delimited string for parameters
# - user_auth(username, password) - potentially dummy method
# - user_loader(username) - locate user if known
class UserAuth(object):
    def __init__(self, csvfile):
        self.uc_csvfile = csvfile
        self.uc_hash = dict()
        self.auth_type = 'userpass'  # for app.py:login() method
        self.auth_brand = 'CSV, FTW' # branding info
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
        print("user_auth(user={}, pass)".format(username))
        username =str(username)
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
        username =username.decode('utf-8')
        print("user_loader(user={})".format(username))
        if username not in self.uc_hash:
            print("user_loader() returns None")
            return None
        return username
