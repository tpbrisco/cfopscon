import time


class UserAuth(object):
    def __init__(self, appopt):
        self.auth_type = 'null'
        self.auth_brand = 'Null and/or Void'
        self.un_hash = dict()
        self.un_hash['username'] = int(time.time()) + 86400
        self.code_request_uri = 'http://127.0.0.1'
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

    def prepare_token_request(self, code):
        if code == '0000':
            return '/mock', {}, {}

    def get_user_from_token(self, id_d):
        return 'nobody'
