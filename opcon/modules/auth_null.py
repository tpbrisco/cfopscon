import time


class UserAuth(object):
    def __init__(self, appopt):
        self.auth_type = 'null'
        self.auth_brand = 'Null and/or Void'
        self.un_hash = dict()
        self.un_hash['username'] = int(time.time()) + 86400
        return

    def user_auth(self, username, password):
        if username == 'username' and password == 'password':
            return True
        else:
            return False

    def user_loader(self, username):
        if username not in self.un_hash:
            return None
        if self.un_hash[username] >= int(time.time()):
            return username
        return None
