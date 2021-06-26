import unittest
from opcon.modules import director


class TestDirector(unittest.TestCase):
    def setUp(self):
        # set up mocking for this director, in kind of a ugly way
        self.director = director.Director('https://192.168.0.0:25555',
                                          'admin',
                                          'nothing',
                                          debug=False,
                                          verify_tls=False)
        # set mock values
        self.director.deployments = ['cf', 'zookeeper']

    def test_director(self):
        self.assertNotEqual(self.director, None)

    def test_director_deployments(self):
        depl = self.director.deployments
        self.assertEqual(len(depl), 2)

    def test_direct_oauth_expires(self):
        self.director.oauth = {'expires_in': 84600}
        self.assertEqual(84600, self.director.oauth_token_expires())


if __name__ == '__main__':
    unittest.main()
