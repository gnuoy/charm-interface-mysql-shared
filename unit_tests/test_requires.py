# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


import unittest
import mock

import requires


_hook_args = {}


def mock_hook(*args, **kwargs):

    def inner(f):
        # remember what we were passed.  Note that we can't actually determine
        # the class we're attached to, as the decorator only gets the function.
        _hook_args[f.__name__] = dict(args=args, kwargs=kwargs)
        return f
    return inner


class TestMySQLSharedRequires(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._patched_hook = mock.patch('charms.reactive.hook', mock_hook)
        cls._patched_hook_started = cls._patched_hook.start()
        # force requires to rerun the mock_hook decorator:
        reload(requires)

    @classmethod
    def tearDownClass(cls):
        cls._patched_hook.stop()
        cls._patched_hook_started = None
        cls._patched_hook = None
        # and fix any breakage we did to the module
        reload(requires)

    def setUp(self):
        self.msr = requires.MySQLSharedRequires('some-relation', [])
        self._patches = {}
        self._patches_start = {}

    def tearDown(self):
        self.msr = None
        for k, v in self._patches.items():
            v.stop()
            setattr(self, k, None)
        self._patches = None
        self._patches_start = None

    def patch_kr(self, attr, return_value=None):
        mocked = mock.patch.object(self.msr, attr)
        self._patches[attr] = mocked
        started = mocked.start()
        started.return_value = return_value
        self._patches_start[attr] = started
        setattr(self, attr, started)

    def test_registered_hooks(self):
        # test that the hooks actually registered the relation expressions that
        # are meaningful for this interface: this is to handle regressions.
        # The keys are the function names that the hook attaches to.
        hook_patterns = {
            'joined': ('{requires:mysql-shared}-relation-joined', ),
            'changed': ('{requires:mysql-shared}-relation-changed', ),
            'departed': (('{requires:mysql-shared}-relation-'
                          '{broken,departed}'), ),
        }
        for k, v in _hook_args.items():
            self.assertEqual(hook_patterns[k], v['args'])

    def test_joined(self):
        self.patch_kr('set_state')
        self.msr.joined()
        self.set_state.assert_called_once_with('{relation_name}.connected')

    def test_changed(self):
        self.patch_kr('base_data_complete', True)
        self.patch_kr('access_network_data_complete', False)
        self.patch_kr('ssl_data_complete', False)
        self.patch_kr('set_state')
        self.msr.changed()
        self.set_state.assert_has_calls([
            mock.call('{relation_name}.available'),
        ])
        self.patch_kr('access_network_data_complete', True)
        self.msr.changed()
        self.set_state.assert_has_calls([
            mock.call('{relation_name}.available'),
            mock.call('{relation_name}.available.access_network'),
        ])
        self.patch_kr('ssl_data_complete', True)
        self.msr.changed()
        self.set_state.assert_has_calls([
            mock.call('{relation_name}.available'),
            mock.call('{relation_name}.available.access_network'),
            mock.call('{relation_name}.available.ssl'),
        ])

    def test_departed(self):
        self.patch_kr('remove_state')
        self.msr.departed()
        self.remove_state.assert_has_calls([
            mock.call('{relation_name}.available'),
            mock.call('{relation_name}.available.access_network'),
        ])

    def test_configure_no_prefix(self):
        self.patch_kr('set_local')
        self.patch_kr('set_remote')
        expect = {
            'database': 'db',
            'username': 'bob',
            'hostname': 'myhost',
        }
        self.msr.configure('db', 'bob', 'myhost')
        self.set_local.assert_called_once_with(**expect)
        self.set_remote.assert_called_once_with(**expect)

    def test_configure_prefix(self):
        self.patch_kr('set_local')
        self.patch_kr('set_prefix')
        self.patch_kr('set_remote')
        expect = {
            'nova_database': 'db',
            'nova_username': 'bob',
            'nova_hostname': 'myhost',
        }
        self.msr.configure('db', 'bob', 'myhost', prefix='nova')
        self.set_prefix.assert_called_once_with('nova')
        self.set_local.assert_called_once_with(**expect)
        self.set_remote.assert_called_once_with(**expect)

    def test_set_prefix(self):
        self.patch_kr('get_local', ['nova'])
        self.patch_kr('set_local')
        self.msr.set_prefix('neutron')
        self.set_local.assert_called_once_with('prefixes', ['nova', 'neutron'])

    def test_set_prefix_all_new(self):
        self.patch_kr('get_local', [])
        self.patch_kr('set_local')
        self.msr.set_prefix('neutron')
        self.set_local.assert_called_once_with('prefixes', ['neutron'])

    def test_get_prefixes(self):
        self.patch_kr('get_local')
        self.msr.get_prefixes()
        self.get_local.assert_called_once_with('prefixes')

    def test_database_no_prefix(self):
        self.patch_kr('get_local')
        self.msr.database()
        self.get_local.assert_called_once_with('database')

    def test_database_prefix(self):
        self.patch_kr('get_local')
        self.msr.database('nova')
        self.get_local.assert_called_once_with('nova_database')

    def test_username_no_prefix(self):
        self.patch_kr('get_local')
        self.msr.username()
        self.get_local.assert_called_once_with('username')

    def test_username_prefix(self):
        self.patch_kr('get_local')
        self.msr.username('nova')
        self.get_local.assert_called_once_with('nova_username')

    def test_hostname_no_prefix(self):
        self.patch_kr('get_local')
        self.msr.hostname()
        self.get_local.assert_called_once_with('hostname')

    def test_hostname_prefix(self):
        self.patch_kr('get_local')
        self.msr.hostname('nova')
        self.get_local.assert_called_once_with('nova_hostname')

    def test_password_no_prefix(self):
        self.patch_kr('get_remote')
        self.msr.password()
        self.get_remote.assert_called_once_with('password')

    def test_password_prefix(self):
        self.patch_kr('get_remote')
        self.msr.password('nova')
        self.get_remote.assert_called_once_with('nova_password')

    def test_allowed_units_no_prefix(self):
        self.patch_kr('get_remote')
        self.msr.allowed_units()
        self.get_remote.assert_called_once_with('allowed_units')

    def test_allowed_units_prefix(self):
        self.patch_kr('get_remote')
        self.msr.allowed_units('nova')
        self.get_remote.assert_called_once_with('nova_allowed_units')

    def test_base_data_complete_prefix_complete(self):
        self.patch_kr('db_host', 'myhost')
        self.patch_kr('get_prefixes', ['nova'])

        def _get_remote(key):
            data = {
                'nova_password': 'novapass',
                'nova_allowed_units': 'nova_allowed',
            }
            return data[key]
        self.patch_kr('get_remote')
        self.get_remote.side_effect = _get_remote
        self.assertTrue(self.msr.base_data_complete())

    def test_base_data_complete_prefix_incomplete(self):
        self.patch_kr('db_host', 'myhost')
        self.patch_kr('get_prefixes', ['nova', 'neutron'])

        def _get_remote(key):
            data = {
                'nova_password': 'novapass',
                'nova_allowed_units': 'nova_allowed',
                'neutron_password': None,
                'neutron_allowed_units': 'neutron_allowed',
            }
            return data[key]
        self.patch_kr('get_remote')
        self.get_remote.side_effect = _get_remote
        self.assertFalse(self.msr.base_data_complete())

    def test_base_data_complete_no_prefix_complete(self):
        self.patch_kr('db_host', 'myhost')
        self.patch_kr('get_prefixes', [])

        def _get_remote(key):
            data = {
                'password': 'pass',
                'allowed_units': 'neutron_allowed',
            }
            return data[key]
        self.patch_kr('get_remote')
        self.get_remote.side_effect = _get_remote
        self.assertTrue(self.msr.base_data_complete())

    def test_base_data_complete_no_prefix_incomplete(self):
        self.patch_kr('db_host', 'myhost')
        self.patch_kr('get_prefixes', [])

        def _get_remote(key):
            data = {
                'password': None,
                'allowed_units': 'neutron_allowed',
            }
            return data[key]
        self.patch_kr('get_remote')
        self.get_remote.side_effect = _get_remote
        self.assertFalse(self.msr.base_data_complete())

    def test_access_network_data_complete(self):
        self.patch_kr('access_network', '10.0.0.10/24')
        self.assertTrue(self.msr.access_network_data_complete())
        self.patch_kr('access_network', None)
        self.assertFalse(self.msr.access_network_data_complete())

    def test_ssl_data_complete(self):
        self.patch_kr('ssl_cert', 'mycert')
        self.patch_kr('ssl_key', 'mykey')
        self.assertTrue(self.msr.ssl_data_complete())
        self.patch_kr('ssl_key', None)
        self.assertFalse(self.msr.ssl_data_complete())
