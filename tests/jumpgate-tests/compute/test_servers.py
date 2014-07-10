import unittest

import falcon
from falcon.testing import helpers
from mock import MagicMock, patch
import SoftLayer

from jumpgate.compute.drivers.sl.servers import (ServerActionV2,
                                                 ServersV2,
                                                 ServersDetailV2)


TENANT_ID = 333333
INSTANCE_ID = 7890782


class TestServersServerActionV2(unittest.TestCase):

    def test_init(self):
        app = MagicMock()
        instance = ServerActionV2(app)
        self.assertEqual(app, instance.app)

    def setUp(self):
        self.req, self.resp = MagicMock(), MagicMock()
        self.vg_clientMock = MagicMock()
        self.req.env = {'sl_client': {
                        'Virtual_Guest': self.vg_clientMock,
                        'Account': MagicMock()}}

    def perform_server_action(self, tenant_id, instance_id):
        instance = ServerActionV2(app=None)
        instance.on_post(self.req, self.resp, tenant_id, instance_id)

    @patch('SoftLayer.CCIManager')
    @patch('SoftLayer.CCIManager.get_instance')
    @patch('json.loads')
    def test_on_post_create(self, bodyMock, cciGetInstanceMock,
                            cciManagerMock):
        bodyMock.return_value = {'createImage': {'name': 'foobar'}}
        cciGetInstanceMock.return_value = {'blockDevices':
                                           [{'device': 0},
                                            {'device': 1}]}
        instance = ServerActionV2(MagicMock())
        instance.on_post(self.req, self.resp, TENANT_ID, INSTANCE_ID)
        self.assertEquals(self.resp.status, 202)

    @patch('SoftLayer.CCIManager')
    @patch('json.loads')
    def test_on_post_create_fail(self, bodyMock, cciManagerMock):
        e = SoftLayer.SoftLayerAPIError(123, 'abc')
        self.vg_clientMock.createArchiveTransaction.side_effect = e
        bodyMock.return_value = {'createImage': {'name': 'foobar'}}
        instance = ServerActionV2(MagicMock())
        instance.on_post(self.req, self.resp, TENANT_ID, INSTANCE_ID)
        self.assertRaises(SoftLayer.SoftLayerAPIError,
                          self.vg_clientMock.createArchiveTransaction)
        self.assertEquals(self.resp.status, 500)

    @patch('json.loads')
    def test_on_post_powerOn(self, bodyMock):
        bodyMock.return_value = {'os-start': None}
        self.perform_server_action(TENANT_ID, INSTANCE_ID)
        self.assertEquals(self.resp.status, 202)
        self.vg_clientMock.powerOn.assert_called_with(id=INSTANCE_ID)

    @patch('json.loads')
    def test_on_post_powerOff(self, bodyMock):
        bodyMock.return_value = {'os-stop': None}
        self.perform_server_action(TENANT_ID, INSTANCE_ID)
        self.assertEquals(self.resp.status, 202)
        self.vg_clientMock.powerOff.assert_called_with(id=INSTANCE_ID)

    @patch('json.loads')
    def test_on_post_reboot_soft(self, bodyMock):
        bodyMock.return_value = {'reboot': {'type': 'SOFT'}}
        self.perform_server_action(TENANT_ID, INSTANCE_ID)
        self.assertEquals(self.resp.status, 202)
        self.vg_clientMock.rebootSoft.assert_called_with(id=INSTANCE_ID)

    @patch('json.loads')
    def test_on_post_reboot_hard(self, bodyMock):
        bodyMock.return_value = {'reboot': {'type': 'HARD'}}
        self.perform_server_action(TENANT_ID, INSTANCE_ID)
        self.assertEquals(self.resp.status, 202)
        self.vg_clientMock.rebootHard.assert_called_with(id=INSTANCE_ID)

    @patch('json.loads')
    def test_on_post_reboot_default(self, bodyMock):
        bodyMock.return_value = {'reboot': {'type': 'DEFAULT'}}
        self.perform_server_action(TENANT_ID, INSTANCE_ID)
        self.assertEquals(self.resp.status, 202)
        self.vg_clientMock.rebootDefault.assert_called_with(id=INSTANCE_ID)

    @patch('json.loads')
    @patch('SoftLayer.managers.vs.VSManager.upgrade')
    def test_on_post_resize(self, upgradeMock, bodyMock):
        bodyMock.return_value = {"resize": {"flavorRef": "2"}}
        upgradeMock.return_value = True
        self.perform_server_action(TENANT_ID, INSTANCE_ID)
        self.assertEquals(self.resp.status, 202)

    @patch('json.loads')
    def test_on_post_resize_invalid(self, bodyMock):
        bodyMock.return_value = {"resize": {"flavorRef": "17"}}
        self.perform_server_action(TENANT_ID, INSTANCE_ID)
        self.assertEquals(self.resp.status, 400)

    @patch('json.loads')
    def test_on_post_confirm_resize(self, bodyMock):
        bodyMock.return_value = {'confirmResize': None}
        self.perform_server_action(TENANT_ID, INSTANCE_ID)
        self.assertEquals(self.resp.status, 204)

    @patch('json.loads')
    def test_on_post_body_empty(self, bodyMock):
        bodyMock.return_value = {}
        self.perform_server_action(TENANT_ID, INSTANCE_ID)
        self.assertEquals(self.resp.status, 400)
        self.assertEquals(self.resp.body['badRequest']
                          ['message'], 'Malformed request body')

    @patch('json.loads')
    def test_on_post_instanceid_empty(self, bodyMock):
        bodyMock.return_value = {'os-stop': None}
        self.perform_server_action(TENANT_ID, '')
        self.assertEquals(self.resp.status, 404)
        self.assertEquals(self.resp.body['notFound']
                          ['message'], 'Invalid instance ID specified.')

    @patch('json.loads')
    def test_on_post_instanceid_none(self, bodyMock):
        bodyMock.return_value = {'os-start': None}
        self.perform_server_action(TENANT_ID, None)
        self.assertEquals(self.resp.status, 404)

    @patch('json.loads')
    def test_on_post_malformed_body(self, bodyMock):
        bodyMock.return_value = {'os_start': None}
        self.perform_server_action(TENANT_ID, INSTANCE_ID)
        self.assertEquals(self.resp.status, 400)

    def tearDown(self):
        self.req, self.resp, self.vg_clientMock = None, None, None


def get_client_env(**kwargs):
    client = MagicMock()
    env = helpers.create_environ(**kwargs)
    env['sl_client'] = client
    return client, env


class TestServers(unittest.TestCase):
    def setUp(self):

        self.app = MagicMock()
        self.instance = ServersV2(self.app)
        self.payload = {}
        self.body = {'server': {'name': 'testserver',
                                'imageRef':
                                    'a1783280-6b1f',
                                'availability_zone': 'dal05', 'flavorRef': '1',
                                'max_count': 1, 'min_count': 1,
                                'networks': [{'uuid': 489586},
                                             {'uuid': 489588}]}}
        self.body_string = '{"server": {"name": "testserver", ' \
                           '"imageRef": "a1783280-6b1f", ' \
                           '"availability_zone": "dal05", ' \
                           '"flavorRef": "1", ' \
                           '"max_count": 1, ' \
                           '"min_count": 1, ' \
                           '"networks": [{"uuid": 489586}, {"uuid": 489588}]}}'
        self.client, env = get_client_env()

    def test_init(self):
        self.assertEqual(self.app, self.instance.app)

    def test_handle_flavor(self):
        self.instance._handle_flavor(self.payload, self.body)
        self.assertEqual(self.payload['cpus'], 1)
        self.assertEqual(self.payload['memory'], 1024)
        self.assertEqual(self.payload['local_disk'], True)

    def test_handle_sshkeys_empty(self):
        self.instance._handle_sshkeys(self.payload, self.body, self.client)
        self.assertEqual(self.payload['ssh_keys'], [])

    @patch('SoftLayer.managers.sshkey.SshKeyManager.list_keys')
    def test_handle_sshkeys_nonempty_valid(self, sshKeyManagerList):
        sshKeyManagerList.return_value = [{'id': 'fakeid'}]
        self.body['server']['key_name'] = 'fakename'
        self.instance._handle_sshkeys(self.payload, self.body, self.client)
        self.assertEqual(self.payload['ssh_keys'], ['fakeid'])

    @patch('SoftLayer.managers.sshkey.SshKeyManager.list_keys')
    def test_handle_sshkeys_nonempty_invalid(self, sshKeyManagerList):
        sshKeyManagerList.return_value = []
        self.body['server']['key_name'] = 'fakename'
        should_fail = False
        try:
            self.instance._handle_sshkeys(self.payload, self.body, self.client)
            should_fail = True
        except Exception:
            pass
        if should_fail:
            self.fail('Exception expected')

    def test_handle_user_data_empty(self):
        self.instance._handle_user_data(self.payload, self.body)
        self.assertEqual(self.payload['userdata'], '{}')

    def test_handle_user_data_metadata(self):
        self.body['server']['metadata'] = 'metadata'
        self.instance._handle_user_data(self.payload, self.body)
        self.assertEqual(self.payload['userdata'], '{"metadata": "metadata"}')

    def test_handle_user_data_user_data(self):
        self.body['server']['user_data'] = 'user_data'
        self.instance._handle_user_data(self.payload, self.body)
        self.assertEqual(self.payload['userdata'],
                         '{"user_data": "user_data"}')

    def test_handle_user_data_personality(self):
        self.body['server']['personality'] = 'personality'
        self.instance._handle_user_data(self.payload, self.body)
        self.assertEqual(self.payload['userdata'],
                         '{"personality": "personality"}')

    def test_handle_datacenter(self):
        self.body['server']['availability_zone'] = 'dal05'
        self.instance._handle_datacenter(self.payload, self.body)
        self.assertEqual(self.payload['datacenter'], 'dal05')

    @patch('oslo.config.cfg.ConfigOpts.GroupAttr')
    def test_handle_datacenter_empty(self, conf_mock):
        self.body['server']['availability_zone'] = None
        conf_mock.return_value = {
            "default_availability_zone": None
        }
        should_fail = False
        try:
            self.instance._handle_datacenter(self.payload, self.body)
            should_fail = True
        except Exception:
            pass
        if should_fail:
            self.fail('Exception expected')

    def test_handle_network_valid_public_private_ids(self):

        self.instance._handle_network(self.payload, self.client,
                                      [{'uuid': 489586}, {'uuid': 489588}])
        self.assertEqual(self.payload['public_vlan'], 489588)
        self.assertEqual(self.payload['private_vlan'], 489586)
        self.assertEqual(self.payload['private'], False)

    def test_handle_network_invalid_too_many(self):
        should_fail = False
        try:
            self.instance._handle_network(self.payload, self.client,
                                          [{'uuid': 489588}, {'uuid': 489586},
                                           {'uuid': 43}])
            should_fail = True
        except Exception:
            pass
        if should_fail:
            self.fail('Exception excepted, too many arguments')

    def test_handle_network_invalid_id_order(self):
        self.client['Account'].getPrivateNetworkVlans.return_value = []
        should_fail = False
        try:
            self.instance._handle_network(self.payload, self.client,
                                          [{'uuid': 489588}, {'uuid': 489586}])
            should_fail = True
        except Exception:
            pass
        if should_fail:
            self.fail('Exception excepted')

    def test_handle_network_invalid_id_format(self):
        self.client['Account'].getPrivateNetworkVlans.return_value = []
        should_fail = False
        try:
            self.instance._handle_network(self.payload, self.client,
                                          [{'uuid': 'bad_network'}])
            should_fail = True
        except Exception:
            pass
        if should_fail:
            self.fail('Exception excepted')

    def test_handle_network_invalid_id_format_public(self):
        self.client['Account'].getPrivateNetworkVlans.return_value = []
        should_fail = False
        try:
            self.instance._handle_network(self.payload, self.client,
                                          [{'uuid': '489586'},
                                           {'uuid': 'bad_pub_id'}])
            should_fail = True
        except Exception:
            pass
        if should_fail:
            self.fail('Exception excepted')

    def test_handle_network_valid_private_ids(self):
        self.client['Account'].getPrivateNetworkVlans.return_value = [489586]
        self.instance._handle_network(self.payload, self.client,
                                      [{'uuid': 489586}])
        self.assertEqual(self.payload['private_vlan'], 489586)
        self.assertEqual(self.payload['private'], True)

    def test_handle_network_valid_ids(self):
        self.client['Account'].getPrivateNetworkVlans.return_value = [489586]
        self.client['Account'].getPublicNetworkVlans.return_value = [489588]
        self.instance._handle_network(self.payload, self.client,
                                      [{'uuid': 489586}, {'uuid': 489588}])
        self.assertEqual(self.payload['private_vlan'], 489586)
        self.assertEqual(self.payload['public_vlan'], 489588)
        self.assertEqual(self.payload['private'], False)

    def test_handle_network_valid_public(self):
        self.instance._handle_network(self.payload, self.client,
                                      [{'uuid': 'public'}])
        self.assertEqual(self.payload['private'], False)

    def test_handle_network_valid_private(self):
        self.instance._handle_network(self.payload, self.client,
                                      [{'uuid': 'private'}])
        self.assertEqual(self.payload['private'], True)

    def test_handle_network_invalid_private(self):
        should_fail = False
        try:
            self.instance._handle_network(self.payload, self.client,
                                          [{'uuid': 'private'},
                                           {'uuid': 'public'}])
            should_fail = True
        except Exception:
            pass
        if should_fail:
            self.fail('Exception excepted')

    def test_handle_network_invalid_public(self):
        should_fail = False
        try:
            self.instance._handle_network(self.payload, self.client,
                                          [{'uuid': 'public'},
                                           {'uuid': 'private'}])
            should_fail = True
        except Exception:
            pass
        if should_fail:
            self.fail('Exception excepted')

    @patch('SoftLayer.managers.vs.VSManager.create_instance')
    def test_on_post_valid(self, create_instance_mock):
        create_instance_mock.return_value = \
            {"domain": "jumpgate.com",
             "maxMemory": 1024,
             "maxCpuUnits": 'CORE',
             "maxCpu": 1, "metricPollDate": "",
             "createDate": "2014-06-23T14:44:27-05:00",
             "hostname": "testserver",
             "startCpus": 1,
             "lastPowerStateId": "",
             "lastVerifiedDate": "",
             "statusId": 1001,
             "globalIdentifier": "8bfd7c70-5ee4-4581-a2c1-6ae8986fc97a",
             "dedicatedAccountHostOnlyFlag": False,
             "modifyDate": '',
             "accountId": 333582,
             "id": 5139276,
             "fullyQualifiedDomainName": "testserver2.jumpgate.com"}
        client, env = get_client_env(body=self.body_string)
        req = falcon.Request(env)
        resp = falcon.Response()
        self.instance.on_post(req, resp, 'tenant_id')
        self.assertEqual(resp.status, 202)
        self.assertEqual(resp.body['server']['id'], 5139276)

    @patch('SoftLayer.managers.vs.VSManager.create_instance')
    def test_on_post_invalid_create(self, create_instance_mock):
        create_instance_mock.side_effect = Exception('badrequest')
        client, env = get_client_env(body=self.body_string)
        req = falcon.Request(env)
        resp = falcon.Response()
        self.instance.on_post(req, resp, 'tenant_id')
        self.assertEqual(resp.status, 400)

    def test_on_post_invalid(self):
        self.body['server']['networks'][0]['uuid'] = 'invalid'
        client, env = get_client_env(
            body='{"server": {"name": "testserver", '
                 '"imageRef": "a1783280-6b1f", "flavorRef": "invalid"}}')
        req = falcon.Request(env)
        resp = falcon.Response()
        self.instance.on_post(req, resp, 'tenant_id')
        self.assertEqual(resp.status, 400)


class TestServersServersDetailV2(unittest.TestCase):

    def setUp(self):
        self.req, self.resp = MagicMock(), MagicMock()
        self.app = MagicMock()
        self.instance = ServersDetailV2(self.app)

    def test_init(self):
        self.assertEquals(self.app, self.instance.app)

    @patch('SoftLayer.CCIManager.list_instances')
    def test_on_get(self, mockListInstance):
        href = u'http://localhost:5000/compute/v2/333582/servers/4846014'
        dict = {'status': 'ACTIVE',
                'updated': '2014-05-23T10:58:29-05:00',
                'hostId': 4846014,
                'user_id': 206942,
                'addresses': {
                    'public': [{
                        'version': 4,
                        'addr': '23.246.195.197',
                        'OS-EXT-IPS:type': 'fixed'}],
                    'private': [{
                        'version': 4,
                        'addr': '10.107.38.132',
                        'OS-EXT-IPS:type': 'fixed'}]},
                'links': [{
                    'href': href,
                    'rel': 'self'}],
                'created': '2014-05-23T10:57:07-05:00',
                'tenant_id': 333582,
                'image_name': '',
                'OS-EXT-STS:power_state': 1,
                'accessIPv4': '',
                'accessIPv6': '',
                'OS-EXT-STS:vm_state': 'ACTIVE',
                'OS-EXT-STS:task_state': None,
                'flavor': {
                    'id': '1',
                    'links': [{
                        'href': 'http://localhost:5000/compute/v2/flavors/1',
                        'rel': 'bookmark'}]},
                'OS-EXT-AZ:availability_zone': 154820,
                'id': '4846014',
                'security_groups': [{
                    'name': 'default'}],
                'name': 'minwoo-metis',
                }
        status = {'keyName': 'ACTIVE', 'name': 'Active'}
        pwrState = {'keyName': 'RUNNING', 'name': 'Running'}
        sshKeys = []
        dataCenter = {'id': 154820, 'name': 'dal06', 'longName': 'Dallas 6'}
        orderItem = {'itemId': 858,
                     'setupFee': '0',
                     'promoCodeId': '',
                     'oneTimeFeeTaxRate': '.066',
                     'description': '2 x 2.0 GHz Cores',
                     'laborFee': '0',
                     'oneTimeFee': '0',
                     'itemPriceId': '1641',
                     'setupFeeTaxRate': '.066',
                     'order': {
                         'userRecordId': 206942,
                         'privateCloudOrderFlag': False},
                     'laborFeeTaxRate': '.066',
                     'categoryCode': 'guest_core',
                     'setupFeeDeferralMonths': 12,
                     'parentId': '',
                     'recurringFee': '0',
                     'id': 34750548,
                     'quantity': '',
                     }
        billingItem = {'modifyDate': '2014-06-05T08:37:01-05:00',
                       'resourceTableId': 4846014,
                       'hostName': 'minwoo-metis',
                       'recurringMonths': 1,
                       'orderItem': orderItem,
                       }

        mockListInstance.return_value = {'billingItem': billingItem,
                                         'datacenter': dataCenter,
                                         'powerState': pwrState,
                                         'sshKeys': sshKeys,
                                         'status': status,
                                         'accountId': 'foobar',
                                         'id': '1234',
                                         'createDate': 'foobar',
                                         'hostname': 'foobar',
                                         'modifyDate': 'foobar'
                                         }
        self.instance.on_get(self.req, self.resp)
        self.assertEquals(set(self.resp.body['servers'][0].keys()),
                          set(dict.keys()))
        self.assertEquals(self.resp.status, 200)
