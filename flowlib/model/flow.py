# -*- coding: utf-8 -*-
from abc import ABC

from flowlib.model import FlowLibException

from nipyapi.nifi.models.processor_config_dto import ProcessorConfigDTO
from nipyapi.nifi.models.controller_service_dto import ControllerServiceDTO
from nipyapi.nifi.models.reporting_task_dto import ReportingTaskDTO


PG_NAME_DELIMETER = '/'

class Flow:
    def __init__(self, name, canvas, flowlib_version=None, version=None, controllers=None, comments=None, global_vars=None):
        """
        :param name: The name of the Flow
        :type name: str
        :param canvas: The root elements of the flow
        :type canvas: list(FlowElement)
        :param flowlib_version: The version of the flowlib module
        :type flowlib_version: str
        :param version: The version of the Flow
        :type version: str
        :param controllers: The root controllers for the root canvas
        :type controllers: dict(str:Controller)
        :param comments: Flow comments
        :type comments: str
        :param global_vars: Global variables for jinja var injection in NiFi component properties
        :type global_vars: dict(str:Any)
        :attr _loaded_components: A map of components (component_path) loaded while initializing the flow, these are re-useable components
        :type _loaded_components: dict(str:FlowComponent)
        :attr _elements: A map of elements defining the flow logic, may be deeply nested if the FlowElement is a ProcessGroup itself.
          Initialized by calling flow.init()
        :type _elements: dict(str:FlowElement)
        """
        self.name = name
        self.canvas = canvas
        self.flowlib_version = flowlib_version
        self.version = version
        self.controllers = controllers
        self.comments = comments
        self.global_vars = global_vars or dict()
        self._loaded_components = dict()
        self._elements = dict()

    def __repr__(self):
        return str(vars(self))

    def find_component_by_path(self, path):
        """
        A helper method for looking up a component from a breadcrumb path
        :param name: The name of the controller
        :type name: str
        """
        if self._loaded_components:
            filtered = list(filter(lambda x: x.source_file == path, self._loaded_components.values()))
            if len(filtered) > 1:
                raise FlowLibException("Found multiple loaded components named {}".format(name))
            if len(filtered) == 1:
                return filtered[0]
        return None

    def find_controller_by_name(self, name):
        """
        A helper method for looking up a controller by name
        :param name: The name of the controller
        :type name: str
        """
        if self.controllers:
            filtered = list(filter(lambda c: c.name == name, self.controllers))
            if len(filtered) > 1:
                raise FlowLibException("Found multiple controllers named {}".format(name))
            if len(filtered) == 1:
                return filtered[0]
        return None

    def get_parent_element(self, element):
        """
        A helper method for looking up parent elements from a breadcrumb path
        :param element: The element to retrieve the parent of
        :type element: FlowElement
        """
        target = self
        names = element.parent_path.split(PG_NAME_DELIMETER)
        for n in names[1:]:
            elements = target._elements
            target = elements.get(n)
        return target

class FlowElement(ABC):
    """
    An abstract parent class for things that might appear on the flow's canvas
    This is either a ProcessGroup, Processor, InputPort, or OutputPort
    :param _id: The NiFi uuid of the element
    :type _id: str
    :param _parent_id: The NiFi uuid of the process group which contains this element
    :type _parent_id: str
    :param _parent_path: The path of the parent process group on the canvas (e.g flow-name/group-name)
    :type _parent_path: str
    :param _src_component_name: The name of the component which contains this Element
    :type _src_component_name: str
    :param _type: one of ['processor', 'process_group', 'input_port', 'output_port']
    :type _type: str
    :param name: A unique name for the Element
    :type name: str
    :param connections: A list of Connections defining this Elements connections to other Elements
    :type connections: list(Connection)
    """
    def __init__(self, **kwargs):
        self._id = kwargs.get('_id')
        self._parent_id = kwargs.get('_parent_id')
        self._parent_path = kwargs.get('_parent_path')
        self._src_component_name = kwargs.get('_src_component_name')
        self._type = kwargs.get('_type')
        self.name = kwargs.get('name')
        self.connections = [Connection(**c) for c in kwargs.get('connections')] if kwargs.get('connections') else None

    @staticmethod
    def from_dict(elem_dict):
        if not isinstance(elem_dict, dict) or not elem_dict.get('type'):
            raise FlowLibException("FlowElement.from_dict() requires a dict with a 'type' field, one of ['processor', 'process_group', 'input_port', 'output_port']")

        name = elem_dict.get('name')
        if not name or len(name) < 1:
            raise FlowLibException("Element names may not be empty. Found invalid element with parent path: {}".format(elem_dict.get('parent_path')))
        if PG_NAME_DELIMETER in name:
            raise FlowLibException("Invalid element: '{}'. Element names may not contain '{}' characters".format(name, Flow.PG_DELIMETER))

        elem_dict['_type'] = elem_dict.pop('type')
        if elem_dict['_type'] == 'process_group':
            if elem_dict.get('vars'):
                elem_dict['_vars'] = elem_dict.pop('vars')
            return ProcessGroup(**elem_dict)
        elif elem_dict['_type'] == 'processor':
            return Processor(**elem_dict)
        elif elem_dict['_type'] == 'input_port':
            return InputPort(**elem_dict)
        elif elem_dict['_type'] == 'output_port':
            return OutputPort(**elem_dict)
        else:
            raise FlowLibException("Element 'type' field must be one of ['processor', 'process_group', 'input_port', 'output_port']")

    @property
    def id(self):
        return self._id

    @id.setter
    def id(self, _id):
        if self._id:
            raise FlowLibException("Attempted to change readonly attribute after initialization")
        self._id = _id

    @property
    def parent_id(self):
        return self._parent_id

    @parent_id.setter
    def parent_id(self, _id):
        if self._parent_id:
            raise FlowLibException("Attempted to change readonly attribute after initialization")
        self._parent_id = _id

    @property
    def type(self):
        return self._type

    def __repr__(self):
        return str(vars(self))


class ProcessGroup(FlowElement):
    def __init__(self, **kwargs):
        """
        Represents the instantiation of a flowlib Component
        :param component_path: The relative file path of the source component in component_dir
        :type component_path: str
        :param controllers: Maps a required_controller to the controller implementation to use
        :type controllers: dict(str:str)
        :param vars: The variables to inject into the component instance
        :type vars: dict(str:Any)
        :attr _elements: A map of elements defining the flow logic, may be deeply nested if the FlowElement is a ProcessGroup itself.
          Initialized by calling FlowElement.load()
        :type _elements: dict(str:FlowElement)
        """
        super().__init__(**kwargs)
        self.component_path = kwargs.get('component_path')
        self.controllers = kwargs.get('controllers', dict())
        self.vars = kwargs.get('_vars', dict())
        self._elements = dict()


class Processor(FlowElement):
    def __init__(self, **kwargs):
        """
        Represents a processor element within a process group
        :param config: The configuration of the processor to instantiate in NiFi
        :type config: ProcessorConfig
        """
        super().__init__(**kwargs)
        if not kwargs.get('config', {}).get('package_id'):
            raise FlowLibException("Invalid processor definition. config.package_id is a required field")
        if not 'properties' in kwargs.get('config', {}):
            kwargs['config']['properties'] = dict()
        self.config = ProcessorConfig(kwargs['config'].pop('package_id'), **kwargs['config'])


class ProcessorConfig(ProcessorConfigDTO):
    def __init__(self, package_id, **kwargs):
        super().__init__(**kwargs)
        self.package_id = package_id

    def __repr__(self):
        return str(vars(self))


class InputPort(FlowElement):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class OutputPort(FlowElement):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)


class Connection:
    def __init__(self, name, from_port=None, to_port=None, relationships=None):
        self.name = name
        self.from_port = from_port
        self.to_port = to_port
        self.relationships = relationships

    def __repr__(self):
        return str(vars(self))


class Controller:
    def __init__(self, name, config):
        self._id = None
        self._parent_id = None
        self.name = name

        if not 'properties' in config:
            config['properties'] = dict()
        self.config = ControllerServiceConfig(config.pop('package_id'), **config)

    @property
    def id(self):
        return self._id

    @id.setter
    def id(self, _id):
        if self._id:
            raise FlowLibException("Attempted to change readonly attribute after initialization")
        self._id = _id

    @property
    def parent_id(self):
        return self._parent_id

    @parent_id.setter
    def parent_id(self, _id):
        if self._parent_id:
            raise FlowLibException("Attempted to change readonly attribute after initialization")
        self._parent_id = _id

    def __repr__(self):
        return str(vars(self))


class ControllerServiceConfig(ControllerServiceDTO):
    def __init__(self, package_id, **kwargs):
        super().__init__(**kwargs)
        self.package_id = package_id

    def __repr__(self):
        return str(vars(self))


class ReportingTask:
    def __init__(self, name, config):
        self._id = None
        self.name = name

        if not 'properties' in config:
            config['properties'] = dict()
        self.config = ReportingTaskConfig(config.pop('package_id'), **config)

    @property
    def id(self):
        return self._id

    @id.setter
    def id(self, _id):
        if self._id:
            raise FlowLibException("Attempted to change readonly attribute after initialization")
        self._id = _id

    def __repr__(self):
        return str(vars(self))


class ReportingTaskConfig(ReportingTaskDTO):
    def __init__(self, package_id, **kwargs):
        super().__init__(**kwargs)
        self.package_id = package_id

    def __repr__(self):
        return str(vars(self))
