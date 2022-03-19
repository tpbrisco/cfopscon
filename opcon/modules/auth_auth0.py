from flask import (
    Flask,
    redirect, request,
    url_for)
import requests
import base64
import json
import sys
import time
import jwt
from cryptography import x509
from cryptography.hazmat.backends import default_backend


class UserAuth(object):
    def __init__(self, appopt):
        # CLIENT_ID, CLIENT_SECRET
        (self.client_id,
         self.client_secret,
         self.oidc_url,
         self.base_url) = appopt.config['USER_AUTH_DATA'].split(',')
        self.debug = appopt.config['USER_AUTH_DEBUG']
        self.auth_type = 'oidc'  # for app.py:login() method
        self.auth_brand = 'Google'
        if len(appopt.config['USER_AUTH_BRAND']):
            self.auth_brand = appopt.config['USER_AUTH_BRAND']
        self.discovery = self.oidc_url + '/.well-known/openid-configuration'
        r = requests.get(self.discovery)
        if not r.ok:
            print("Error discovering {} endpoints: {}".format(self.auth_brand, r.text), file=sys.stderr)
            sys.exit(1)
        self.oidc_config = r.json()
        if self.debug:
            with open("/tmp/oidc-config.json", "w") as f:
                print("oidc_config: ", json.dumps(self.oidc_config, indent=2), file=f)
            print("OpenID config at /tmp/oidc-config.json")
        self.code_request_uri = "{}?response_type=code&client_id={}&redirect_uri={}&scope=openid+email+profile&audience=https://opcon/user&prompt=login".format(
            self.oidc_config['authorization_endpoint'],
            self.client_id,
            self.base_url + "/_callback")
        self.oidc_keys = self.get_oidc_keys()
        self.ug_hash = dict()   # who has logged in

    def prepare_token_request(self, code):
        token_url = self.oidc_config['token_endpoint']
        headers = {'Content-Type': 'application/x-www-form-urlencoded',
                   'Accept': 'application/json'}
        payload = {'client_id': self.client_id,
                   'code': code,
                   'redirect_uri': self.base_url + "/_callback",
                   'grant_type': 'authorization_code'}
        return token_url, headers, payload

    def get_oidc_keys(self):
        oauth_keys = {}
        endpoint = self.oidc_config['jwks_uri']
        r = requests.get(url=endpoint, headers={
            'Content-Type': 'application/x-wwwform-urlencoded',
            'Accept': 'application/json'})
        keys = r.json()['keys']
        for key in keys:
            kid = key['kid']
            code = key['n']
            if self.debug:
                print("Adding {} key for {} ({})".format(self.auth_brand, kid, key['alg']))
            oauth_keys[kid] = key
        return oauth_keys

    def validate_access_token(self, token):
        at_list = token.split('.')
        at_list[0] = self.b64repad(at_list[0])
        at_list[1] = self.b64repad(at_list[1])
        at_list[2] = self.b64repad(at_list[2])
        header = json.loads(self.b64decode(at_list[0]).decode('utf-8'))
        body = json.loads(self.b64decode(at_list[1]).decode('utf-8'))
        tok = header['kid']
        if tok not in self.oidc_keys:
            return None
        token = token + '=' * divmod(len(token), 4)[1]
        try:
            claims = jwt.decode(token,
                                self.oidc_keys[tok]['x5c'][0],
                                issuer=self.oidc_config['issuer'],
                                audience=body['aud'],
                                algorithms=[header['alg']],
                                options={'verify_signature': False})
        except (jwt.ExpiredSignatureError,
                jwt.InvalidTokenError) as e:
            print('validate_access_token:', e)
            return None
        return claims

    def user_auth(self, username, token_d):
        # real auth is done in app.py:login_callback(), and user token fetched from there
        claims = self.validate_access_token(token_d['access_token'])
        if claims is None:
            return False
        if self.debug:
            with open(f'/tmp/{username}-claims.json', 'w') as f:
                print(f"dumping user {username} claims")
                print(json.dumps(claims, indent=2), file=f)
        header, id_token, tail = token_d['id_token'].split('.')
        id_token = self.b64repad(id_token)
        id_dict = json.loads(self.b64decode(id_token))
        self.ug_hash[username] = id_dict['exp']
        if self.debug:
            print("oidc user_auth({}) good until {}".format(username, self.ug_hash[username]))
        return True

    def user_loader(self, username):
        username = username.decode('utf-8')
        if self.debug:
            print("trying user_loader({}) in user hash: {}".format(
                username, username in self.ug_hash))
        if username not in self.ug_hash:
            return None
        if self.debug:
            print("user_loader({}) expires at {}".format(username, self.ug_hash[username]))
        if self.ug_hash[username] >= int(time.time()):
            return username
        return None

    def b64repad(self, token):
        pad_len = len(token) % 4
        if pad_len == 0:
            return token
        return token + "=" * pad_len

    def b64decode(self, string):
        '''a version of b64decode that figures out which version of base64 is being used'''
        if '_' in string:
            return base64.urlsafe_b64decode(string)
        return base64.b64decode(string)

    def get_user_from_token(self, token):
        header, id_token, tail = token.split('.')
        id_token = self.b64repad(id_token)
        id_dict = json.loads(self.b64decode(id_token))
        if self.debug:
            username = id_dict['email']
            fname = f'/tmp/{username}-token.json'
            print("dumping user_auth token to", fname)
            with open(fname, 'w') as f:
                print(json.dumps(id_dict, indent=2), file=f)
        return id_dict['email']
