
import configparser
import os


class config(object):
    def __init__(self, **kwargs):
        '''config(config_file="path") - parse options'''
        self.config = dict()
        if 'config_file' in kwargs:
            configini = configparser.ConfigParser()
            configini.read(kwargs['config_file'])
            if 'bosh' in configini:
                g = configini['bosh']
                self.config['o_debug'] = g.getboolean('debug', fallback=False)
                self.config['o_director_url'] = g.get('director_url')
                self.config['o_verify_tls'] = g.getboolean('verify_tls',
                                                           fallback=True)
                self.config['o_testing'] = g.getboolean('testing', fallback=False)
                self.config['o_bosh_user'] = g.get('user',
                                                   fallback=os.getenv('BOSH_USERNAME', ''))
                self.config['o_bosh_pass'] = g.get('pass',
                                                   fallback=os.getenv('BOSH_PASSWORD', ''))
                # default username/password to environment variables
                if self.config['o_bosh_user'] == '':
                    self.config['o_bosh_user'] = os.getenv('BOSH_USERNAME')
                if self.config['o_bosh_pass'] == '':
                    self.config['o_bosh_pass'] = os.getenv('BOSH_PASSWORD')
            if 'auth' in configini:
                a = configini['auth']
                self.config['o_auth_type'] = a.get('type')
                self.config['o_auth_data'] = a.get('data')
                self.config['o_auth_mod'] = a.get('module')
                self.config['o_auth_debug'] = a.getboolean('debug', fallback=False)
        if 'o_debug' in self.config and self.config['o_debug']:
            print("Configuration")
            for k in self.config:
                print(f'\t{k}:{self.config[k]}')

    def __repr__(self):
        return self.config

    def get(self, kw):
        # print("Config.Get {}: {}".format(kw, self.config[kw]))
        if kw in self.config:
            return self.config[kw]
        return None

    def __getitem__(self, kw):
        if kw in self.config:
            return self.config[kw]
        return None
