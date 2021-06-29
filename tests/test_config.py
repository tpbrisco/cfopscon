import unittest
from opcon.modules import config


class TestConfig(unittest.TestCase):
    def setUp(self):
        self.config = config.config(command_line=False,
                                    config_file="tests/data/test_config.ini")

    def test_config_b_debug(self):
        self.assertEqual(self.config['o_debug'], True)

    def test_config_b_director(self):
        self.assertEqual(self.config['o_director_url'],
                         'https://10.0.0.0:25555')

    def test_config_b_tls(self):
        self.assertEqual(self.config['o_verify_tls'], False)

    def test_config_b_user(self):
        self.assertEqual(self.config['o_bosh_user'], 'username')

    def test_config_b_pass(self):
        self.assertEqual(self.config['o_bosh_pass'], 'password')

    def test_config_auth(self):
        self.assertEqual(self.config['o_auth_type'], 'MOD')

    def test_config_a_data(self):
        self.assertEqual(self.config['o_auth_data'], 'a,b,c')

    def test_config_a_mod(self):
        self.assertEqual(self.config['o_auth_mod'], 'auth_null')

    def test_config_a_debug(self):
        self.assertEqual(self.config['o_auth_debug'], True)

    def test_config_getter(self):
        result = self.config.get('o_auth_debug')
        self.assertEqual(True, result)

    def test_config_repr(self):
        cfgrepr = self.config.__repr__()
        self.assertNotEqual(len(cfgrepr), 0)

    def test_config_absence(self):
        nonevar = self.config.get('notthere')
        self.assertEqual(nonevar, None)
        nonevar = self.config['nothere']
        self.assertEqual(nonevar, None)


if __name__ == '__main__':
    unittest.main()
