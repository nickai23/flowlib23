# -*- coding: utf-8 -*-
import copy
import os
import re
import yaml

import jinja2
from jinja2 import Environment

import flowlib
from flowlib.logger import log
from flowlib.exceptions import FlowLibException, FlowValidationException
from flowlib.model.component import FlowComponent
from flowlib.model.flow import Flow, FlowElement, ControllerService, Processor, ProcessGroup, ReportingTask
from flowlib.validator import check_name, is_component_circular

env = Environment()

def _set_global_helpers(controllers=None):

    if not controllers:
        controllers = dict()

    def env_lookup(key, default=None):
        value = os.getenv(key, default)
        return value

    def controller_lookup(name):
        if name in controllers:
            return controllers[name].id
        else:
            return None

    env.globals['env'] = env_lookup
    env.globals['controller'] = controller_lookup


def init_controllers(controllers):
    """
    :param controllers: A list of controller services that require initialization
    :type controllers: list(dict)
    :return: list(Controller)
    """
    # Construct and validate controllers
    controllers = list(map(lambda c: ControllerService(**c), controllers))
    if len(controllers) != len(set(list(map(lambda c: c.name, controllers)))):
        raise FlowValidationException("Duplicate controllers are defined. Controller names must be unique.")

    # Inject template vars into controller properties
    _set_global_helpers()
    for c in controllers:
        check_name(c.name)
        _template_properties(c)

    return controllers


def init_reporting_tasks(controllers, reporting_tasks):
    """
    :param controllers: A list of controller services
    :type controllers: list(Controller)
    :param reporting_tasks: A list of reporting tasks that require initialization
    :type reporting_tasks: list(dict)
    :return: list(ReportingTask)
    """
    # Construct and validate reporting tasks
    reporting_tasks = list(map(lambda t: ReportingTask(**t), reporting_tasks))
    if len(reporting_tasks) != len(set(list(map(lambda t: t.name, reporting_tasks)))):
        raise FlowValidationException("Duplicate reporting_tasks are defined. ReportingTask names must be unique.")

    # Inject template vars into reporting task properties, apply controller service lookups
    _set_global_helpers(controllers={c.name: c for c in controllers})
    for t in reporting_tasks:
        check_name(t.name)
        _template_properties(t)

    return reporting_tasks


def init_flow(flow, component_dir=None, with_components=None):
    """
    Initialize a Flow from from a yaml definition
    :param flow: An unitialized Flow instance
    :type flow: flowlib.model.flow.Flow
    :param component_dir: The directory of components to use for initializing process groups
    :type component_dir: str
    :param with_components: A list of components to use for initializing process groups
    :type with_components: list(DeployedComponent)
    """
    check_name(flow.name)

    # Set controllers as empty dict for now so that the env helper is available for templating controller properties
    _set_global_helpers()
    if 'env' in flow.global_vars or 'controller' in flow.global_vars:
        log.warning("'env' and 'controller' are reserved words and should not be set inside of globals, these values will be overwritten.")

    # Jinja template the global vars
    for k,v in flow.global_vars.items():
        if isinstance(v, str):
            t = env.from_string(v)
            flow.global_vars[k] = t.render()

    # Set jinja globals for templating process_group.vars and processor.properties later
    env.globals.update(**flow.global_vars)

    # initialize and apply templating for the controller services
    flow._controllers = init_controllers(flow.controller_services)

    log.info("Initializing root Flow {}".format(flow.name))
    for elem_dict in flow.canvas:
        elem_dict['_parent_path'] = flow.name
        el = FlowElement.from_dict(copy.deepcopy(elem_dict))
        check_name(el.name)
        el.src_component_name = 'root'

        if flow._elements.get(el.name):
            raise FlowValidationException("Root FlowElement named '{}' is already defined.".format(el.name))
        else:
            flow._elements[el.name] = el

        if component_dir and with_components:
            raise FlowLibException("Only one of component_dir or with_components should be provided")

        if isinstance(el, ProcessGroup):
            if with_components:
                # load all components before initialization
                for component in [c.component for c in with_components]:
                    _load_component(el, flow, component=component)
                _init_component_recursive(el, flow)
            elif component_dir:
                _load_component(el, flow, component_dir=component_dir)
                # otherwise, provide component_dir so we can load them only when they are needed
                _init_component_recursive(el, flow, component_dir)
            else:
                raise FlowValidationException("Attempted to load component {} but no component_dir or components were specified".format(el.component_path))


def _load_component(el, flow, component_dir=None, component=None):
    """
    Parse and load a component from a dict or from a component_dir.
    If the component already exists then this method does nothing
    """
    if component_dir and component:
        raise FlowLibException("Only one of component_dir or component should be provided")

    if component_dir:
        with open(os.path.join(component_dir, el.component_path), 'r') as f:
            raw_component = yaml.safe_load(f)
        source_file = f.name.split(component_dir)[1].lstrip(os.sep)
        log.info("Loading component from file: {}".format(source_file))
        raw_component['source_file'] = source_file
    elif component:
        raw_component = component
    else:
        raise FlowValidationException("Attempted to load component {} but no component_dir or raw component were specified".format(el.component_path))

    if not 'name' in raw_component:
        raise FlowValidationException("Component does not contain a 'name' field")
    else:
        component_name = raw_component['name']
    check_name(component_name)

    # save the component so it can be instantiated later
    if flow._loaded_components.get(component_name):
        log.info("A component named {} is already defined, skipping...".format(component_name))
    else:
        flow._loaded_components[component_name] = FlowComponent(copy.deepcopy(raw_component), **raw_component)


def _init_component_recursive(pg_element, flow, component_dir=None):
    log.info("Loading ProcessGroup: {}".format(pg_element.name))
    component = flow.find_component_by_path(pg_element.component_path)
    if not component:
        parent = flow.get_parent_element(pg_element)
        source = parent.source_file if hasattr(parent, 'source_file') else 'root'
        raise FlowValidationException("Component reference {} not found for ProcessGroup {} loaded from {}".format(
            pg_element.component_path, pg_element.name, source))
    else:
        pg_element.src_component_name = component.name

    # Validate all required controllers are provided
    for k,v in component.required_controllers.items():
        if not k in pg_element.controllers:
            raise FlowValidationException("Missing required_controllers. {} is not provided but is required by {}".format(k, component.source_file))

        controller = flow.find_controller_by_name(pg_element.controllers[k])
        if v != controller.config.package_id:
            raise FlowValidationException("Invalid controller reference. A controller of type {} was provided, but {} is required by {}".format(controller.config.package_id, v, component.source_file))

        pg_element.controllers[k] = controller

    # Validate all required variables are provided
    if component.required_vars:
        for v in component.required_vars:
            if not v in pg_element.vars:
                raise FlowValidationException("Missing required_vars. {} is not provided but is required by {}".format(v, component.source_file))

    # Call FlowElement.from_dict() on each element in the process_group
    for elem_dict in component.process_group:
        elem_dict['_parent_path'] = "{}{}{}".format(pg_element._parent_path, Flow.PG_NAME_DELIMETER, pg_element.name)
        el = FlowElement.from_dict(copy.deepcopy(elem_dict))
        check_name(el.name)
        el.src_component_name = component.name

        if pg_element._elements.get(el.name):
            raise FlowValidationException("Found duplicate elements. A FlowElement named '{}' is already defined in {}".format(el.name, pg_element.component_ref))
        else:
            pg_element._elements[el.name] = el

        if isinstance(el, ProcessGroup):
            if el.component_path == pg_element.component_path:
                raise FlowValidationException("Recursive component reference found in {}. A component cannot reference itself.".format(pg_element.component_path))
            elif is_component_circular(flow, el):
                raise FlowValidationException("Circular component reference found in {}. One of this components's ancestors is another instance of this component".format(pg_element.component_path))
            else:
                if component_dir:
                    _load_component(el, flow, component_dir=component_dir)
                _init_component_recursive(el, flow, component_dir=component_dir)

    component._is_used = True


def replace_flow_element_vars_recursive(flow, elements, loaded_components):
    """
    Recusively apply the variable evaluation to each element in the flow
    :param flow: An unitialized Flow instance
    :type flow: flowlib.model.flow.Flow
    :param elements: The elements to deploy
    :type elements: list(flowlib.model.flow.FlowElement)
    :param loaded_components: The components that were imported during flow.init()
    :type loaded_components: map(str:flowlib.model.flow.FlowComponent)
    """
    for el in elements.values():
        if isinstance(el, ProcessGroup):
            source_component = flow.find_component_by_path(el.component_path)
            _replace_vars(el, source_component)
            replace_flow_element_vars_recursive(flow, el._elements, loaded_components)

        # This should be called for top-level processors of the flow only
        # which would have access to the global context and nothing else
        elif isinstance(el, Processor):
            # Top level processors may need to reference controller services, so set them explictly before templating
            _set_global_helpers({ c.name: c for c in flow._controllers })
            _template_properties(el)


def _replace_vars(process_group, source_component):
    """
    Replace vars for all Processor elements inside a given ProcessGroup

    Note: We already valdated that all required_vars were present during
        _init_component_recursive() so don't worry about it here

    :param process_group: The process_group processors that need vars evaluated
    :type process_group: flowlib.model.ProcessGroup
    :param component: The source component that the processGroup was created from
    :type component: flowlib.model.flow.FlowComponent
    """
    # Create a dict of vars to replace
    context = copy.deepcopy(source_component.defaults)
    if process_group.vars:
        for key,val in process_group.vars.items():
            t = env.from_string(val)
            context[key] = t.render(**context)

    # Setup controller lookup helper for this process group
    _set_global_helpers(process_group.controllers)

    # Apply var replacements for each value of processor.config.properties
    for el in process_group._elements.values():
        if isinstance(el, Processor):
            _template_properties(el, context)


def _template_properties(el, context=dict()):
    for k,v in el.config.properties.items():
        t = env.from_string(v)
        el.config.properties[k] = t.render(**context)
