from flask import (
    Flask,
    redirect, request,
    url_for)
from oauthlib.oauth2 import WebApplicationClient
import requests
import base64
import json
import sys
import time


class UserAuth(object):
    def __init__(self, appopt):
        # GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET
        (self.client_id,
         self.client_secret,
         self.base_url) = appopt.config['USER_AUTH_DATA'].split(',')
        self.debug = appopt.config['USER_AUTH_DEBUG']
        self.auth_type = 'oidc'  # for app.py:login() method
        self.auth_brand = 'Google'
        self.discovery = 'https://accounts.google.com/.well-known/openid-configuration'
        self.ug_hash = dict()   # who has logged in
        self.client = WebApplicationClient(self.client_id)
        r = requests.get(self.discovery)
        if not r.ok:
            print("Error discovering Google endpoints: {}".format(r.text), file=sys.stderr)
            sys.exit(1)
        self.oidc_config = r.json()
        self.request_uri = self.client.prepare_request_uri(
            self.oidc_config['authorization_endpoint'],
            redirect_uri=self.base_url + '/_callback',
            scope=["openid", "email", "profile"])

    def user_auth(self, username, token_d):
        # real auth is done in app.py:login_callback(), and user token fetched from there
        header, id_token, tail = token_d['id_token'].split('.')
        id_token = self.b64repad(id_token)
        id_dict = json.loads(base64.b64decode(id_token))
        self.ug_hash[username] = id_dict['exp']
        if self.debug:
            print("oidc user_auth({}) good until {}".format(username, self.ug_hash[username]))
        return True

    def user_loader(self, username):
        # username = username.decode('utf-8')
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

    def get_user_from_token(self, token):
        header, id_token, tail = token.split('.')
        id_token = self.b64repad(id_token)
        id_dict = json.loads(base64.b64decode(id_token))
        return id_dict['email']
