from flask import (
    Flask,
    redirect, request,
    url_for)
from oauthlib.oauth2 import WebApplicationClient
import requests
import uuid
import sys


class UserAuth(object):
    def __init__(self, keyvars):
        # GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET
        (self.google_client_id,
         self.google_client_secret,
         self.base_url) = keyvars.split(',')
        self.auth_type = 'oidc'  # for app.py:login() method
        self.auth_brand = 'Google'
        self.discovery = 'https://accounts.google.com/.well-known/openid-configuration'
        self.client_secret = uuid.uuid4().hex
        self.ug_hash = dict()   # who has logged in
        self.client = WebApplicationClient(self.google_client_id)
        r = requests.get(self.discovery)
        if not r.ok:
            print("Error discovering Google endpoints: {}".format(r.text), file=sys.stderr)
            sys.exit(1)
        self.oidc_config = r.json()
        self.request_uri = self.client.prepare_request_uri(
            self.oidc_config['authorization_endpoint'],
            redirect_uri=self.base_url + '/_callback',
            scope=["openid", "email", "profile"])

    def user_auth(self, username, password):
        self.ug_hash[username] = True
        return True

    def authorize(self, resp):
        access_token = resp['access_token']

    def user_loader(self, username):
        print("user_loader(user)")
        if username not in self.ug_hash:
            return None
        return username
