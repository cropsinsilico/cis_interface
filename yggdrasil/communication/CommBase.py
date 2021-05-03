import os
import copy
import uuid
import atexit
import logging
import types
import time
import collections
import numpy as np
from yggdrasil import tools, multitasking
from yggdrasil.tools import YGG_MSG_EOF
from yggdrasil.communication import (
    new_comm, get_comm, determine_suffix, TemporaryCommunicationError,
    import_comm)
from yggdrasil.components import import_component, create_component
from yggdrasil.metaschema.datatypes import MetaschemaTypeError, type2numpy
from yggdrasil.metaschema.datatypes.MetaschemaType import MetaschemaType
from yggdrasil.communication.transforms.TransformBase import TransformBase
from yggdrasil.serialize import consolidate_array


logger = logging.getLogger(__name__)
_registered_servers = multitasking.LockedDict(task_method='thread')
_registered_comms = multitasking.LockedDict(task_method='thread')


FLAG_FAILURE = 0
FLAG_SUCCESS = 1
FLAG_TRYAGAIN = 2
FLAG_SKIP = 3
FLAG_EOF = 4
FLAG_INCOMPLETE = 5
FLAG_EMPTY = 6


class NeverMatch(Exception):
    'An exception class that is never raised by any code anywhere'


class IncompleteBaseComm(Exception):
    r"""An exception class for methods that are incomplete for base classes."""


class CommMessage(object):
    r"""Class for passing messages around with additional information required
    to send/receive them.

    Attributes:
        msg (bytes): The serialized message including the header.
        length (int): The size of the message.
        flag (int): Indicates the result of processing the message. Values are:
            FLAG_FAILURE: Processing was unsuccessful.
            FLAG_SUCCESS: Processing was successful.
            FLAG_SKIP:    The message should be skipped.
            FLAG_EOF:     The message indicates that there will be no more messages.
        args (object): The unserialized message (post-transformation).
        header (dict): Parameters sent in the header of the message.
        additional_messages (list): Messages that should be sent along with this
            message as in the case that the message was an iterator.
        worker (CommBase): Worker communicator that should be used to send
            worker messages in the case that the original message had to be split.
        worker_messages (list): Messages that should be sent via the worker comm
            comm as the original message had to be split due to its size.
        sent (bool): True if the message has been sent, False otherwise.
        singular (bool): True if there was only one argument.

    """

    __slots__ = ['msg', 'length', 'flag', 'args', 'header',
                 'additional_messages', 'worker', 'worker_messages',
                 'sent', 'finalized', 'singular', 'stype', 'sinfo']

    def __init__(self, msg=None, length=0, flag=None, args=None, header=None):
        self.msg = msg
        self.length = length
        self.flag = flag
        self.args = args
        self.header = header
        self.additional_messages = []
        self.worker_messages = []
        self.worker = None
        self.sent = False
        self.finalized = False
        self.singular = False
        self.stype = None
        self.sinfo = None

    def __str__(self):
        return 'CommMessage(flag=%s, %.100s..., sent=%s)' % (
            self.flag, str(self.msg), self.sent)

    @property
    def tuple_args(self):
        r"""tuple: Form that arguments were originally supplied."""
        if self.singular:
            return (self.args, )
        return self.args

    def add_message(self, *args, **kwargs):
        r"""Add a message to the list of additional messages that should be sent
        following this one.

        Args:
            *args: Arguments are passed to the CommMessage constructor.
            *kwargs: Keyword arguments are passed to the CommMessage constructor.

        """
        kwargs.setdefault('flag', FLAG_SUCCESS)
        self.additional_messages.append(CommMessage(*args, **kwargs))

    def add_worker_message(self, *args, **kwargs):
        r"""Add a message to the list of messages that should be sent via work
        comm following this one.

        Args:
            *args: Arguments are passed to the CommMessage constructor.
            *kwargs: Keyword arguments are passed to the CommMessage constructor.

        """
        kwargs.setdefault('flag', FLAG_SUCCESS)
        self.worker_messages.append(CommMessage(*args, **kwargs))

    def send_worker_messages(self, **kwargs):
        r"""Send the worker messages via the worker comm.

        Args:
            **kwargs: Keyword arguments are passed to the send_message
                 method of the worker comm for each message.

        Returns:
            bool: Success of the send operations.

        """
        if self.worker is not None:
            for x in self.worker_messages:
                if not self.worker.send_message(x, **kwargs):
                    return False  # pragma: debug
        return True

    def apply_function(self, x):
        r"""Apply a function to the message.

        Args:
            x (function): Function to apply.

        """
        out = x(self)
        out.additional_messages = [x(imsg) for imsg in out.additional_messages]
        return out


def is_registered(commtype, key):
    r"""Determine if a comm object has been registered under the specified key.
    
    Args:
        commtype (str): Comm class to check for the key under.
        key (str): Key that should be checked.

    """
    global _registered_comms
    with _registered_comms.lock:
        if commtype not in _registered_comms:
            return False
        return (key in _registered_comms[commtype])


def get_comm_registry(commtype):
    r"""Get the comm registry for a comm class.

    Args:
        commtype (str): Comm class to get registry for.

    Returns:
        dict: Dictionary of registered comm objects.

    """
    with _registered_comms.lock:
        # if commtype is None:
        #     out = {}
        # else:
        out = _registered_comms.get(commtype, {})
    return out


def register_comm(commtype, key, value):
    r"""Add a comm object to the global registry.

    Args:
        commtype (str): Comm class to register the object under.
        key (str): Key that should be used to register the object.
        value (obj): Object being registered.

    """
    global _registered_comms
    with _registered_comms.lock:
        if commtype not in _registered_comms:
            _registered_comms.add_subdict(commtype)
        if key not in _registered_comms[commtype]:
            _registered_comms[commtype][key] = value


def unregister_comm(commtype, key, dont_close=False):
    r"""Remove a comm object from the global registry and close it.

    Args:
        commtype (str): Comm class to check for key under.
        key (str): Key for object that should be removed from the registry.
        dont_close (bool, optional): If True, the comm will be removed from
            the registry, but it won't be closed. Defaults to False.

    Returns:
        bool: True if an object was closed.

    """
    global _registered_comms
    with _registered_comms.lock:
        if commtype not in _registered_comms:
            return False
        if key not in _registered_comms[commtype]:
            return False
        value = _registered_comms[commtype].pop(key)
        if dont_close:
            return False
        out = import_comm(commtype).close_registry_entry(value)
        del value
    return out


def cleanup_comms(commtype, close_func=None):
    r"""Clean up comms of a certain type.

    Args:
        commtype (str): Comm class that should be cleaned up.

    Returns:
        int: Number of comms closed.

    """
    count = 0
    # if commtype is None:
    #     return count
    global _registered_comms
    with _registered_comms.lock:
        if commtype in _registered_comms:
            keys = list(_registered_comms[commtype].keys())
            for k in keys:
                flag = unregister_comm(commtype, k)
                if flag:  # pragma: debug
                    count += 1
    return count


class CommTaskLoop(multitasking.YggTaskLoop):
    r"""Task loop for comms to ensure cleanup.

    Args:
        comm (:class:.CommBase): Comm class that thread is for.
        name (str, optional): Name for the thread. If not provided, one is
            created by combining the comm name and the provided suffix.
        suffix (str, optional): Suffix that should be added to comm name to name
            the thread. Defaults to 'CommTask'.
        **kwargs: Additional keyword arguments are passed to the parent class.

    Attributes:
        comm (:class:.CommBase): Comm class that thread is for.

    """
    def __init__(self, comm, name=None, suffix='CommTask', **kwargs):
        self.comm = comm
        if name is None:
            name = '%s.%s' % (comm.name, suffix)
        super(CommTaskLoop, self).__init__(name=name, **kwargs)

    def on_main_terminated(self):  # pragma: debug
        r"""Actions taken on the backlog thread when the main thread stops."""
        self.debug('is_interface = %s, direction = %s',
                   self.comm.is_interface, self.comm.direction)
        if self.comm.is_interface:
            self.debug('_1st_main_terminated = %s', str(self._1st_main_terminated))
            if self.comm.direction == 'send':
                self._1st_main_terminated = True
                self.comm.send_eof()
                self.comm.close_in_thread(no_wait=True)
                self.debug("Close in thread, closed = %s, nmsg = %d",
                           self.comm.is_closed, self.comm.n_msg)
                return
        super(CommTaskLoop, self).on_main_terminated()


class CommServer(multitasking.YggTaskLoop):
    r"""Basic server object to keep track of clients.

    Attributes:
        cli_count (int): Number of clients that have connected to this server.

    """
    def __init__(self, srv_address, cli_address=None, name=None, **kwargs):
        global _registered_servers
        self.cli_count = 0
        self.srv_count = 0
        if cli_address is None:
            cli_address = srv_address
        self.srv_address = srv_address
        self.cli_address = cli_address
        super(CommServer, self).__init__('CommServer(%s).%s.to.%s' % (
            name, cli_address, srv_address), **kwargs)
        _registered_servers[self.srv_address] = self

    # def add_server(self):
    #     r"""Increment the server count."""
    #     global _registered_servers
    #     _registered_servers[self.srv_address].srv_count += 1
    #     self.debug("Added server to server: nservers = %d", self.srv_count)

    def add_client(self):
        r"""Increment the client count."""
        global _registered_servers
        _registered_servers[self.srv_address].cli_count += 1
        self.debug("Added client to server: nclients = %d", self.cli_count)

    # def remove_server(self):
    #     r"""Decrement the client count, closing the server if all clients done."""
    #     global _registered_servers
    #     self.debug("Removing server from server")
    #     _registered_servers[self.srv_address].srv_count -= 1
    #     if _registered_servers[self.srv_address].srv_count <= 0:
    #         self.debug("Shutting down server")
    #         self.terminate()
    #         _registered_servers.pop(self.srv_address)
            
    def remove_client(self):
        r"""Decrement the client count, closing the server if all clients done."""
        global _registered_servers
        self.debug("Removing client from server")
        _registered_servers[self.srv_address].cli_count -= 1
        if _registered_servers[self.srv_address].cli_count <= 0:
            self.debug("Shutting down server")
            self.terminate()
            _registered_servers.pop(self.srv_address)


class CommBase(tools.YggClass):
    r"""Class for handling I/O.

    Args:
        name (str): The environment variable where communication address is
            stored.
        address (str, optional): Communication info. Default to None and
            address is taken from the environment variable.
        direction (str, optional): The direction that messages should flow
            through the connection. 'send' if the connection will send
            messages, 'recv' if the connecton will receive messages. Defaults
            to 'send'.
        is_interface (bool, optional): Set to True if this comm is a Python
            interface binding. Defaults to False.
        language (str, optional): Programming language of the calling model.
            Defaults to 'python'.
        env (dict, optional): Environment variable that should be used.
            Defaults to os.environ if not provided.
        partner_model (str, optional): Name of model that this comm is
            partnered with. Default to None, indicating that the partner
            is not a model.
        partner_language (str, optional): Programming language of this comm's
            partner comm. Defaults to 'python'.
        partner_mpi_ranks (list, optional): Ranks of processes of this comm's
            partner comm(s). Defaults to [].
        datatype (schema, optional): JSON schema (with expanded core types
            defined by |yggdrasil|) that constrains the type of data that
            should be sent/received by this object. Defaults to {'type': 'bytes'}.
            Additional information on specifying datatypes can be found
            :ref:`here <datatypes_rst>`.
        field_names (list, optional): [DEPRECATED] Field names that should be
            used to label fields in sent/received tables. This keyword is only
            valid for table-like datatypes. If not provided, field names are
            created based on the field order.
        field_units (list, optional): [DEPRECATED] Field units that should be
            used to convert fields in sent/received tables. This keyword is only
            valid for table-like datatypes. If not provided, all fields are
            assumed to be unitless.
        as_array (bool, optional): [DEPRECATED] If True and the datatype is
            table-like, tables are sent/recieved with either columns rather
            than row by row. Defaults to False.
        serializer (:class:.DefaultSerialize, optional): Class with serialize and
            deserialize methods that should be used to process sent and received
            messages. Defaults to None and is constructed using provided
            'serializer_kwargs'.
        serializer_kwargs (dict, optional): Keyword arguments that should be
            passed to :class:.DefaultSerialize to create serializer. Defaults to {}.
        format_str (str, optional): String that should be used to format/parse
            messages. Default to None.
        dont_open (bool, optional): If True, the connection will not be opened.
            Defaults to False.
        is_interface (bool, optional): Set to True if this comm is a Python
            interface binding. Defaults to False.
        recv_timeout (float, optional): Time that should be waited for an
            incoming message before returning None. Defaults to 0 (no wait). A
            value of False indicates that recv should block.
        close_on_eof_recv (bool, optional): If True, the comm will be closed
            when it receives an end-of-file messages. Otherwise, it will remain
            open. Defaults to True.
        close_on_eof_send (bool, optional): If True, the comm will be closed
            after it sends an end-of-file messages. Otherwise, it will remain
            open. Defaults to False.
        single_use (bool, optional): If True, the comm will only be used to
            send/recv a single message. Defaults to False.
        reverse_names (bool, optional): If True, the suffix added to the comm
            with be reversed. Defaults to False.
        no_suffix (bool, optional): If True, no directional suffix will be added
            to the comm name. Defaults to False.
        allow_multiple_comms (bool, optional): If True, initialize the comm
            such that mulitiple comms can connect to the same address. Defaults
            to False.
        is_client (bool, optional): If True, the comm is one of many potential
            clients that will be sending messages to one or more servers.
            Defaults to False.
        is_response_client (bool, optional): If True, the comm is a client-side
            response comm. Defaults to False.
        is_server (bool, optional): If True, the commis one of many potential
            servers that will be receiving messages from one or more clients.
            Defaults to False.
        is_response_server (bool, optional): If True, the comm is a server-side
            response comm. Defaults to False.
        recv_converter (func, optional): Converter that should be used on
            received objects. Defaults to None.
        send_converter (func, optional): Converter that should be used on
            sent objects. Defaults to None.
        vars (list, optional): Names of variables to be sent/received by
            this comm. Defaults to [].
        length_map (dict, optional): Map from pointer variable names to

            the names of variables where their length will be stored.
            Defaults to {}.
        comm (str, optional): The comm that should be created. This only serves
            as a check that the correct class is being created. Defaults to None.
        filter (:class:.FilterBase, optional): Callable class that will be used to
            determine when messages should be sent/received. Defaults to None
            and is ignored.
        transform (:class:.TransformBase, optional): Callable class that will be
            used to transform messages that are sent/received. Defaults to None
            and is ignored.
        is_default (bool, optional): If True, this comm was created to handle
            all input/output variables to/from a model. Defaults to False. This
            variable is used internally and should not be set explicitly in
            the YAML.
        outside_loop (bool, optional): If True, and the comm is an
            input/outputs to/from a model being wrapped. The receive/send
            calls for this comm will be outside the loop for the model.
            Defaults to False.
        dont_copy (bool, optional): If True, the comm will not be duplicated
            in the even a model is duplicated via the 'copies' parameter.
            Defaults to False except for in the case that a model is wrapped
            and the comm is inside the loop or that a model is a RPC input to
            a model server.
        default_file (:class:FileComm, optional): Comm information for
            a file that input should be drawn from (for input comms)
            or that output should be sent to (for output comms) in
            the event that a yaml does not pair the comm with another
            model comm or a file.
        default_value (object, optional): Value that should be returned in
            the event that a yaml does not pair the comm with another
            model comm or a file.
        **kwargs: Additional keywords arguments are passed to parent class.

    Class Attributes:
        is_file (bool): True if the comm accesses a file.
        _maxMsgSize (int): Maximum size of a single message that should be sent.
        address_description (str): Description of the information constituting
            an address for this communication mechanism.

    Attributes:
        name (str): The environment variable where communication address is
            stored.
        address (str): Communication info.
        direction (str): The direction that messages should flow through the
            connection.
        is_interface (bool): True if this comm is a Python interface binding.
        language (str): Language that this comm is being called from.
        env (dict): Environment variable that should be used.
        partner_model (str): Name of model that this comm is partnered with.
        partner_language (str): Programming language of this comm's partner comm.
        partner_mpi_ranks (list): Ranks of processes of this comm's partner comm(s).
        serializer (:class:.DefaultSerialize): Object that will be used to
            serialize/deserialize messages to/from python objects.
        recv_timeout (float): Time that should be waited for an incoming
            message before returning None.
        close_on_eof_recv (bool): If True, the comm will be closed when it
            receives an end-of-file messages. Otherwise, it will remain open.
        close_on_eof_send (bool): If True, the comm will be closed after it
            sends an end-of-file messages. Otherwise, it will remain open.
        single_use (bool): If True, the comm will only be used to send/recv a
            single message.
        allow_multiple_comms (bool): If True, initialize the comm such that
            mulitiple comms can connect to the same address.
        is_client (bool): If True, the comm is one of many potential clients
            that will be sending messages to one or more servers.
        is_response_client (bool): If True, the comm is a client-side response
            comm.
        is_server (bool): If True, the comm is one of many potential servers
            that will be receiving messages from one or more clients.
        is_response_server (bool): If True, the comm is a server-side response
            comm.
        recv_converter (func): Converter that should be used on received objects.
        send_converter (func): Converter that should be used on sent objects.
        filter (:class:.FilterBase): Callable class that will be used to determine when
            messages should be sent/received.

    Raises:
        RuntimeError: If the comm class is not installed.
        RuntimeError: If there is not an environment variable with the specified
            name.
        ValueError: If directions is not 'send' or 'recv'.

    """

    _commtype = None
    _schema_type = 'comm'
    _schema_subtype_key = 'commtype'
    _schema_required = ['name', 'commtype', 'datatype']
    _schema_properties = {
        'name': {'type': 'string'},
        'commtype': {'type': 'string', 'default': 'default',
                     'description': ('Communication mechanism '
                                     'that should be used.')},
        'datatype': {'type': 'schema',
                     'default': {'type': 'bytes'}},
        'recv_converter': {'anyOf': [
            {'$ref': '#/definitions/transform'},
            {'type': ['function', 'string']},
            {'type': 'array',
             'items': {'anyOf': [
                 {'$ref': '#/definitions/transform'},
                 {'type': ['function', 'string']}]}}]},
        'send_converter': {'anyOf': [
            {'$ref': '#/definitions/transform'},
            {'type': ['function', 'string']},
            {'type': 'array',
             'items': {'anyOf': [
                 {'$ref': '#/definitions/transform'},
                 {'type': ['function', 'string']}]}}]},
        'vars': {'type': 'array',
                 'items': {'type': 'string'}},
        'length_map': {
            'type': 'object',
            'additionalProperties': {'type': 'string'}},
        'format_str': {'type': 'string'},
        'field_names': {'type': 'array',
                        'items': {'type': 'string'}},
        'field_units': {'type': 'array',
                        'items': {'type': 'string'}},
        'as_array': {'type': 'boolean', 'default': False},
        'filter': {'$ref': '#/definitions/filter'},
        'transform': {'anyOf': [
            {'$ref': '#/definitions/transform'},
            {'type': ['function', 'string']},
            {'type': 'array',
             'items': {'anyOf': [
                 {'$ref': '#/definitions/transform'},
                 {'type': ['function', 'string']}]}}]},
        'is_default': {'type': 'boolean', 'default': False},
        'outside_loop': {'type': 'boolean',
                         'default': False},
        'dont_copy': {'type': 'boolean', 'default': False},
        'default_file': {'$ref': '#/definitions/file'},
        'default_value': {'type': 'any'}}
    _schema_excluded_from_class = ['name']
    _default_serializer = 'default'
    _default_serializer_class = None
    _schema_excluded_from_class_validation = ['datatype']
    is_file = False
    _maxMsgSize = 0
    address_description = None
    no_serialization = False
    _model_schema_prop = ['is_default', 'outside_loop', 'dont_copy',
                          'default_file', 'default_value']
    _disconnect_attr = (tools.YggClass._disconnect_attr
                        + ['_closing_event', '_closing_thread',
                           '_eof_recv', '_eof_sent'])
    _prepare_message_kws = ['header_kwargs', 'skip_serialization',
                            'skip_processing', 'skip_language2python',
                            'after_prepare_message']
    _finalize_message_kws = ['skip_python2language', 'after_finalize_message']

    def __init__(self, name, address=None, direction='send', dont_open=False,
                 is_interface=None, language=None, env=None, partner_copies=0,
                 partner_model=None, partner_language='python', partner_mpi_ranks=[],
                 recv_timeout=0.0, close_on_eof_recv=True, close_on_eof_send=False,
                 single_use=False, reverse_names=False, no_suffix=False,
                 allow_multiple_comms=False,
                 is_client=False, is_response_client=False,
                 is_server=False, is_response_server=False,
                 is_async=False, **kwargs):
        if isinstance(kwargs.get('datatype', None), MetaschemaType):
            self.datatype = kwargs.pop('datatype')
        super(CommBase, self).__init__(name, **kwargs)
        if not self.__class__.is_installed(language='python'):  # pragma: debug
            raise RuntimeError("Comm class %s not installed" % self.__class__)
        if (partner_model is None) and (not is_interface):
            no_suffix = True
        suffix = determine_suffix(no_suffix=no_suffix,
                                  reverse_names=reverse_names,
                                  direction=direction)
        if env is None:
            env = os.environ
        self.env = env
        self.name_base = name
        self.suffix = suffix
        self._name = name + suffix
        if address is None:
            if self.name not in self.env:
                model_name = self.model_name
                prefix = '%s:' % model_name
                if model_name and (not self.name.startswith(prefix)):
                    self._name = prefix + self.name
                if (((self.name not in self.env)
                     and (self.name.replace(':', '__COLON__')
                          not in self.env))):
                    import pprint
                    env_str = pprint.pformat(self.env.copy())
                    raise RuntimeError(
                        'Cannot see %s in env (model = %s). Env:\n%s' %
                        (self.name, model_name, env_str))
            try:
                self.address = self.env[self.name]
            except KeyError:
                self.address = self.env[self.name.replace(':', '__COLON__')]
        else:
            self.address = address
        self.direction = direction
        if is_interface is None:
            is_interface = False  # tools.is_subprocess()
        self.is_interface = is_interface
        if self.is_interface:
            # All models connect to python connection drivers
            partner_model = None
            partner_language = 'python'
            partner_copies = 1
            recv_timeout = False
        if language is None:
            language = 'python'
        self.language = language
        self.partner_model = partner_model
        self.partner_copies = partner_copies
        self.partner_language = partner_language
        self.partner_language_driver = None
        if self.partner_language:
            self.partner_language_driver = import_component(
                'model', self.partner_language)
        self.partner_mpi_ranks = partner_mpi_ranks
        self.language_driver = import_component('model', self.language)
        self.touches_model = (self.partner_model is not None)
        self.is_client = is_client
        self.is_server = is_server
        self.is_async = is_async
        self.is_response_client = is_response_client
        self.is_response_server = is_response_server
        self._server = None
        self.recv_timeout = recv_timeout
        self.close_on_eof_recv = close_on_eof_recv
        self.close_on_eof_send = close_on_eof_send
        self._work_comms = {}
        self.single_use = single_use
        self._used = False
        self._multiple_first_send = True
        self._n_sent = 0
        self._n_recv = 0
        self._bound = False
        self._last_send = None
        self._last_recv = None
        self._type_errors = []
        self._timeout_drain = False
        self._server_class = CommServer
        self._server_kwargs = {}
        self._send_serializer = True
        self.allow_multiple_comms = allow_multiple_comms
        if (((not self.single_use)
             and ((self.is_interface and self.env.get('YGG_THREADING', False))
                  or (self.model_copies > 1) or (self.partner_copies > 1)))):
            self.allow_multiple_comms = True
        if self.single_use and (not self.is_response_server):
            self._send_serializer = False
        self.create_proxy = ((self.is_client or self.allow_multiple_comms)
                             and (not self.is_interface)
                             and (self.direction != 'recv'))
        # Add interface tag
        if self.is_interface:
            self._name += '_I'
        # if self.is_interface:
        #     self._timeout_drain = False
        # else:
        #     self._timeout_drain = self.timeout
        self._closing_event = multitasking.Event()
        self._closing_thread = multitasking.YggTask(
            target=self.linger_close,
            name=self.name + '.ClosingTask')
        self._eof_sent = multitasking.Event()
        self._iterator_backlog = None
        self._field_backlog = dict()
        if self.single_use:
            self._eof_sent.set()
        if self.is_response_client or self.is_response_server:
            self._eof_sent.set()  # Don't send EOF, these are single use
        if self.is_interface:
            atexit.register(self.atexit)
        self._init_before_open(**kwargs)
        if dont_open:
            self.bind()
        else:
            self.open()
        self.logger._instance_name += (
            '=>%s' % str(self.address).replace('%', '%%'))

    def __getstate__(self):
        if self.is_open and (self._commtype != 'buffer'):  # pragma: debug
            raise RuntimeError("Cannot pickle an open comm.")
        out = super(CommBase, self).__getstate__()
        del out['_closing_thread']
        return out

    def __setstate__(self, state):
        super(CommBase, self).__setstate__(state)
        self._closing_thread = multitasking.YggTask(
            target=self.linger_close, name=self.name + '.ClosingTask')
        if self.is_interface:  # pragma: debug
            atexit.register(self.atexit)

    def _init_before_open(self, **kwargs):
        r"""Initialization steps that should be performed after base class, but
        before the comm is opened."""
        seri_cls = kwargs.pop('serializer_class', None)
        seri_kws = kwargs.pop('serializer_kwargs', {})
        if ('datatype' in self._schema_properties) and (self.datatype is not None):
            seri_kws.setdefault('datatype', self.datatype)
        if ((('serializer' not in self._schema_properties)
             and (not hasattr(self, 'serializer')))):
            self.serializer = self._default_serializer
        if isinstance(self.serializer, str):
            seri_kws.setdefault('seritype', self.serializer)
            self.serializer = None
        elif isinstance(self.serializer, dict):
            seri_kws.update(self.serializer)
            self.serializer = None
        # Only update serializer if not already set
        if self.serializer is None:
            # Get serializer class
            if seri_cls is None:
                if (((seri_kws['seritype'] == self._default_serializer)
                     and (self._default_serializer_class is not None))):
                    seri_cls = self._default_serializer_class
                else:
                    seri_cls = import_component('serializer',
                                                subtype=seri_kws['seritype'])
            # Recover keyword arguments for serializer passed to comm class
            for k in seri_cls.seri_kws():
                if k in kwargs:
                    seri_kws.setdefault(k, kwargs[k])
            # Create serializer instance
            self.debug('seri_kws = %.100s', str(seri_kws))
            self.serializer = seri_cls(**seri_kws)
        # Set send/recv converter based on the serializer
        dir_conv = '%s_converter' % self.direction
        if getattr(self, 'transform', []):
            assert(not getattr(self, dir_conv, []))
            # setattr(self, dir_conv, self.transform)
        elif getattr(self, dir_conv, []):
            self.transform = getattr(self, dir_conv)
        else:
            self.transform = getattr(self.serializer, dir_conv, [])
        if self.transform:
            if not isinstance(self.transform, list):
                self.transform = [self.transform]
            for i, iv in enumerate(self.transform):
                if isinstance(iv, str):
                    cls_conv = getattr(self.language_driver, dir_conv + 's')
                    iv = cls_conv.get(iv, iv)
                if isinstance(iv, str):
                    try:
                        iv = create_component('transform', subtype=iv)
                    except ValueError:
                        iv = None
                elif isinstance(iv, dict):
                    from yggdrasil.schema import get_schema
                    transform_schema = get_schema().get('transform')
                    transform_kws = dict(
                        iv,
                        subtype=transform_schema.identify_subtype(iv))
                    iv = create_component('transform', **transform_kws)
                elif isinstance(iv, TransformBase):
                    pass
                elif ((isinstance(iv, (types.BuiltinFunctionType, types.FunctionType,
                                       types.BuiltinMethodType, types.MethodType))
                       or hasattr(iv, '__call__'))):  # pragma: matlab
                    iv = create_component('transform', subtype='function',
                                          function=iv)
                else:  # pragma: debug
                    raise TypeError("Unsupported transform type: '%s'" % type(iv))
                self.transform[i] = iv
        self.transform = [x for x in self.transform if x]
        # Set filter
        if isinstance(self.filter, dict):
            from yggdrasil.schema import get_schema
            filter_schema = get_schema().get('filter')
            filter_kws = dict(self.filter,
                              subtype=filter_schema.identify_subtype(self.filter))
            self.filter = create_component('filter', **filter_kws)

    @staticmethod
    def before_registration(cls):
        r"""Operations that should be performed to modify class attributes prior
        to registration."""
        tools.YggClass.before_registration(cls)
        cls._default_serializer_class = import_component('serializer',
                                                         cls._default_serializer,
                                                         without_schema=True)

    @classmethod
    def get_testing_options(cls, serializer=None, **kwargs):
        r"""Method to return a dictionary of testing options for this class.

        Args:
            serializer (str, optional): The name of the serializer that should
                be used. If not provided, the _default_serializer class
                attribute will be used.

        Returns:
            dict: Dictionary of variables to use for testing. Key/value pairs:
                kwargs (dict): Keyword arguments for comms tested with the
                    provided content.
                send (list): List of objects to send to test file.
                recv (list): List of objects that will be received from a test
                    file that was sent the messages in 'send'.
                contents (bytes): Bytes contents of test file created by sending
                    the messages in 'send'.

        """
        if serializer is None:
            serializer = cls._default_serializer
        if (((serializer == cls._default_serializer)
             and (cls._default_serializer_class is not None))):
            seri_cls = cls._default_serializer_class
        else:
            seri_cls = import_component('serializer', serializer)
        out_seri = seri_cls.get_testing_options(**kwargs)
        out = {'kwargs': out_seri['kwargs'],
               'send': copy.deepcopy(out_seri['objects']),
               'msg': out_seri['objects'][0],
               'contents': out_seri['contents'],
               'objects': out_seri['objects']}
        out['recv'] = copy.deepcopy(out['send'])
        out['dict'] = seri_cls.object2dict(out['msg'], **out['kwargs'])
        if not out_seri.get('exact_contents', True):
            out['exact_contents'] = False
        msg_array = seri_cls.object2array(out['msg'], **out['kwargs'])
        if msg_array is not None:
            out['msg_array'] = msg_array
        if isinstance(out['msg'], bytes):
            out['msg_long'] = out['msg'] + (cls._maxMsgSize * b'0')
        else:
            out['msg_long'] = out['msg']
        for k in ['field_names', 'field_units']:
            if k in out_seri:
                out[k] = copy.deepcopy(out_seri[k])
        return out

    def get_status_message(self, nindent=0, extra_lines_before=None,
                           extra_lines_after=None):
        r"""Return lines composing a status message.
        
        Args:
            nindent (int, optional): Number of tabs that should be used to
                indent each line. Defaults to 0.
            extra_lines_before (list, optional): Additional lines that should be
                added to the beginning of the default print message. Defaults to
                empty list if not provided.
            extra_lines_after (list, optional): Additional lines that should be
                added to the end of the default print message. Defaults to
                empty list if not provided.
                
        Returns:
            tuple(list, prefix): Lines composing the status message and the
                prefix string used for the last message.

        """
        if extra_lines_before is None:
            extra_lines_before = []
        if extra_lines_after is None:
            extra_lines_after = []
        prefix = nindent * '\t'
        lines = ['', '%s%s:' % (prefix, self.name)]
        prefix += '\t'
        lines += ['%s%s' % (prefix, x) for x in extra_lines_before]
        lines += ['%s%-15s: %s' % (prefix, 'address', self.address),
                  '%s%-15s: %s' % (prefix, 'direction', self.direction),
                  '%s%-15s: %s' % (prefix, 'open', self.is_open),
                  '%s%-15s: %s' % (prefix, 'nsent', self._n_sent),
                  '%s%-15s: %s' % (prefix, 'nrecv', self._n_recv)]
        lines += ['%s%s' % (prefix, x) for x in extra_lines_after]
        return lines, prefix

    def printStatus(self, *args, **kwargs):
        r"""Print status of the communicator."""
        nindent = kwargs.get('nindent', 0)
        lines, prefix = self.get_status_message(*args, **kwargs)
        if len(self._work_comms) > 0:
            lines.append('%sWork comms:' % prefix)
            for v in self._work_comms.values():
                lines += v.get_status_message(nindent=nindent + 1)[0]
        self.info('\n'.join(lines))

    @property
    def any_files(self):
        r"""bool: True if the comm interfaces with any files."""
        return self.is_file
        
    @classmethod
    def is_installed(cls, language=None):
        r"""Determine if the necessary libraries are installed for this
        communication class.

        Args:
            language (str, optional): Specific language that should be checked
                for compatibility. Defaults to None and all languages supported
                on the current platform will be checked. If set to 'any', the
                result will be True if this comm is installed for any of the
                supported languages.

        Returns:
            bool: Is the comm installed.

        """
        lang_list = tools.get_supported_lang()
        commtype = cls._commtype
        use_any = False
        if language in [None, 'all']:
            language = lang_list
        elif language == 'any':
            use_any = True
            language = lang_list
        if isinstance(language, list):
            out = (not use_any)
            for lang in language:
                if not cls.is_installed(language=lang):
                    if not use_any:
                        out = False
                        break
                elif use_any:
                    out = True
                    break
        else:
            if commtype in [None, 'server', 'client', 'fork']:
                out = (language in lang_list)
            else:
                # Check driver
                try:
                    drv = import_component('model', language)
                    out = drv.is_comm_installed(commtype=cls._commtype)
                except ValueError:
                    out = False
        return out

    @property
    def maxMsgSize(self):
        r"""int: Maximum size of a single message that should be sent."""
        return self._maxMsgSize

    @property
    def empty_bytes_msg(self):
        r"""str: Empty serialized message."""
        return b''
        
    @property
    def model_name(self):
        r"""str: Name of the model using the comm."""
        return self.env.get('YGG_MODEL_NAME', '')

    @property
    def full_model_name(self):
        r"""str: Name of the model using the comm w/ copy suffix."""
        out = self.model_name
        if out and ('YGG_MODEL_COPY' in self.env):
            out += '_copy%s' % self.env['YGG_MODEL_COPY']
        return out
        
    @property
    def model_copies(self):
        r"""int: Number of copies of the model using the comm."""
        return int(self.env.get('YGG_MODEL_COPIES', '1'))

    @classmethod
    def underlying_comm_class(cls):
        r"""str: Name of underlying communication class."""
        if cls._commtype in [None, 'fork']:
            return False
        return cls._commtype

    @classmethod
    def close_registry_entry(cls, value):
        r"""Close a registry entry."""
        return False

    @classmethod
    def cleanup_comms(cls):
        r"""Cleanup registered comms of this class."""
        return cleanup_comms(cls.underlying_comm_class())

    @classmethod
    def comm_registry(cls):
        r"""dict: Registry of comms of this class."""
        return get_comm_registry(cls.underlying_comm_class())

    @classmethod
    def is_registered(cls, key):
        r"""bool: True if the comm is registered, False otherwise."""
        commtype = cls.underlying_comm_class()
        return is_registered(commtype, key)

    @classmethod
    def register_comm(cls, key, value):
        r"""Register a comm."""
        # commtype = cls._commtype
        commtype = cls.underlying_comm_class()
        logger.debug("Registering %s comm: %s" % (commtype, key))
        register_comm(commtype, key, value)

    @classmethod
    def unregister_comm(cls, key, dont_close=False):
        r"""Unregister a comm."""
        # commtype = cls._commtype
        commtype = cls.underlying_comm_class()
        logger.debug("Unregistering %s comm: %s (dont_close = %s)",
                     commtype, key, dont_close)
        unregister_comm(commtype, key, dont_close=dont_close)

    @classmethod
    def comm_count(cls):
        r"""int: Number of communication connections."""
        out = len(cls.comm_registry())
        if out > 0:
            logger.debug('There are %d %s comms: %s',
                         len(cls.comm_registry()), cls.__name__,
                         [k for k in cls.comm_registry().keys()])
        return out

    @classmethod
    def new_comm_kwargs(cls, *args, **kwargs):
        r"""Get keyword arguments for new comm."""
        kwargs.setdefault('address', 'address')
        return args, kwargs

    @classmethod
    def new_comm(cls, name, *args, **kwargs):
        r"""Initialize communication with new queue."""
        dont_create = kwargs.pop('dont_create', False)
        env = kwargs.get('env', {})
        for ienv in [env, os.environ]:
            if name in ienv:
                kwargs.setdefault('address', ienv[name])
        new_commtype = kwargs.pop('commtype', None)
        if dont_create:
            args = tuple([name] + list(args))
        else:
            args, kwargs = cls.new_comm_kwargs(name, *args, **kwargs)
        if new_commtype is not None:
            new_cls = import_comm(new_commtype)
            return new_cls(*args, **kwargs)
        return cls(*args, **kwargs)

    @property
    def model_env(self):
        r"""dict: Mapping between model name and opposite comm
        environment variables that need to be provided to the model."""
        out = {}
        if self.partner_model is not None:
            out[self.partner_model] = self.opp_comms
        return out

    @property
    def opp_name(self):
        r"""str: Name that should be used for the opposite comm."""
        return self.name
        
    @property
    def opp_address(self):
        r"""str: Address for opposite comm."""
        return self.address

    @property
    def opp_comms(self):
        r"""dict: Name/address pairs for opposite comms."""
        return {self.opp_name: self.opp_address}

    def opp_comm_kwargs(self):
        r"""Get keyword arguments to initialize communication with opposite
        comm object.

        Returns:
            dict: Keyword arguments for opposite comm object.

        """
        kwargs = {'commtype': self._commtype, 'use_async': self.is_async,
                  'allow_multiple_comms': self.allow_multiple_comms}
        kwargs['address'] = self.opp_address
        kwargs['serializer'] = self.serializer
        # TODO: Pass copies/partner_copies in kwargs?
        if self.direction == 'send':
            kwargs['direction'] = 'recv'
        else:
            kwargs['direction'] = 'send'
        kwargs.update(self.serializer.input_kwargs)
        return kwargs

    def bind(self):
        r"""Bind in place of open."""
        if self.create_proxy:
            self.signon_to_server()

    def open(self):
        r"""Open the connection."""
        self.debug("Openning %s", self.address)
        self.bind()

    def _close(self, *args, **kwargs):
        r"""Close the connection."""
        pass

    def close(self, linger=False, **kwargs):
        r"""Close the connection.

        Args:
            linger (bool, optional): If True, drain messages before closing the
                comm. Defaults to False.
            **kwargs: Additional keyword arguments are passed to linger
                method if linger is True.

        """
        self.debug("Closing %s", self.address)
        if linger and self.is_open:
            self.linger(**kwargs)
        else:
            self._closing_thread.set_terminated_flag()
            linger = False
        # Close with lock
        with self._closing_thread.lock:
            self._close(linger=linger)
            self._n_sent = 0
            self._n_recv = 0
            if self.create_proxy:
                self.debug("Signing off from server")
                self.signoff_from_server()
            if len(self._work_comms) > 0:
                self.debug(
                    "Cleaning up %d work comms", len(self._work_comms))
                keys = [k for k in self._work_comms.keys()]
                for c in keys:
                    self.remove_work_comm(c, linger=linger)
                self.debug("Finished cleaning up work comms")
        self.debug("done")

    def close_in_thread(self, no_wait=False, timeout=None):
        r"""In a new thread, close the comm when it is empty.

        Args:
            no_wait (bool, optional): If True, don't wait for closing thread
                to stop.
            timeout (float, optional): Time that should be waited for the comm
                to close. Defaults to None and is set to self.timeout. If False,
                this will block until the comm is closed.

        """
        if self.language_driver.comm_linger:  # pragma: matlab
            self.linger_close()
            self._closing_thread.set_terminated_flag()
        self.debug("current_thread = %s",
                   self._closing_thread.get_current_task())
        try:
            self._closing_thread.start()
            _started_thread = True
        except RuntimeError:  # pragma: debug
            _started_thread = False
        if self._closing_thread.was_started and (not no_wait):  # pragma: debug
            self._closing_thread.wait(key=str(uuid.uuid4()), timeout=timeout)
            if _started_thread and not self._closing_thread.was_terminated:
                self.debug("Closing thread took too long")
                self.close()

    def linger_close(self, **kwargs):
        r"""Wait for messages to drain, then close."""
        self.close(linger=True, **kwargs)

    def linger(self, active_confirm=False):
        r"""Wait for messages to drain."""
        self.debug('')
        if self.direction == 'recv':
            while self.is_open and (self.n_msg_recv_drain > 0):  # pragma: debug
                self.recv_message(timeout=0, skip_deserialization=True)
            self.wait_for_confirm(timeout=self._timeout_drain,
                                  active_confirm=active_confirm)
        else:
            if (self.direction == 'send') and (not self.is_async):
                self.wait_for_workers(timeout=self._timeout_drain)
            for x in self._work_comms.values():
                x.linger()
            self.drain_messages(variable='n_msg_send')
            self.wait_for_confirm(timeout=self._timeout_drain,
                                  active_confirm=active_confirm)
        self.debug("Finished (timeout_drain = %s)", str(self._timeout_drain))

    def language_atexit(self):  # pragma: debug
        r"""Close operations specific to the language."""
        if self.language_driver.comm_atexit is not None:
            self.language_driver.comm_atexit(self)

    def atexit(self):  # pragma: debug
        r"""Close operations."""
        self.debug('atexit begins (n_msg=%d)', self.n_msg)
        self.language_atexit()
        self.debug('atexit after language_atexit, but before close')
        self.close()
        self.debug(
            'atexit finished: closed=%s, n_msg=%d, close_alive=%s',
            self.is_closed, self.n_msg,
            self._closing_thread.is_alive())

    @property
    def is_open(self):
        r"""bool: True if the connection is open."""
        return False

    @property
    def is_closed(self):
        r"""bool: True if the connection is closed."""
        return (not self.is_open)

    @property
    def is_confirmed_send(self):
        r"""bool: True if all sent messages have been confirmed."""
        for v in list(self._work_comms.values()):
            if (v.direction == 'send') and not v.is_confirmed_send:  # pragma: debug
                return False
        return (self.n_msg_send == 0)

    @property
    def is_confirmed_recv(self):
        r"""bool: True if all received messages have been confirmed."""
        for v in list(self._work_comms.values()):
            if (v.direction == 'recv') and not v.is_confirmed_recv:  # pragma: debug
                return False
        return (self.n_msg_recv == 0)

    @property
    def is_confirmed(self):
        r"""bool: True if all messages have been confirmed."""
        if self.direction == 'recv':
            return self.is_confirmed_recv
        else:
            return self.is_confirmed_send

    def wait_for_workers(self, timeout=None):
        r"""Sleep until all workers are closed or have been used."""
        Tout = self.start_timeout(t=timeout,
                                  key_suffix='.wait_for_workers')
        flag = False
        while (not Tout.is_out):
            for x in self._work_comms.values():
                if hasattr(x, 'task_timer'):
                    flag = (not x.task_timer.is_alive())
                else:  # pragma: completion
                    # This is currently unused as wait_for_workers is only
                    # called for non-asynchronous comms
                    flag = (x._used or x.is_closed)
                if not flag:
                    break
            else:
                break
            self.sleep()
        self.stop_timeout(key_suffix='.wait_for_workers')
        return flag

    def wait_for_confirm(self, timeout=None, direction=None,
                         active_confirm=False, noblock=False):
        r"""Sleep until all messages are confirmed."""
        self.debug('')
        if direction is None:
            direction = self.direction
        T = self.start_timeout(t=timeout, key_suffix='.wait_for_confirm')
        flag = False
        while (not T.is_out) and (not getattr(self, 'is_confirmed_%s' % direction)):
            if active_confirm:
                flag = self.confirm(direction=direction, noblock=noblock)
                if flag:
                    break
            self.sleep()
        self.stop_timeout(key_suffix='.wait_for_confirm')
        if not flag:
            flag = getattr(self, 'is_confirmed_%s' % direction)
        self.debug('Done confirming')
        return flag

    def confirm(self, direction=None, noblock=False):
        r"""Confirm message."""
        if direction is None:
            direction = self.direction
        if direction == 'send':
            out = self.confirm_send(noblock=noblock)
        else:
            out = self.confirm_recv(noblock=noblock)
        return out

    def confirm_send(self, noblock=False):
        r"""Confirm that sent message was received."""
        return noblock

    def confirm_recv(self, noblock=False):
        r"""Confirm that message was received."""
        return noblock

    @property
    def n_msg(self):
        r"""int: The number of messages in the connection."""
        if self.direction == 'recv':
            return self.n_msg_recv
        else:
            return self.n_msg_send

    @property
    def n_msg_recv(self):
        r"""int: The number of incoming messages in the connection."""
        return 0

    @property
    def n_msg_send(self):
        r"""int: The number of outgoing messages in the connection."""
        return 0

    @property
    def n_msg_recv_drain(self):
        r"""int: The number of incoming messages in the connection to drain."""
        return self.n_msg_recv

    @property
    def n_msg_send_drain(self):
        r"""int: The number of outgoing messages in the connection to drain."""
        return self.n_msg_send

    @property
    def eof_msg(self):
        r"""str: Message indicating EOF."""
        return YGG_MSG_EOF

    def is_eof(self, msg):
        r"""Determine if a message is an EOF.

        Args:
            msg (obj): Message object to be tested.

        Returns:
            bool: True if the message indicates an EOF, False otherwise.

        """
        out = (isinstance(msg, bytes) and (msg == self.eof_msg))
        return out

    def update_message_from_serializer(self, msg):
        r"""Update a message with information about the serializer.

        Args:
            msg (CommMessage): Incoming message.

        """
        if self.serializer.initialized:
            msg.stype = self.serializer.typedef
            msg.sinfo = self.serializer.serializer_info
            for k in ['format_str', 'field_names', 'field_units']:
                if k in msg.sinfo:
                    msg.stype[k] = msg.sinfo[k]

    def update_serializer_from_message(self, msg):
        r"""Update the serializer based on information stored in a message.

        Args:
            msg (CommMessage): Outgoing message.

        """
        if msg.sinfo is None:
            return
        assert(msg.stype is not None)
        msg.stype = self.apply_transform_to_type(msg.stype)
        msg.sinfo.pop('seritype', None)
        for k in ['format_str', 'field_names', 'field_units']:
            if k in msg.stype:
                msg.sinfo[k] = msg.stype.pop(k)
        msg.sinfo['datatype'] = msg.stype
        self.serializer.initialize_serializer(msg.sinfo)
        self.serializer.update_serializer(skip_type=True, **msg.header)

    def apply_transform_to_type(self, typedef):
        r"""Evaluate the transform to alter the type definition.

        Args:
            typedef (dict): Type definition to transform.

        Returns:
            dict: Transformed type definition.

        """
        for iconv in self.transform:
            if not iconv.original_datatype:
                iconv.set_original_datatype(typedef)
            typedef = iconv.transformed_datatype
        return typedef

    def apply_transform(self, msg_in, for_empty=False, header=False):
        r"""Evaluate the transform to alter the emssage being sent/received.

        Args:
            msg_in (object): Message being transformed.
            for_empty (bool, optional): If True, the transformation is being used
                to check for an empty message and errors will be caught. Defaults
                to False.
            header (dict, optional): Header keyword arguments associated
                with a message. Defaults to False and is ignored.
            typedef (dict, optiona): Type to transform. Default to None and will
                be determined by the serializer if receiving.

        Returns:
            object: Transformed message.

        """
        if not self.transform:
            return msg_in
        self.debug("Applying transformations to message being %s."
                   % self.direction)
        # If receiving, update the expected datatypes to use information
        # about the received datatype that was recorded by the serializer
        if (((self.direction == 'recv') and self.serializer.initialized
             and (not for_empty))):
            assert(self.transform[0].original_datatype)
        # if (((self.direction == 'recv')
        #      and self.serializer.initialized
        #      and (not self.transform[0].original_datatype))):
        #     typedef = self.serializer.typedef
        #     for iconv in self.transform:
        #         if not iconv.original_datatype:
        #             iconv.set_original_datatype(typedef)
        #         typedef = iconv.transformed_datatype
        # Actual conversion
        msg_out = msg_in
        no_init = (for_empty or ((self.direction == 'recv')
                                 and (not self.serializer.initialized)))
        try:
            for iconv in self.transform:
                msg_out = iconv(msg_out, no_init=no_init)
        except BaseException:
            if for_empty:
                return None
            raise  # pragma: debug
        if (((self.direction == 'send') and (header is not False)
             and iconv and iconv.transformed_datatype
             and (not self.serializer.initialized))):
            if not header:
                header = {}
            metadata = dict(header,
                            datatype=iconv.transformed_datatype)
            self.serializer.initialize_serializer(metadata, extract=True)
        return msg_out

    def evaluate_filter(self, *msg_in):
        r"""Evaluate the filter to determine how the message should be
        handled.

        Args:
            *msg_in (object): Parts of message being evaluated.
        
        Returns:
            bool: True if the filter evaluates to True, False otherwise.

        """
        out = True
        if len(msg_in) == 1:
            msg_in = msg_in[0]
        if self.filter and (not self.is_eof(msg_in)):
            out = self.filter(msg_in)
        assert(isinstance(out, bool))
        return out
        
    @property
    def empty_obj_recv(self):
        r"""obj: Empty message object."""
        return self.apply_transform(self.serializer.empty_msg, for_empty=True)

    def is_empty(self, msg, emsg):
        r"""Check that a message matches an empty message object.

        Args:
            msg (object): Message object.
            emsg (object): Empty message object.

        Returns:
            bool: True if the object is empty, False otherwise.

        """
        from yggdrasil.tests import assert_equal
        try:
            assert_equal(msg, emsg, dont_print_diff=True)
        except AssertionError:
            return False
        return True

    def is_empty_recv(self, msg):
        r"""Check if a received message object is empty.

        Args:
            msg (obj): Message object.

        Returns:
            bool: True if the object is empty, False otherwise.

        """
        
        if self.is_eof(msg):
            return False
        return self.is_empty(msg, self.empty_obj_recv)
        
    def chunk_message(self, msg):
        r"""Yield chunks of message of size maxMsgSize

        Args:
            msg (str, bytes): Raw message bytes to be chunked.

        Returns:
            str: Chunks of message.

        """
        prev = 0
        while prev < len(msg):
            next = min(prev + self.maxMsgSize, len(msg))
            yield msg[prev:next]
            prev = next

    def precheck(self, direction):
        r"""Check that comm is ready for action in specified direction,
        raising errors if it is not.

        Args:
            direction (str): Check that comm is ready to perform this
                action.

        """
        if (((self._commtype not in ['server', 'client'])
             and (self.direction != direction))):
            raise RuntimeError(("This comm (%s, %s) is designated to %s and "
                                "therefore cannot %s.")
                               % (self.name, self.address, self.direction, direction))
        if self.single_use and self._used:
            raise RuntimeError("This comm (%s, %s) is single use and it "
                               "was already used."
                               % (self.name, self.address))

    # CLIENT/SERVER METHODS
    def server_exists(self, srv_address):
        r"""Determine if a server exists.

        Args:
            srv_address (str): Address of server comm.

        Returns:
            bool: True if a server with the provided address exists, False
                otherwise.

        """
        global _registered_servers
        return (srv_address in _registered_servers)

    def new_server(self, srv_address):
        r"""Create a new server.

        Args:
            srv_address (str): Address of server comm.

        """
        return self._server_class(srv_address, name=self.name,
                                  **self._server_kwargs)

    def signon_to_server(self):
        r"""Add a client to an existing server or create one."""
        global _registered_servers
        with _registered_servers.lock:
            if self._server is None:
                assert(not self.server_exists(self.address))
                self.debug("Creating new server")
                self._server = self.new_server(self.address)
                self._server.start()
                # Currently server are only started once per model
                # self._server = _registered_servers[self.address]
                if self.direction == 'send':
                    self._server.add_client()
                    self.address = self._server.cli_address
                else:  # pragma: debug
                    # self._server.add_server()
                    # self.address = self._server.srv_address
                    raise RuntimeError("Receive-side proxy untested")

    def signoff_from_server(self):
        r"""Remove a client from the server."""
        global _registered_servers
        with _registered_servers.lock:
            if self._server is not None:
                self.debug("Signing off")
                if self.direction == 'send':
                    self._server.remove_client()
                else:  # pragma: debug
                    # self._server.remove_server()
                    raise RuntimeError("Receive-side proxy untested")
                self._server = None

    # TEMP COMMS
    @property
    def get_work_comm_kwargs(self):
        r"""dict: Keyword arguments for an existing work comm."""
        if self._commtype is None:
            raise IncompleteBaseComm(
                "Base comm class '%s' cannot create work comm."
                % self.__class__.__name__)
        out = dict(commtype=self._commtype, direction='recv',
                   recv_timeout=self.recv_timeout,
                   is_interface=self.is_interface,
                   use_async=self.is_async,
                   single_use=True)
        if out.get('use_async', False):
            out['async_recv_method'] = 'recv_message'
            out['async_recv_kwargs'] = {'skip_deserialization': True}
        return out

    @property
    def create_work_comm_kwargs(self):
        r"""dict: Keyword arguments for a new work comm."""
        if self._commtype is None:
            raise IncompleteBaseComm(
                "Base comm class '%s' cannot create work comm."
                % self.__class__.__name__)
        return dict(commtype=self._commtype, direction='send',
                    recv_timeout=self.recv_timeout,
                    is_interface=self.is_interface,
                    use_async=self.is_async,
                    uuid=str(uuid.uuid4()), single_use=True)

    def get_work_comm(self, header, **kwargs):
        r"""Get temporary work comm, creating as necessary.

        Args:
            header (dict): Information that will be sent in the message header
                to the work comm.
            **kwargs: Additional keyword arguments are passed to header2workcomm.

        Returns:
            :class:.CommBase: Work comm.

        """
        c = self._work_comms.get(header['id'], None)
        if c is None:
            c = self.header2workcomm(header, **kwargs)
            self.add_work_comm(c)
        return c

    def create_work_comm(self, work_comm_name=None, **kwargs):
        r"""Create a temporary work comm.

        Args:
            work_comm_name (str, optional): Name that should be used for the
                work comm. If not provided, one is created from the header id
                and the comm class.
            **kwargs: Keyword arguments for new_comm that should override
                work_comm_kwargs.

        Returns:
            :class:.CommBase: Work comm.

        """
        kws = self.create_work_comm_kwargs
        kws.update(**kwargs)
        if work_comm_name is None:
            cls = kws.get('commtype', 'default')
            work_comm_name = '%s_temp_%s_%s.%s' % (
                self.name, cls, kws['direction'], kws['uuid'])
        c = new_comm(work_comm_name, **kws)
        self.add_work_comm(c)
        return c

    def add_work_comm(self, comm):
        r"""Add work comm to dict.

        Args:
            comm (:class:.CommBase): Comm that should be added.

        Raises:
            KeyError: If there is already a comm associated with the key.

        """
        key = comm.uuid
        if key in self._work_comms:
            raise KeyError("Comm already registered with key %s." % key)
        self._work_comms[key] = comm

    def remove_work_comm(self, key, in_thread=False, linger=False):
        r"""Close and remove a work comm.

        Args:
            key (str): Key of comm that should be removed.
            in_thread (bool, optional): If True, close the work comm in a thread.
                Defaults to False.
            linger (bool, optional): If True, drain messages before closing the
                comm. Defaults to False.

        """
        if key not in self._work_comms:
            return
        if not in_thread:
            c = self._work_comms.pop(key)
            c.close(linger=linger)
        else:  # pragma: debug
            # c = self._work_comms[key]
            # c.close_in_thread(no_wait=True)
            raise Exception("Closing in thread not recommended")

    def workcomm2header(self, work_comm, **kwargs):
        r"""Get header information from a comm.

        Args:
            work_comm (:class:.CommBase): Work comm that header describes.
            **kwargs: Additional keyword arguments are added to the header.

        Returns:
            dict: Header information that will be sent with a message.

        """
        header = kwargs
        header['address'] = work_comm.address
        header['id'] = work_comm.uuid
        return header

    def header2workcomm(self, header, work_comm_name=None, **kwargs):
        r"""Get a work comm based on header info.

        Args:
            header (dict): Information that will be sent in the message header
                to the work comm.
            work_comm_name (str, optional): Name that should be used for the
                work comm. If not provided, one is created from the header id
                and the comm class.
            **kwargs: Additional keyword arguments are added to the returned
                dictionary.

        Returns:
            :class:.CommBase: Work comm.

        """
        kws = self.get_work_comm_kwargs
        kws.update(**kwargs)
        kws['uuid'] = header['id']
        kws['address'] = header['address']
        if work_comm_name is None:
            cls = kws.get('commtype', 'default')
            work_comm_name = '%s_temp_%s_%s.%s' % (
                self.name, cls, kws['direction'], header['id'])
        c = get_comm(work_comm_name, **kws)
        return c

    # SERIALIZATION/DESERIALIZATION METHODS
    def serialize(self, *args, **kwargs):
        r"""Serialize a message using the associated serializer."""
        # Don't send metadata for files
        # kwargs.setdefault('dont_encode', self.is_file)
        kwargs.setdefault('add_serializer_info',
                          (self._send_serializer and (not self.is_file)))
        kwargs.setdefault('no_metadata', self.is_file)
        kwargs.setdefault('max_header_size', self.maxMsgSize)
        return self.serializer.serialize(*args, **kwargs)

    def deserialize(self, *args, **kwargs):
        r"""Deserialize a message using the associated deserializer."""
        # Don't serialize files using JSON
        # kwargs.setdefault('dont_decode', self.is_file)
        return self.serializer.deserialize(*args, **kwargs)

    # SEND METHODS
    def _safe_send(self, *args, **kwargs):
        r"""Send message checking if is 1st message and then waiting."""
        timeout = kwargs.pop('timeout', self.timeout)
        send_1st = ((not self._used) and self._multiple_first_send)
        if send_1st:
            timeout = max(timeout, self.timeout)
            self.suppress_special_debug = True
        Tout = self.start_timeout(timeout, key_suffix='._safe_send')
        out = False
        error = None
        while (not Tout.is_out):
            error = None
            try:
                with self._closing_thread.lock:
                    if self.is_open:
                        out = self._send(*args, **kwargs)
                        if out or (not send_1st):
                            break
                    else:  # pragma: debug
                        self.debug('Comm closed')
                        out = False
                        break
            except TemporaryCommunicationError as e:
                error = e
                self.special_debug("TemporaryCommunicationError: %s" % e)
            self.sleep()
        self.stop_timeout(key_suffix='._safe_send')
        if error and self.is_async:
            raise TemporaryCommunicationError(error)
        if send_1st:
            self.suppress_special_debug = False
        if out:
            self._n_sent += 1
            self._last_send = time.perf_counter()
        return out
    
    def _send(self, msg, *args, **kwargs):  # pragma: debug
        r"""Raw send. Should be overridden by inheriting class."""
        raise IncompleteBaseComm("_send method needs implemented.")

    def send_message(self, msg, skip_safe_send=False, **kwargs):
        r"""Send a message encapsulated in a CommMessage object.

        Args:
            msg (CommMessage): Message to be sent.
            skip_safe_send (bool, optional): If True, no actual send will take
                place. Defaults to False.
            **kwargs: Additional keyword arguments are passed to _safe_send.

        Returns:
            bool: Success or failure of send.
        
        """
        if self.is_closed:
            self.debug('Comm closed')
            return False
        if msg.flag == FLAG_SKIP:
            return True
        elif msg.flag == FLAG_FAILURE:
            return False  # pragma: debug
        elif msg.flag == FLAG_EOF:
            with self._closing_thread.lock:
                if not self._eof_sent.is_set():
                    if self.partner_copies == 1:
                        self._eof_sent.set()
                    else:
                        self.partner_copies -= 1
                else:  # pragma: debug
                    self.debug("EOF SENT TWICE")
                    return False
        elif msg.flag == FLAG_SUCCESS:
            pass
        else:  # pragma: debug
            raise Exception("Unrecognized message flag: %s" % msg.flag)
        self.special_debug('Sending %d bytes to %s', msg.length, self.address)
        if self.maxMsgSize != 0:
            assert(msg.length <= self.maxMsgSize)
        try:
            if skip_safe_send:
                pass
            elif not msg.sent:
                if not self._safe_send(msg.msg, **kwargs):  # pragma: debug
                    self.special_debug('Failed to send %d bytes', msg.length)
                    return False
                msg.sent = True
                self.debug('Sent %d bytes to %s', msg.length, self.address)
            if msg.worker is not None:
                if msg.worker.is_async:
                    if not msg.send_worker_messages(**kwargs):  # pragma: debug
                        self.error("Error sending message chunk")
                        return False
                else:
                    msg.worker.task_timer = self.sched_task(
                        0, msg.send_worker_messages, kwargs=kwargs,
                        name=(msg.worker.name + '.task'))
            for x in msg.additional_messages:
                if not self.send_message(x, **kwargs):  # pragma: debug
                    self.error("Error sending message iteration")
                    return False
            self._used = True
            if self.serializer.initialized:
                self._send_serializer = False
            if (msg.flag == FLAG_EOF) and self.close_on_eof_send:
                self.debug('Close on send EOF')
                self.linger_close()
                # self.close_in_thread(no_wait=True, timeout=False)
            return True
        except MetaschemaTypeError as e:  # pragma: debug
            self._type_errors.append(e)
            try:
                self.exception('Failed to send: %.100s.', str(msg.args))
            except ValueError:  # pragma: debug
                self.exception('Failed to send (unyt array in message)')
        except TemporaryCommunicationError if self.is_async else NeverMatch:
            if (msg.flag == FLAG_EOF) and self._used:
                with self._closing_thread.lock:
                    self._eof_sent.clear()
            raise
        except BaseException:
            # if (msg.flag == FLAG_EOF) and self._used:  # pragma: intermittent
            #     # This will only be called if the EOF send fails because
            #     # the receiving connection has already been closed (most
            #     # likely due to circular dependence).
            #     if self.close_on_eof_send:
            #         self.debug('Close on send EOF (send failed)')
            #         self.linger_close()
            #     return True
            # Handle error caused by calling repr on unyt array that isn't float64
            try:
                self.exception('Failed to send: %.100s.', str(msg.args))
            except ValueError:  # pragma: debug
                self.exception('Failed to send (unyt array in message)')
        return False

    def prepare_message(self, *args, header_kwargs=None, skip_serialization=False,
                        skip_processing=False, skip_language2python=False,
                        after_prepare_message=None):
        r"""Perform actions preparing to send a message. The order of steps is

            1. Convert the message based on the language
            2. Isolate the message if there is only one
            3. Check if the message is EOF
            4. Check if the message should be filtered
            5. Transform the message
            6. Apply after_prepare_message functions
            7. Serialize the message
            8. Create a work comm if the message is too large to be sent all at once

        Args:
            *args: Components of the outgoing message.
            header_kwargs (dict, optional): Header options that should be set.
            skip_serialization (bool, optional): If True, serialization will not
                be performed. Defaults to False.
            skip_processing (bool, optional): If True, filters, transformations, and
                after_prepare_message function applications will not be performed.
                Defaults to False.
            skip_language2python (bool, optional): If True, language2python will be
                skipped. Defaults to False.
            after_prepare_message (list, optional): Functions that should be applied
                after transformation, but before serialization. Defaults to None
                and is ignored.

        Returns:
            CommMessage: Serialized and annotated message.

        """
        if (len(args) == 1) and isinstance(args[0], CommMessage):
            msg = args[0]
            if header_kwargs:
                if msg.header is None:
                    msg.header = header_kwargs
                else:
                    msg.header = copy.deepcopy(msg.header)
                    msg.header.update(header_kwargs)
        else:
            model_name = self.full_model_name
            if model_name:
                if header_kwargs is None:
                    header_kwargs = {}
                header_kwargs.setdefault('model', model_name)
            msg = CommMessage(args=args, header=header_kwargs,
                              flag=FLAG_SUCCESS)
            # 1. Convert the message based on the language
            if not skip_language2python:
                msg.args = self.language_driver.language2python(msg.args)
            # 2. Isolate the message if there is only one
            if len(msg.args) == 1:
                msg.args = msg.args[0]
                msg.singular = True
            # 3. Check if the message is EOF
            if self.is_eof(msg.args):
                msg.flag = FLAG_EOF
                if self.partner_copies > 1:
                    for i in range(self.partner_copies - 1):
                        msg.add_message(args=msg.args,
                                        header=copy.deepcopy(msg.header))
        if not skip_processing:
            # 4. Check if the message should be filtered
            if msg.flag not in [FLAG_SKIP, FLAG_EOF]:
                if not self.evaluate_filter(*msg.tuple_args):
                    self.debug("Sent message skipped based on filter: %.100s",
                               str(msg.args))
                    msg.flag = FLAG_SKIP
                    return msg
            # 5. Transform the message
            if msg.flag not in [FLAG_SKIP, FLAG_EOF]:
                args = self.apply_transform(msg.args, header=msg.header)
                if isinstance(args, collections.abc.Iterator):
                    try:
                        msg.args = args.__next__()
                    except StopIteration:
                        msg.args = None
                        msg.flag = FLAG_SKIP
                        return msg
                    for iarg in args:
                        msg.add_message(args=iarg,
                                        header=copy.deepcopy(msg.header))
                else:
                    msg.args = args
                self.update_serializer_from_message(msg)
            # 6. Apply after_prepare_message function
            if after_prepare_message:
                for x in after_prepare_message:
                    msg = msg.apply_function(x)
        # Looping over all messages (allowing for transform to produce iterator)
        if (msg.flag not in [FLAG_SKIP]) and (not skip_serialization):
            for x in [msg] + msg.additional_messages:
                # 7. Serialize the message
                if self.no_serialization:
                    x.msg = x.args
                    x.length = 1
                    x.flag = FLAG_SUCCESS
                else:
                    if x.flag == FLAG_EOF:
                        if x.header:
                            x.msg = self.serialize(x.args, header_kwargs=x.header,
                                                   add_serializer_info=True)
                        else:
                            x.msg = x.args
                    else:
                        x.msg = self.serialize(x.args, header_kwargs=x.header)
                        x.flag = FLAG_SUCCESS
                    x.length = len(x.msg)
                # 8. Create a work comm if the message is too large to be sent all
                #    at once and re-serialize the message w/ the work comm info in it
                if (x.length > self.maxMsgSize) and (self.maxMsgSize != 0):
                    if x.flag == FLAG_EOF:  # pragma: debug
                        raise NotImplementedError(("EOF message with header (%d) "
                                                   "exceeds max message size (%d).")
                                                  % (msg.length, self.maxMsgSize))
                    if x.header is None:
                        x.header = dict()
                    x.worker = self.create_work_comm()
                    # if 'address' not in x.header:
                    #     x.worker = self.create_work_comm()
                    # else:
                    #     x.worker = self.get_work_comm(x.header)
                    x.header = self.workcomm2header(x.worker, **x.header)
                    total = self.serialize(x.args, header_kwargs=x.header)
                    x.msg = total[:self.maxMsgSize]
                    x.length = len(x.msg)
                    for imsg in self.chunk_message(total[self.maxMsgSize:]):
                        x.add_worker_message(msg=imsg, length=len(imsg))
        return msg

    def send(self, *args, **kwargs):
        r"""Send a message.

        Args:
            *args: All arguments are assumed to be part of the message.
            **kwargs: All keywords arguments are passed to prepare_message or
                send_message.

        Returns:
            bool: Success or failure of send.

        """
        self.precheck('send')
        kws_prepare = {k: kwargs.pop(k) for k in self._prepare_message_kws
                       if k in kwargs}
        msg = self.prepare_message(*args, **kws_prepare)
        return self.send_message(msg, **kwargs)

    def send_nolimit(self, *args, **kwargs):
        r"""Alias for send."""
        return self.send(*args, **kwargs)

    def send_eof(self, *args, **kwargs):
        r"""Send the EOF message as a short message.
        
        Args:
            *args: All arguments are passed to comm send.
            **kwargs: All keywords arguments are passed to comm send.

        Returns:
            bool: Success or failure of send.

        """
        return self.send(self.eof_msg, *args, **kwargs)

    # RECV METHODS
    def _safe_recv(self, timeout=None, **kwargs):
        r"""Safe receive that does things for all comm classes."""
        if timeout is None:
            timeout = self.recv_timeout
        Tout = self.start_timeout(timeout, key_suffix='._safe_recv')
        out = (True, self.empty_bytes_msg)
        error = None
        while (not Tout.is_out):
            error = None
            try:
                with self._closing_thread.lock:
                    if self.is_open:
                        out = self._recv(**kwargs)
                    else:
                        self.debug('Comm closed')
                        out = (False, self.empty_bytes_msg)
                    break
            except TemporaryCommunicationError as e:
                error = e
                self.periodic_debug("_safe_recv", period=1000)(
                    "TemporaryCommunicationError: %s" % e)
            self.sleep()
        self.stop_timeout(key_suffix='._safe_recv')
        if error and self.is_async:
            raise TemporaryCommunicationError(error)
        if out[0] and (not self.is_empty(out[1], self.empty_bytes_msg)):
            self._n_recv += 1
            self._last_recv = time.perf_counter()
        return out

    def _recv(self, *args, **kwargs):  # pragma: debug
        r"""Raw recv. Should be overridden by inheriting class."""
        raise IncompleteBaseComm("_recv method needs implemented.")

    def recv(self, *args, return_message_object=False, **kwargs):
        r"""Receive a message.

        Args:
            *args: All arguments are passed to comm _recv method.
            return_message_object (bool, optional): If True, the full wrapped
                CommMessage message object is returned instead of the tuple.
                Defaults to False.
            **kwargs: All keywords arguments are passed to comm _recv method.

        Returns:
            tuple (bool, obj): Success or failure of receive and received
                message. If return_message_object is True, the CommMessage object
                will be returned instead.

        """
        self.precheck('recv')
        kws_finalize = {k: kwargs.pop(k) for k in self._finalize_message_kws
                        if k in kwargs}
        msg = self.recv_message(*args, **kwargs)
        msg = self.finalize_message(msg, **kws_finalize)
        if msg.flag == FLAG_SKIP:
            kwargs['return_message_object'] = return_message_object
            kwargs.update(kws_finalize)
            return self.recv(*args, **kwargs)
        if return_message_object:
            out = msg
        else:
            out = (bool(msg.flag), msg.args)
        return out

    def recv_message(self, *args, skip_deserialization=False, **kwargs):
        r"""Receive a message.

        Args:
            *args: Arguments are passed to _safe_recv.
            skip_deserialization (bool, optional): If True, deserialization is not
                performed. Defaults to False.
            **kwargs: Additional keyword arguments are passed to _safe_recv.

        Returns:
            CommMessage: Received message.

        """
        no_serialization = (skip_deserialization or self.no_serialization)
        if self.is_closed:
            self.debug('Comm closed')
            return CommMessage(flag=FLAG_FAILURE)
        try:
            self.periodic_debug("recv_message", period=1000)(
                "Receiving message from %s" % self.address)
            flag, s_msg = self._safe_recv(*args, **kwargs)
            msg = CommMessage(msg=s_msg)
            if not flag:
                msg.flag = FLAG_FAILURE
                return msg
            if no_serialization:
                msg.args = msg.msg
                msg.header = {}
                if isinstance(msg.msg, bytes):
                    msg.header['size'] = len(msg.msg)
            else:
                msg.args, msg.header = self.deserialize(msg.msg)
            msg.flag = FLAG_SUCCESS
            if msg.header.get('incomplete', False):
                msg.msg = msg.args
                msg.worker = self.get_work_comm(msg.header)
                msg.flag = FLAG_INCOMPLETE
                while len(msg.msg) < msg.header['size']:
                    imsg = msg.worker.recv_message(skip_deserialization=True, **kwargs)
                    if imsg.flag in [FLAG_EOF, FLAG_FAILURE]:  # pragma: debug
                        self.error("Receive interupted at %d of %d bytes.",
                                   len(msg.msg), msg.header['size'])
                        msg.flag = FLAG_FAILURE
                        break
                    if imsg.flag == FLAG_SUCCESS:
                        msg.msg += imsg.msg
                self.debug("Received %d/%d bytes", len(msg.msg), msg.header['size'])
                if msg.flag in [FLAG_INCOMPLETE, FLAG_SUCCESS]:
                    msg.args = msg.msg
                    if not (no_serialization or msg.header.get('raw', False)):
                        msg.args, msg.header = self.deserialize(msg.msg,
                                                                metadata=msg.header)
                    msg.flag = FLAG_SUCCESS
                msg.worker.linger_close()
            if not no_serialization:
                self.update_message_from_serializer(msg)
        except TemporaryCommunicationError if self.is_async else NeverMatch:
            raise
        except BaseException:
            self.exception('Failed to recv.')
            self.close()
            return CommMessage(flag=FLAG_FAILURE)
        if isinstance(msg.msg, bytes):
            msg.length = len(msg.msg)
        else:
            msg.length = 1
        if msg.length == 0:
            msg.flag = FLAG_EMPTY
        if msg.flag == FLAG_SUCCESS:
            self.debug('%d bytes received from %s', msg.length, self.address)
        if self.is_eof(msg.args):
            msg.flag = FLAG_EOF
        msg.header['commtype'] = self._commtype
        return msg

    def finalize_message(self, msg, skip_processing=False,
                         skip_python2language=False, after_finalize_message=None):
        r"""Perform actions to decipher a message. The order of steps is

            1. Transform the message
            2. Filter
            3. python2language
            4. Close comm on EOF if close_on_eof_recv set
            5. Check for empty recv after processing
            6. Mark comm as used and close if single use
            7. Apply after_finalize_message functions

        Args:
            msg (CommMessage): Initial message object to be finalized.
            skip_processing (bool, optional): If True, filters, transformations,
                and after_finalize_message funciton applications will not be
                performed. Defaults to False.
            skip_python2language (bool, optional): If True, python2language will
                not be applied. Defaults to False.
            after_finalize_message (list, optional): A set of function that should
                be applied to received CommMessage objects following the standard
                finalization. Defaults to None and is ignored.

        Returns:
            CommMessage: Deserialized and annotated message.

        """
        if msg.finalized:
            return msg
        if not skip_processing:
            # 1. Transform the message
            if msg.flag == FLAG_SUCCESS:
                if msg.stype is not None:
                    msg.stype = self.apply_transform_to_type(msg.stype)
                msg.args = self.apply_transform(msg.args)
            # 2. Filter
            if (msg.flag == FLAG_SUCCESS) and (not self.evaluate_filter(msg.args)):
                msg.flag = FLAG_SKIP
            # 3. Perform python2language
            if (msg.flag in [FLAG_EOF, FLAG_SUCCESS]) and (not skip_python2language):
                msg.args = self.language_driver.python2language(msg.args)
        # 4. Close the comm on EOF
        if msg.flag == FLAG_EOF:
            self.debug("Received EOF")
            if self.close_on_eof_recv:
                self.debug("Lingering close on EOF Received")
                self.linger_close()
                msg.flag = FLAG_FAILURE
        # 5. Check for empty receive
        if (msg.flag == FLAG_SUCCESS) and (self.is_empty_recv(msg.args)):
            msg.flag = FLAG_EMPTY
        # if not (self.is_empty(msg.msg, self.empty_bytes_msg)
        #         or msg.header.get('incomplete', False)):
        # 6. Mark comm as used and close if single use
        if msg.flag in [FLAG_EOF, FLAG_SUCCESS]:
            self._used = True
        if self.single_use and self._used and self.is_open:
            self.debug('Linger close on single use')
            self.linger_close(active_confirm=self.is_async)
        # 7. Apply after_finalize_message functions
        if after_finalize_message:
            for x in after_finalize_message:
                msg = msg.apply_function(x)
        msg.finalized = True
        return msg

    def recv_nolimit(self, *args, **kwargs):
        r"""Alias for recv."""
        return self.recv(*args, **kwargs)

    def drain_server_signon_messages(self, **kwargs):
        r"""Drain server signon messages. This should only be used
        for testing purposes."""
        pass

    def drain_messages(self, direction=None, timeout=None, variable=None):
        r"""Sleep while waiting for messages to be drained."""
        self.debug('')
        if direction is None:
            direction = self.direction
        if variable is None:
            variable = 'n_msg_%s_drain' % direction
        if timeout is None:
            timeout = self._timeout_drain
        if not hasattr(self, variable):
            raise ValueError("No attribute named '%s'" % variable)
        Tout = self.start_timeout(timeout, key_suffix='.drain_messages')
        while (not Tout.is_out) and self.is_open:
            n_msg = getattr(self, variable)
            if n_msg == 0:
                break
            else:  # pragma: debug
                self.verbose_debug("Draining %d %s messages.",
                                   n_msg, variable)
                self.sleep()
        self.stop_timeout(key_suffix='.drain_messages')
        self.debug('Done draining')

    def purge(self):
        r"""Purge all messages from the comm."""
        if self.direction == 'recv':
            while self.n_msg_recv > 0:  # pragma: debug
                self.recv(skip_deserialization=True)
        self._n_sent = 0
        self._n_recv = 0
        self._last_send = None
        self._last_recv = None

    # Send/recv dictionary of fields
    def send_dict(self, args_dict, **kwargs):
        r"""Send a message with fields specified in the input dictionary.

        Args:
            args_dict (dict): Dictionary of arguments to send.
            **kwargs: Additiona keyword arguments are passed to send.

        Returns:
            bool: Success/failure of send.

        Raises:
            RuntimeError: If the field order can not be determined.

        """
        from yggdrasil.metaschema.datatypes.JSONArrayMetaschemaType import (
            JSONArrayMetaschemaType)
        metadata = kwargs.get('header_kwargs', {})
        if 'field_order' in kwargs:
            kwargs.setdefault('key_order', kwargs.pop('field_order'))
        if 'key_order' in kwargs:
            metadata['key_order'] = kwargs.pop('key_order')
        metadata.setdefault('key_order', self.serializer.get_field_names())
        if (((metadata['key_order'] is None)
             and isinstance(args_dict, dict)
             and (len(args_dict) <= 1))):
            metadata['key_order'] = [k for k in args_dict.keys()]
        if not self.serializer.initialized:
            metadata['field_names'] = metadata['key_order']
        args = JSONArrayMetaschemaType.coerce_type(args_dict, **metadata)
        # Add field order to kwargs so it can be reconstructed
        kwargs['header_kwargs'] = metadata
        return self.send(*args, **kwargs)

    def recv_dict(self, *args, **kwargs):
        r"""Return a received message as a dictionary of fields. If there are
        not any fields specified, the fields will have the form 'f0', 'f1',
        'f2', ...

        Args:
            *args: Arguments are passed to recv.
            **kwargs: Keyword arguments are passed to recv.

        Returns:
            tuple(bool, dict): Success/failure of receive and a dictionar of
                message fields.

        Raises:

        """
        from yggdrasil.metaschema.datatypes.JSONObjectMetaschemaType import (
            JSONObjectMetaschemaType)
        if 'field_order' in kwargs:
            kwargs.setdefault('key_order', kwargs.pop('field_order'))
        key_order = kwargs.pop('key_order', None)
        return_message_object = kwargs.pop('return_message_object', False)
        kwargs['return_message_object'] = True
        msg = self.recv(*args, **kwargs)
        if msg.flag == FLAG_SUCCESS:
            if self.serializer.typedef['type'] == 'array':
                metadata = copy.deepcopy(msg.header)
                # if metadata is None:
                #     metadata = {}
                if key_order is not None:
                    metadata['key_order'] = key_order
                metadata.setdefault('key_order', self.serializer.get_field_names())
                msg_dict = JSONObjectMetaschemaType.coerce_type(msg.args, **metadata)
            else:
                msg_dict = {'f0': msg.args}
        else:
            msg_dict = msg.args
        out = copy.deepcopy(msg)
        out.args = msg_dict
        if not return_message_object:
            out = (bool(out.flag), out.args)
        return out

    # SEND/RECV FIELDS
    # def recv_field(self, field, *args, **kwargs):
    #     r"""Receive an entry for a single field.

    #     Args:
    #         field (str): Name of the field that should be received.
    #         *args: All arguments are passed to recv method if there is not
    #             an existing entry for the requested field.
    #         **kwargs: All keyword arguments are passed to recv method if there
    #             is not an existing entry for the requested field.

    #     Returns:
    #         tuple (bool, obj): Success or failure of receive and received
    #             field entry.

    #     """
    #     flag = True
    #     field_msg = self.empty_obj_recv
    #     if not self._field_backlog.get(field, []):
    #         flag, msg = self.recv_dict(*args, **kwargs)
    #         if self.is_eof(msg):
    #             for k in self.fields:
    #                 self._field_backlog.setdefault(k, [])
    #                 self._field_backlog[k].append(msg)
    #         elif not self.is_empty_recv(msg):
    #             for k, v in msg.items():
    #                 self._field_backlog.setdefault(k, [])
    #                 self._field_backlog.append(v)
    #     if self._field_backlog.get(field, []):
    #         field_msg = self._field_backlog[field].pop(0)
    #     return flag, field_msg

    # ALIASES
    def send_array(self, *args, **kwargs):
        r"""Alias for send."""
        # TODO: Maybe explicitly handle transformation from array
        return self.send(*args, **kwargs)

    def recv_array(self, *args, **kwargs):
        r"""Alias for recv."""
        flag, out = self.recv(*args, **kwargs)
        if flag:
            if self.transform:
                dtype = type2numpy(self.transform[-1].transformed_datatype)
                if dtype and isinstance(out, (list, tuple, np.ndarray)):
                    out = consolidate_array(out, dtype=dtype)
            else:
                out = self.serializer.consolidate_array(out)
        return flag, out
