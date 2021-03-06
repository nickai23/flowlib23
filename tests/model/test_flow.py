# -*- coding: utf-8 -*-
import unittest

import flowlib
from flowlib.exceptions import FlowLibException, FlowValidationException
from flowlib.model.flow import (Flow, FlowElement,
    ControllerService, RemoteProcessGroup, ProcessGroup, Processor, InputPort, OutputPort)
from flowlib.model.component import FlowComponent

from tests import utils

class TestFlow(unittest.TestCase):

    def test_load_flow(self):
        flow = utils.load_test_flow(init=False)

        self.assertRaisesRegex(FlowValidationException, "^Cannot validate an uninitialized flow.*", flow.validate)
        flow.initialize(utils.COMPONENT_DIR)
        flow.validate()

    def test_find_component_by_path(self):
        flow = utils.load_test_flow()
        real = 'test-component.yaml'
        notreal = 'not-real/abc.yaml'
        self.assertIsInstance(flow.find_component_by_path(real), FlowComponent)
        self.assertIsNone(flow.find_component_by_path(notreal))

        duplicate = utils.load_test_component('test-component.yaml')
        flow._loaded_components['duplicate'] = duplicate
        self.assertRaisesRegex(FlowLibException, '^Found multiple loaded components with source_file.*', flow.find_component_by_path, 'test-component.yaml')

    def find_controller_by_name(self):
        flow = utils.load_test_flow()

        controller = flow.find_controller_by_name('aws-s3-credentials')
        self.assertIsInstance(controller, ControllerService)

        flow._controllers.append(controller)
        self.assertRaisesRegex(FlowLibException, '^Found multiple controllers named.*', flow.find_controller_by_name, 'aws-s3-credentials')
        self.assertIsNone(flow.find_controller_by_name('not-real'), ControllerService)

    def test_get_parent_element(self):
        flow = utils.load_test_flow()

        # check that the parent of flow itself is None
        self.assertIsNone(flow.get_parent_element(flow))

        # get the first element at the flow root
        el = [e for e in flow._elements.values()][0]
        self.assertIsInstance(flow.get_parent_element(el), Flow)

        # get all the process groups at the root canvas level
        groups = [g for g in flow._elements.values() if g.type == 'process_group']

        for g in groups:
            # for each group, get all non-process group elements
            elements = [e for e in g._elements.values() if e.type != 'process_group']
            for e in elements:
                # assert that the parent of each element is the correct group
                self.assertEqual(g, flow.get_parent_element(e))

    def test_flow_element_from_dict(self):
        no_name = {
            'name': '',
            'type': 'invalid-type'
        }
        self.assertRaisesRegex(FlowLibException, "^Element names may not be empty.*", FlowElement.from_dict, no_name)
        invalid_name = {
            'name': 'invalid{}name'.format(Flow.PG_NAME_DELIMETER),
            'type': 'processor'
        }
        self.assertRaisesRegex(FlowLibException, ".*Element names may not contain.*", FlowElement.from_dict, invalid_name)
        invalid_type = {
            'name': 'test',
            'type': 'invalid-type'
        }
        self.assertRaisesRegex(FlowLibException, "^Element 'type' field must be one of .*", FlowElement.from_dict, invalid_type)
        missing_package_id = {
            'name': 'test-processor',
            'type': 'processor',
            'config': {}
        }
        self.assertRaisesRegex(FlowLibException, ".*config.package_id is a required field.*", FlowElement.from_dict, missing_package_id)
        processor = {
            'name': 'test-processor',
            'type': 'processor',
            'config': {
                'package_id': 'io.b23.package.id'
            }
        }
        self.assertIsInstance(FlowElement.from_dict(processor), Processor)
        process_group = {
            'name': 'test-process-group',
            'type': 'process_group'
        }
        self.assertIsInstance(FlowElement.from_dict(process_group), ProcessGroup)
        input_port = {
            'name': 'test-input-port',
            'type': 'input_port'
        }
        self.assertIsInstance(FlowElement.from_dict(input_port), InputPort)
        output_port = {
            'name': 'test-output-port',
            'type': 'output_port'
        }
        self.assertIsInstance(FlowElement.from_dict(output_port), OutputPort)
        output_port = {
            'name': 'test-remote-group',
            'type': 'remote_process_group',
            'config': {}
        }
        self.assertIsInstance(FlowElement.from_dict(output_port), RemoteProcessGroup)
