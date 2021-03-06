# -*- coding: utf-8 -*-
import os
import unittest

from flowlib.model.config import FlowLibConfig
from flowlib.cli import FlowLibCLI

from tests import utils


class TestFlowLibConfig(unittest.TestCase):

    def test_defaults(self):
        config = FlowLibConfig()
        for k in FlowLibConfig.DEFAULTS:
            self.assertEqual(FlowLibConfig.DEFAULTS[k], getattr(config, k))

    def test_new_from_file(self):
        config = utils.load_test_config()
        self.assertIsNotNone(config)
        self.assertEqual(config.nifi_endpoint, 'http://nifi-dev:8080')
        self.assertEqual(config.zookeeper_connection, 'nifi-dev:2181')
        self.assertEqual(config.component_dir, 'components')
        self.assertEqual(len(config.reporting_task_controllers), 1)
        self.assertEqual(len(config.reporting_tasks), 1)
        self.assertIsNone(config.flow_yaml)
        self.assertIsNone(config.scaffold)
        self.assertIsNone(config.generate_docs)
        self.assertIsNone(config.force)
        self.assertIsNone(config.export)
        self.assertIsNone(config.configure_flow_controller)
        self.assertIsNone(config.validate)

    def test_with_flag_overrides(self):
        config = FlowLibConfig()
        nifi_endpoint_override = 'https://whatever.com:8020'
        zookeeper_connection_override = 'fake-zookeeper.com:1111'
        component_dir_override = 'some_other_component_dir'
        documentation_dir_override = 'some_docs'

        args = [
            '--nifi-endpoint', nifi_endpoint_override,
            '--zookeeper-connection', zookeeper_connection_override,
            '--component-dir', component_dir_override,
            '--generate-docs', documentation_dir_override
        ]
        cli = FlowLibCLI(args=args, file_config=config)
        self.assertEqual(config.nifi_endpoint, nifi_endpoint_override)
        self.assertEqual(config.zookeeper_connection, zookeeper_connection_override)
        self.assertEqual(config.component_dir, component_dir_override)
        self.assertEqual(config.generate_docs, documentation_dir_override)
