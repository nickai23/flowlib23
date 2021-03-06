# -*- coding: utf-8 -*-
import unittest

from flowlib.exceptions import FlowValidationException

from tests import utils

class TestValidator(unittest.TestCase):

    def test_connection_from_pg_no_port_validation(self):
        flow = utils.load_test_flow(init=False)
        flow.canvas = [{
            'name': 'process-group',
            'type': 'process_group',
            'component_path': 'simple-component.yaml',
            'connections': [{
                'name': 'debug'
            }]
        },
        {
            'name': 'debug',
            'type': 'processor',
            'config': {
                'package_id': 'org.apache.nifi.processors.standard.DebugFlow'
            }
        }]
        flow.initialize(utils.COMPONENT_DIR)
        self.assertRaisesRegex(FlowValidationException, "^ProcessGroup\s.*\sdoes not define a from_port for connection.*", flow.validate)

    def test_connection_from_pg_invalid_port_validation(self):
        flow = utils.load_test_flow(init=False)
        flow.canvas = [{
            'name': 'process-group',
            'type': 'process_group',
            'component_path': 'simple-component.yaml',
            'connections': [{
                'name': 'debug',
                'from_port': 'not-real'
            }]
        },
        {
            'name': 'debug',
            'type': 'processor',
            'config': {
                'package_id': 'org.apache.nifi.processors.standard.DebugFlow'
            }
        }]
        flow.initialize(utils.COMPONENT_DIR)
        self.assertRaisesRegex(FlowValidationException, "^ProcessGroup\s.*\sdoes not define an OutputPort named\s.*, must be one of:\s.*$", flow.validate)


    def test_connection_to_pg_no_port_validation(self):
        flow = utils.load_test_flow(init=False)
        flow.canvas = [{
            'name': 'debug',
            'type': 'processor',
            'config': {
                'package_id': 'org.apache.nifi.processors.standard.DebugFlow'
            },
            'connections': [{
                'name': 'process-group'
            }]
        },
        {
            'name': 'process-group',
            'type': 'process_group',
            'component_path': 'simple-component.yaml'
        }]
        flow.initialize(utils.COMPONENT_DIR)
        self.assertRaisesRegex(FlowValidationException, "^ProcessGroup\s.*\sdoes not define a to_port for connection.*", flow.validate)


    def test_connection_to_pg_invalid_port_validation(self):
        flow = utils.load_test_flow(init=False)
        flow.canvas = [{
            'name': 'debug',
            'type': 'processor',
            'config': {
                'package_id': 'org.apache.nifi.processors.standard.DebugFlow'
            },
            'connections': [{
                'name': 'process-group',
                'to_port': 'not-real'
            }]
        },
        {
            'name': 'process-group',
            'type': 'process_group',
            'component_path': 'simple-component.yaml'
        }]
        flow.initialize(utils.COMPONENT_DIR)
        self.assertRaisesRegex(FlowValidationException, "^ProcessGroup\s.*\sdoes not define an InputPort named\s.*, must be one of:\s.*$", flow.validate)
