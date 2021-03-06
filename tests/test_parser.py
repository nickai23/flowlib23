# -*- coding: utf-8 -*-
import copy
import os
import unittest

from flowlib.exceptions import FlowValidationException
from flowlib.parser import init_flow, replace_flow_element_vars_recursive

from tests import utils

class TestParser(unittest.TestCase):

    def test_init_flow(self):
        flow = utils.load_test_flow(init=False)
        flow.initialize(utils.COMPONENT_DIR)

        self.assertIsInstance(flow.raw, dict)
        self.assertTrue(len(flow._elements.keys()) > 0)
        self.assertTrue(len(flow.components.keys()) == 1)
        self.assertIsNotNone(flow._controllers)
        self.assertTrue(len(flow._controllers) == 1)


    def test_required_controller(self):
        flow = utils.load_test_flow(init=False)

        pg = [e for e in flow.canvas if e['name'] == 'test-process-group'][0]
        pg['controllers'] = dict()
        self.assertRaisesRegex(FlowValidationException, '^Missing required_controllers.*', flow.initialize, utils.COMPONENT_DIR)


    def test_required_var(self):
        flow = utils.load_test_flow(init=False)

        pg = [e for e in flow.canvas if e['name'] == 'test-process-group'][0]
        pg['vars'] = dict()
        self.assertRaisesRegex(FlowValidationException, '^Missing required_vars.*', flow.initialize, utils.COMPONENT_DIR)


    def test_var_injection(self):
        # unset env for jinja helper lookup
        os.environ.clear()
        os.environ['NO_DEFAULT'] = 'env value set'

        flow = utils.load_test_flow()
        replace_flow_element_vars_recursive(flow, flow._elements, flow.components)

        # check env lookup and controller var injection
        controller = flow._elements.get('test-process-group').controllers.get('test_controller')
        self.assertIsNotNone(controller)
        self.assertEqual(controller.config.properties['no_default'], 'env value set')
        self.assertEqual(controller.config.properties['with_default'], 'default value set')

        # check canvas-level processor var injection
        self.assertEqual(flow._elements.get('debug').config.properties['prop1'], 'constant-value')
        self.assertEqual(flow._elements.get('debug').config.properties['prop2'], flow.global_vars['global_var'])

        # check component var injection
        component = flow.find_component_by_path('test-component.yaml')
        pg = flow._elements.get('test-process-group')
        props = flow._elements.get('test-process-group')._elements.get('debug').config.properties
        self.assertEqual(props['prop1'], 'constant-value') # test constant
        self.assertEqual(props['prop2'], flow.global_vars['global_var']) # test global
        self.assertEqual(props['prop3'], component.defaults['default_var1']) # test component default
        self.assertEqual(props['prop4'], pg.vars['default_var2']) # test override component default

        # We can't test the controller lookup because the controller has not been created in NiFi yet
        # so there is no uuid to lookup. This should probably be refactored so that it can be unit tested.
        # For now it will be tested by the itests
        # self.assertEqual(props['controller-lookup'], 'controller') # test controller

    def test_nested_components(self):
        flow = utils.load_test_flow(init=False)
        flow.canvas = []
        pg = {
            'name': 'nested-process-group',
            'type': 'process_group',
            'component_path': 'nested-component.yaml',
        }
        flow.canvas.append(pg)
        flow.initialize(utils.COMPONENT_DIR)
        self.assertIsInstance(flow.raw, dict)
        self.assertTrue(len(flow._elements.keys()) > 0)
        self.assertTrue(len(flow.components.keys()) == 2)

    # Tests Github issue #76
    def test_duplicate_components(self):
        flow = utils.load_test_flow(init=False)
        # Find the first process_group and duplicate it with a new name
        pg_element = [el for el in flow.canvas if el['type'] == 'process_group'][0]
        duplicate = copy.deepcopy(pg_element)
        duplicate['name'] = duplicate['name'] + '-copy'
        flow.canvas.append(duplicate)
        flow.initialize(utils.COMPONENT_DIR)
        self.assertIsInstance(flow.raw, dict)
        self.assertTrue(len(flow._elements.keys()) > 0)
        self.assertTrue(len(flow.components.keys()) == 1)

    def test_recursive_components(self):
        flow = utils.load_test_flow(init=False)
        flow.canvas = []
        pg = {
            'name': 'recursive-process-group',
            'type': 'process_group',
            'component_path': 'recursive-component.yaml',
        }
        flow.canvas.append(pg)
        self.assertRaisesRegex(FlowValidationException, "^Recursive component reference found in.*", flow.initialize, utils.COMPONENT_DIR)

    # Tests Github issue #32
    def test_circular_components(self):
        flow = utils.load_test_flow(init=False)
        flow.canvas = []
        pg = {
            'name': 'circular-process-group-root',
            'type': 'process_group',
            'component_path': 'circular-component-1.yaml',
        }
        flow.canvas.append(pg)
        self.assertRaisesRegex(FlowValidationException, "^Circular component reference found in.*", flow.initialize, utils.COMPONENT_DIR)
