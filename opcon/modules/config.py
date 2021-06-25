
import configparser
import os


class config(object):
    def __init__(self, **kwargs):
        '''config(command_line=True|False, config_file="path") - parse options'''
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
        # command line parsing is second, to override config file
        if 'command_line' in kwargs and kwargs['command_line'] is True:
            from optparse import OptionParser
            parser = OptionParser()
            parser.add_option('-d', '--debug', dest='debug',
                              default=self.config['o_debug'],
                              action='store_true',
                              help='enable debugging mode')
            parser.add_option('-b', '--bosh-url', dest='bosh_url', default='',
                              help='indicate https://<ip>:<port> for bosh director')
            parser.add_option('--skip-tls-verification', dest='verify_tls',
                              default=self.config['o_verify_tls'],
                              action='store_false',
                              help='skip TLS/SSL certificate validation')
            parser.add_option('-u', '--user', dest='bosh_user', default='',
                              help='bosh username')
            parser.add_option('-p', '--pass', '--password', dest='bosh_pass',
                              default='', help='bosh password')
            (options, args) = parser.parse_args()
            self.config['o_debug'] = options.debug
            self.config['o_verify_tls'] = options.verify_tls
            if options.bosh_url:
                self.config['o_director_url'] = options.bosh_url
            if options.bosh_user:
                self.config['o_bosh_user'] = options.bosh_user
            if options.bosh_pass:
                self.config['o_bosh_pass'] = options.bosh_pass
        # parsing done
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
