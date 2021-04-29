import os
import tempfile
import uuid
import logging
from yggdrasil import tools
from yggdrasil import multitasking
from yggdrasil.communication import (
    CommBase, TemporaryCommunicationError, NoMessages)
logger = logging.getLogger(__name__)
try:
    import zmq
    _zmq_installed = True
except ImportError:  # pragma: debug
    logger.debug("Could not import pyzmq. "
                 + "ZMQ support will be disabled.")
    zmq = None
    _zmq_installed = False


_socket_type_pairs = [('PUSH', 'PULL'),
                      ('PUB', 'SUB'),
                      ('REP', 'REQ'),
                      ('ROUTER', 'DEALER'),
                      ('PAIR', 'PAIR')]
_socket_send_types = [t[0] for t in _socket_type_pairs]
_socket_recv_types = [t[1] for t in _socket_type_pairs]
_socket_protocols = ['tcp', 'inproc', 'ipc', 'udp', 'pgm', 'epgm']
_flag_zmq_filter = b'_ZMQFILTER_'
_default_socket_type = 4
_default_protocol = 'tcp'
_wait_send_t = 0  # 0.0001
_reply_msg = b'YGG_REPLY'
_purge_msg = b'YGG_PURGE'


def set_context_opts(context):
    context.set(zmq.MAX_SOCKETS, 8000)
    context.setsockopt(zmq.LINGER, 0)
    context.setsockopt(zmq.IMMEDIATE, 0)


if _zmq_installed:
    _global_context = zmq.Context.instance()
    set_context_opts(_global_context)
else:  # pragma: debug
    _global_context = None


def get_ipc_host():
    r"""Get an IPC host using uuid.

    Returns:
        str: File path for IPC transport created using uuid.

    """
    return os.path.join(tempfile.gettempdir(), str(uuid.uuid4()) + '.ipc')

        
def get_socket_type_mate(t_in):
    r"""Find the counterpart socket type.

    Args:
        t_in (str): Socket type.

    Returns:
        str: Counterpart socket type.

    Raises:
        ValueError: If t_in is not a recognized socket type.

    """
    if t_in in _socket_send_types:
        for t in _socket_type_pairs:
            if t[0] == t_in:
                return t[1]
    elif t_in in _socket_recv_types:
        for t in _socket_type_pairs:
            if t[1] == t_in:
                return t[0]
    else:
        raise ValueError('Could not locate socket type %s' % t_in)


def format_address(protocol, host, port=None, partner_mpi_ranks=[]):
    r"""Format an address based on its parts.

    Args:
        protocol (str): Communication protocol that should be used.
        host (str): Host that address should point to.
        port (int, optional): Port that address should point to. Defaults to
            None and is not added to the address.
        partner_mpi_ranks (list, optional): Ranks of processes of this comm's
            partner comm(s). Defaults to [].

    Returns:
        str: Complete address.

    Raises:
        ValueError: If the protocol is not recognized.

    """
    if host == 'localhost':
        host = '127.0.0.1'
        if multitasking._mpi_rank >= 0:
            for x in partner_mpi_ranks:
                if x != multitasking._mpi_rank:
                    assert(protocol not in ['inproc', 'ipc'])
                    # TODO: Get address from config
                    logger.error("TODO: Get full address from config")
    if protocol in ['inproc', 'ipc']:
        address = "%s://%s" % (protocol, host)
    elif protocol not in _socket_protocols:
        raise ValueError("Unrecognized protocol: %s" % protocol)
    else:
        address = "%s://%s" % (protocol, host)
        if port is not None:
            address += ":%d" % port
    return address

                    
def parse_address(address):
    r"""Split an address into its parts.

    Args:
        address (str): Address to be split.

    Returns:
        dict: Parameters extracted from the address.

    Raises:
        ValueError: If the address dosn't contain '://'.
        ValueError: If the protocol is not supported.

    """
    if '://' not in address:
        raise ValueError("Address must contain '://' (address provided = '%s')"
                         % address)
    protocol, res = address.split('://')
    if protocol not in _socket_protocols:
        raise ValueError("Protocol '%s' not supported." % protocol)
    if protocol in ['inproc', 'ipc']:
        host = res
        port = protocol
    else:
        if ':' in res:
            host, port = res.split(':')
            port = int(port)
        else:
            host = res
            port = None
    out = dict(protocol=protocol, host=host, port=port)
    return out


def create_socket(context, socket_type):
    r"""Create a socket w/ some default options to improve cleanup.

    Args:
        context (zmq.Context): ZeroMQ context.
        socket_type (int): ZeroMQ socket type.

    Returns:
        zmq.Socket: New socket.

    """
    socket = context.socket(socket_type)
    socket.setsockopt(zmq.LINGER, 0)
    return socket


def bind_socket(socket, address, retry_timeout=-1, nretry=1):
    r"""Bind a socket to an address, getting a random port as necessary.

    Args:
        socket (zmq.Socket): Socket that should be bound.
        address (str): Address that socket should be bound to.
        retry_timeout (float, optional): Time (in seconds) that should be
            waited before retrying to bind the socket to the address. If
            negative, a retry will not be attempted and an error will be
            raised. Defaults to -1.
        nretry (int, optional): Number of times to try binding the socket to
            the addresses. Defaults to 1.

    Returns:
        str: Address that socket was bound to, including random port if one
            was used.

    """
    try:
        param = parse_address(address)
        if (param['protocol'] in ['inproc', 'ipc']) or (param['port'] is not None):
            socket.bind(address)
        else:
            port = socket.bind_to_random_port(address)
            address += ":%d" % port
    except zmq.ZMQError as e:  # pragma: debug
        if (retry_timeout < 0) or (nretry == 0):
            # if (e.errno not in [48, 98]) or (retry_timeout < 0):
            # print(e, e.errno)
            raise e
        else:
            logger.debug("Retrying bind in %f s", retry_timeout)
            tools.sleep(retry_timeout)
            address = bind_socket(socket, address, nretry=nretry - 1,
                                  retry_timeout=retry_timeout)
    return address

    
class ZMQProxy(CommBase.CommServer):
    r"""Start a proxy in a new thread for a server address. A client-side
    address will be randomly generated.

    Args:
        srv_address (str): Address that should face the server(s).
        context (zmq.Context, optional): ZeroMQ context that should be used.
            Defaults to None and the global context is used.
        protocol (str, optional): Protocol that should be used for the sockets.
            Defaults to None and is set to _default_protocol.
        host (str, optional): Host for socket address. Defaults to 'localhost'.
        retry_timeout (float, optional): Time (in seconds) that should be
            waited before retrying to bind the sockets to the addresses. If
            negative, a retry will not be attempted and an error will be
            raised. Defaults to -1.
        nretry (int, optional): Number of times to try binding the sockets to
            the addresses. Defaults to 1.
        partner_mpi_ranks (list, optional): Ranks of processes of this comm's
            partner comm(s). Defaults to [].
        **kwargs: Additional keyword arguments are passed to the parent class.

    Attributes:
        srv_address (str): Address that faces the server(s).
        cli_address (str): Address that faces the client(s).
        context (zmq.Context): ZeroMQ context that will be used.
        srv_socket (zmq.Socket): Socket facing client(s).
        cli_socket (zmq.Socket): Socket facing server(s).
        cli_count (int): Number of clients that have connected to this proxy.

    """

    server_signon_msg = b'ZMQ_SERVER_SIGNING_ON::'
    # server_signoff_msg = b'ZMQ_SERVER_SIGNING_OFF::'
    
    def __init__(self, srv_address, zmq_context=None, retry_timeout=-1,
                 nretry=1, partner_mpi_ranks=[], **kwargs):
        # Get parameters
        srv_param = parse_address(srv_address)
        cli_param = dict()
        for k in ['protocol', 'host', 'port']:
            cli_param[k] = kwargs.pop(k, srv_param[k])
        zmq_context = zmq_context or _global_context
        # Create new address for the frontend
        if cli_param['protocol'] in ['inproc', 'ipc']:
            cli_param['host'] = get_ipc_host()
        cli_address = format_address(cli_param['protocol'], cli_param['host'],
                                     partner_mpi_ranks=partner_mpi_ranks)
        self.cli_socket = create_socket(zmq_context, zmq.ROUTER)
        self.cli_address = bind_socket(self.cli_socket, cli_address,
                                       nretry=nretry,
                                       retry_timeout=retry_timeout)
        self.nsignon = 0
        ZMQComm.register_comm('ROUTER_server_' + self.cli_address,
                              self.cli_socket)
        # Bind backend
        self.srv_socket = create_socket(zmq_context, zmq.DEALER)
        try:
            self.srv_address = bind_socket(self.srv_socket, srv_address,
                                           nretry=nretry,
                                           retry_timeout=retry_timeout)
        except zmq.ZMQError:  # pragma: debug
            self.cli_socket.close()
            self.cli_socket = None
            CommBase.unregister_comm(
                'ZMQComm', 'ROUTER_server_' + self.cli_address)
            raise
        ZMQComm.register_comm('DEALER_server_' + self.srv_address,
                              self.srv_socket)
        # Set up poller
        # self.poller = zmq.Poller()
        # self.poller.register(frontend, zmq.POLLIN)
        self.reply_socket = None
        # Set name
        self.backlog = []
        self.server_active = False
        super(ZMQProxy, self).__init__(self.srv_address, self.cli_address, **kwargs)
        self._name = 'ZMQProxy.%s.to.%s' % (cli_address, srv_address)

    def client_recv(self):
        r"""Receive single message from the client."""
        with self.lock:
            if self.was_break:  # pragma: debug
                return None
            if self.backlog and self.server_active:
                return self.backlog.pop(0)
            msg = self.cli_socket.recv_multipart()
            if msg[1].startswith(self.server_signon_msg):
                self.debug(("A server has signed on after %d attempts, "
                            "activating proxy.") % self.nsignon)
                self.server_active = True
                return None
            # if msg[1].startswith(self.server_signoff_msg):
            #     self.sleep(1.0)
            #     return None
            if not self.server_active:
                self.debug("Backlogging message")
                self.backlog.append(msg)
                return None
            return msg

    def server_send(self, msg):
        r"""Send single message to the server."""
        if msg is None:  # pragma: debug
            return
        while not self.was_break:
            try:
                self.srv_socket.send(msg, zmq.NOBLOCK)
                break
            except zmq.ZMQError:  # pragma: no cover
                self.sleep(0.0001)

    def poll(self):
        # socks = dict(self.poller.poll())
        # return (socks.get(self.cli_socket) == zmq.POLLIN)
        with self.lock:
            if self.was_break:  # pragma: debug
                return False
        if self.backlog and self.server_active:
            return True
        out = self.cli_socket.poll(timeout=1, flags=zmq.POLLIN)
        return (out == zmq.POLLIN)

    def run_loop(self):
        r"""Forward messages from client to server."""
        if self.poll():
            message = self.client_recv()
            if message is not None:
                self.debug('Forwarding message of size %d from %s',
                           len(message[1]), message[0])
                self.server_send(message[1])
        if (not self.server_active):
            self.nsignon += 1
            self.server_send(self.server_signon_msg + self.cli_address.encode('utf-8'))
            self.sleep()

    def after_loop(self):
        r"""Close sockets after the loop finishes."""
        self.cleanup()
        super(ZMQProxy, self).after_loop()

    def cleanup(self):
        r"""Clean up sockets on exit."""
        self.close_sockets()
        super(ZMQProxy, self).cleanup()

    def close_sockets(self):
        r"""Close the sockets."""
        self.debug('Closing sockets')
        if self.cli_socket:
            self.cli_socket.close()
            self.cli_socket = None
        if self.srv_socket:
            self.srv_socket.close()
            self.srv_socket = None
        ZMQComm.unregister_comm('ROUTER_server_' + self.cli_address)
        ZMQComm.unregister_comm('DEALER_server_' + self.srv_address)


class ZMQComm(CommBase.CommBase):
    r"""Class for handling I/O using ZeroMQ sockets.

    Args:
        name (str): The environment variable where the socket address is
            stored.
        context (zmq.Context, optional): ZeroMQ context that should be used.
            Defaults to None and the global context is used.
        socket_type (str, optional): The type of socket that should be created.
            Defaults to _default_socket_type. See zmq for all options.
        socket_action (str, optional): The action that the socket should perform.
            Defaults to action based on the direction ('connect' for 'recv',
            'bind' for 'send'.)
        topic_filter (str, optional): Message filter to use when subscribing.
            This is only used for 'SUB' socket types. Defaults to '' which is
            all messages.
        dealer_identity (str, optional): Identity that should be used to route
            messages to a dealer socket. Defaults to '0'.
        **kwargs: Additional keyword arguments are passed to :class:.CommBase.

    Attributes:
        context (zmq.Context): ZeroMQ context that will be used.
        socket (zmq.Socket): ZeroMQ socket.
        socket_type_name (str): The type of socket that should be created.
        socket_type (int): ZeroMQ socket type.
        socket_action (str, optional): The action that the socket should perform.
        topic_filter (str): Message filter to use when subscribing.
        dealer_identity (str): Identity that should be used to route messages
            to a dealer socket.

    Developer Notes:
        |yggdrasil| uses the tcp transport by default with a PAIR socket type.
        For every connection, |yggdrasil| establishes a second request/reply
        connection that is used to confirm messages passed between the primary
        PAIR of sockets. On the first send, the model should create a REP socket
        on an open tcp address and send that address in the header of the first
        message under the key 'zmq_reply'. Receiving models should check
        message headers for this key and, on receipt, establish the partner
        REQ socket with the specified address (receiving comms can receive from
        more than one source so they can have more than one request addresses at
        at time for this purpose). Following every message, the sending model
        should wait for a message on the reply socket and, on receipt, return
        the message. Following every message, the receiving model should send
        the message 'YGG_REPLY' on the request socket and wait for a reply.
        When creating worker comms for sending large messages, the sending
        model should create the reply comm for the worker in advanced and send
        it in the header with the worker address under the key 'zmq_reply_worker'.

    """

    _commtype = 'zmq'
    _schema_subtype_description = ('ZeroMQ socket.')
    # Based on limit of 32bit int, this could be 2**30, but this is
    # too large for stack allocation in C so 2**20 will be used.
    _maxMsgSize = 2**20
    address_description = ("A ZeroMQ endpoint of the form "
                           "<transport>://<address>, where the format of "
                           "address depends on the transport. "
                           "Additional information can be found "
                           "`here <http://api.zeromq.org/3-2:zmq-bind>`_.")
    _disconnect_attr = (CommBase.CommBase._disconnect_attr
                        + ['reply_socket_lock', 'socket_lock',
                           '_reply_thread'])
    
    def _init_before_open(self, context=None, socket_type=None,
                          socket_action=None, topic_filter='',
                          dealer_identity=None, new_process=False,
                          reply_socket_address=None, **kwargs):
        r"""Initialize defaults for socket type/action based on direction."""
        self.reply_socket_lock = multitasking.RLock()
        self.socket_lock = multitasking.RLock()
        self._reply_thread = None
        # Client/Server things
        if self.allow_multiple_comms:
            socket_type = 'DEALER'
            if self.create_proxy or self.is_interface:
                socket_action = 'connect'
            else:
                socket_action = 'bind'
        if self.is_client:
            socket_type = 'DEALER'
            socket_action = 'connect'
            self.direction = 'send'
        elif self.is_server:
            socket_type = 'DEALER'
            socket_action = 'connect'
            self.direction = 'recv'
        elif ((self.is_response_client or self.is_response_server)
              and (self.direction == 'recv')):
            socket_type = 'ROUTER'
            socket_action = 'bind'
        elif ((self.is_response_client or self.is_response_server)
              and (self.direction == 'send')):
            # The would be the RPCResponseDriver output comm that
            # partners with the ClientComm response comm that is set
            # to use a ROUTER socket type as defined above
            socket_type = 'DEALER'
            socket_action = 'connect'
        # Set defaults
        if socket_type is None:
            if self.direction == 'recv':
                socket_type = _socket_recv_types[_default_socket_type]
            elif self.direction == 'send':
                socket_type = _socket_send_types[_default_socket_type]
        if not (self.allow_multiple_comms or self.is_client or self.is_server
                or self.is_response_client or self.is_response_server):
            if socket_type in ['PULL', 'SUB', 'REP', 'DEALER']:
                self.direction = 'recv'
            elif socket_type in ['PUSH', 'PUB', 'REQ', 'ROUTER']:
                self.direction = 'send'
        if socket_action is None:
            if self.port in ['inproc', 'ipc']:
                if socket_type in ['PULL', 'SUB', 'REQ', 'DEALER']:
                    socket_action = 'connect'
                elif socket_type in ['PUSH', 'PUB', 'REP', 'ROUTER']:
                    socket_action = 'bind'
                else:
                    if self.direction == 'recv':
                        socket_action = 'connect'
                    elif self.direction == 'send':
                        socket_action = 'bind'
            elif self.port is None:
                socket_action = 'bind'
            else:
                socket_action = 'connect'
        if new_process:
            self.context = zmq.Context()
            set_context_opts(self.context)
        else:
            self.context = context or _global_context
        self.socket_type_name = socket_type
        self.socket_type = getattr(zmq, socket_type)
        self.socket_action = socket_action
        self.socket = create_socket(self.context, self.socket_type)
        self.topic_filter = tools.str2bytes(topic_filter)
        if dealer_identity is None:
            dealer_identity = str(uuid.uuid4())
        self.dealer_identity = tools.str2bytes(dealer_identity)
        self._openned = False
        self._bound = False
        self._connected = False
        self._recv_identities = set([])
        # Reply socket attributes
        self.zmq_sleeptime = int(10000 * self.sleeptime)
        self.reply_socket_address = reply_socket_address
        self.reply_socket_send = None
        self.reply_socket_recv = {}
        self._n_zmq_sent = 0
        self._n_zmq_recv = {}
        self._n_reply_sent = 0
        self._n_reply_recv = {}
        self._server_class = ZMQProxy
        self._server_kwargs = dict(zmq_context=self.context,
                                   nretry=4, retry_timeout=2.0 * self.sleeptime,
                                   partner_mpi_ranks=self.partner_mpi_ranks)
        self.cli_address = None
        self.cli_socket = None
        super(ZMQComm, self)._init_before_open(**kwargs)

    def __getstate__(self):
        if self._bound:
            self.unbind()
            self._bound = True
        state = super(ZMQComm, self).__getstate__()
        del state['context']
        state['_server_kwargs'].pop('zmq_context', None)
        # del state['_server_kwargs']['zmq_context']
        del state['socket']
        return state

    def __setstate__(self, state):
        state['context'] = zmq.Context()
        state['_server_kwargs']['zmq_context'] = state['context']
        super(ZMQComm, self).__setstate__(state)
        self.socket = create_socket(self.context, self.socket_type)
        if self._bound:
            self._bound = False
            self.bind()
        
    def get_status_message(self, nindent=0, **kwargs):
        r"""Return lines composing a status message.
        
        Args:
            nindent (int, optional): Number of tabs that should be used to
                indent each line. Defaults to 0.
            **kwargs: Additional keyword arguments are passed to the
                parent class's method.
                
        Returns:
            tuple(list, prefix): Lines composing the status message and the
                prefix string used for the last message.

        """
        lines, prefix = super(ZMQComm, self).get_status_message(
            nindent=nindent, **kwargs)
        lines += ['%s%-15s: %s' % (prefix, 'nsent (zmq)', self._n_zmq_sent),
                  '%s%-15s: %s' % (prefix, 'nsent reply (zmq)', self._n_reply_sent)]
        for k in self._n_zmq_recv.keys():
            lines += ['%s%-15s: %s' % (prefix, 'nrecv (%s)' % k, self._n_zmq_recv[k]),
                      '%s%-15s: %s' % (prefix, 'nrecv reply (%s)' % k,
                                       self._n_reply_recv[k])]
        return lines, prefix

    @property
    def reply_thread(self):
        r"""tools.YggTask: Task that will handle sending or receiving
        backlogged messages."""
        if (self._reply_thread is None) and (not self.is_async):
            def reply_target():
                if self.is_closed:
                    if self.direction == 'send':
                        with self.reply_socket_lock:
                            if (((self._n_zmq_sent != self._n_reply_sent)
                                 and (self.reply_socket_send is not None)
                                 and (not self.reply_socket_send.closed))):
                                self._reply_handshake_send()  # pragma: intermittent
                        self._close_backlog(wait=True)
                    raise multitasking.BreakLoopException("Comm closed")
                if self.direction == 'send':
                    self.confirm_send()
                else:
                    self.confirm_recv()
                self.sleep()
            self._reply_thread = CommBase.CommTaskLoop(
                self, target=reply_target, suffix='Reply')
        return self._reply_thread
    
    @classmethod
    def close_registry_entry(cls, value):
        r"""Close a registry entry."""
        out = False
        if not value.closed:
            value.close(linger=0)
            out = True
        return out

    @property
    def address_param(self):
        r"""dict: Address parameters."""
        return parse_address(self.address)

    @property
    def protocol(self):
        r"""str: Protocol that socket uses."""
        return self.address_param['protocol']

    @property
    def host(self):
        r"""str: Host that socket is connected to."""
        return self.address_param['host']

    @property
    def port(self):
        r"""str: Port that socket is connected to."""
        return self.address_param['port']

    @classmethod
    def new_comm_kwargs(cls, name, protocol=None, host=None, port=None,
                        partner_mpi_ranks=[], **kwargs):
        r"""Initialize communication with new queue.

        Args:
            name (str): Name of new socket.
            protocol (str, optional): The protocol that should be used.
                Defaults to None and is set to _default_protocol. See zmq for
                details.
            host (str, optional): The host that should be used. Invalid for
                'inproc' protocol. Defaults to 'localhost'.
            port (int, optional): The port used. Invalid for 'inproc' protocol.
                Defaults to None and a random port is choosen.
            partner_mpi_ranks (list, optional): Ranks of processes of this comm's
                partner comm(s). Defaults to [].
            **kwargs: Additional keywords arguments are returned as keyword
                arguments for the new comm.

        Returns:
            tuple(tuple, dict): Arguments and keyword arguments for new socket.

        """
        args = [name]
        if protocol is None:
            protocol = _default_protocol
        if host is None:
            if protocol in ['inproc', 'ipc']:
                host = get_ipc_host()
            else:
                host = 'localhost'
        if 'address' not in kwargs:
            kwargs['address'] = format_address(protocol, host, port=port,
                                               partner_mpi_ranks=partner_mpi_ranks)
        return args, kwargs

    @property
    def opp_address(self):
        r"""str: Address for opposite comm."""
        if self.create_proxy:
            if self._server is None:  # pragma: debug
                raise Exception("The proxy does not yet have an address.")
            if self.direction == 'send':
                return self._server.srv_address
            else:  # pragma: debug
                # return self._server.cli_address
                raise RuntimeError("Receive-side proxy untested")
        else:
            return self.address

    def opp_comm_kwargs(self):
        r"""Get keyword arguments to initialize communication with opposite
        comm object.

        Returns:
            dict: Keyword arguments for opposite comm object.

        """
        kwargs = super(ZMQComm, self).opp_comm_kwargs()
        kwargs['socket_type'] = get_socket_type_mate(self.socket_type_name)
        if self.is_client:
            kwargs['is_server'] = True
        elif self.is_server:
            kwargs['is_client'] = True
        if kwargs['socket_type'] in ['DEALER', 'ROUTER']:
            kwargs['dealer_identity'] = self.dealer_identity
        kwargs['context'] = self.context
        return kwargs

    @property
    def registry_key(self):
        r"""str: String used to register the socket."""
        return '%s_%s_%s' % (self.socket_type_name, self.address, self.direction)

    def bind(self):
        r"""Bind to address, getting random port as necessary."""
        super(ZMQComm, self).bind()
        if self.is_open or self._bound or self._connected:  # pragma: debug
            return
        # Bind to reserve port if that is this sockets action
        with self.socket_lock:
            if (self.socket_action == 'bind') or (self.port is None):
                self._bound = True
                self.debug('Binding %s socket to %s.',
                           self.socket_type_name, self.address)
                try:
                    self.address = bind_socket(self.socket, self.address,
                                               retry_timeout=self.sleeptime,
                                               nretry=2)
                except zmq.ZMQError as e:
                    if (self.socket_type_name == 'PAIR') and (e.errno == 98):
                        self.error(("There is already a 'PAIR' socket sending "
                                    + "to %s. Maybe you meant to create a recv "
                                    + "PAIR?") % self.address)
                    self._bound = False
                    raise e
                self.debug('Bound %s socket to %s.',
                           self.socket_type_name, self.address)
                # Unbind if action should be connect
                if self.socket_action == 'connect':
                    self.unbind(dont_close=True)
            else:
                self._bound = False
            if self._bound:
                self.register_comm(self.registry_key, self.socket)

    def connect(self):
        r"""Connect to address."""
        if self.is_open or self._bound or self._connected:  # pragma: debug
            return
        with self.socket_lock:
            if (self.socket_action == 'connect'):
                self._connected = True
                self.debug("Connecting %s socket to %s",
                           self.socket_type_name, self.address)
                self.socket.connect(self.address)
            if self._connected:
                self.register_comm(self.registry_key, self.socket)

    def unbind(self, dont_close=False):
        r"""Unbind from address."""
        with self.socket_lock:
            if self._bound:
                self.debug('Unbinding from %s' % self.address)
                try:
                    self.socket.unbind(self.address)
                except zmq.ZMQError:  # pragma: debug
                    pass
                self.unregister_comm(self.registry_key, dont_close=dont_close)
                self._bound = False
            self.debug('Unbound socket')

    def disconnect(self, dont_close=False):
        r"""Disconnect from address."""
        if not hasattr(self, 'socket_lock'):
            return
        with self.socket_lock:
            if self._connected:
                self.debug('Disconnecting from %s' % self.address)
                try:
                    self.socket.disconnect(self.address)
                except zmq.ZMQError:  # pragma: debug
                    pass
                self.unregister_comm(self.registry_key, dont_close=dont_close)
                self._connected = False
            self.debug('Disconnected socket')

    def open(self):
        r"""Open connection by binding/connect to the specified socket."""
        super(ZMQComm, self).open()
        with self.socket_lock:
            if not self.is_open:
                # Set dealer identity
                if self.socket_type_name == 'DEALER':
                    self.socket.setsockopt(zmq.IDENTITY, self.dealer_identity)
                # Bind/connect
                if self.socket_action == 'bind':
                    self.bind()
                elif self.socket_action == 'connect':
                    # Bind then unbind to get port as necessary
                    self.bind()
                    self.unbind(dont_close=True)
                    self.connect()
                # Set topic filter
                if self.socket_type_name == 'SUB':
                    self.socket.setsockopt(zmq.SUBSCRIBE, self.topic_filter)
                self._openned = True
            if (not self.is_async) and (not self.reply_thread.is_alive()):
                self.reply_thread.start()

    def set_reply_socket_send(self):
        r"""Set the send reply socket if it dosn't exist."""
        if self.reply_socket_send is None:
            s = create_socket(self.context, zmq.REP)
            s.setsockopt(zmq.IMMEDIATE, 1)
            address = format_address(_default_protocol, 'localhost',
                                     partner_mpi_ranks=self.partner_mpi_ranks)
            address = bind_socket(s, address)
            self.register_comm('REPLY_SEND_' + address, s)
            with self.reply_socket_lock:
                self.reply_socket_send = s
                self.reply_socket_address = address
            self.debug("new send address: %s", address)
        return self.reply_socket_address

    def set_reply_socket_recv(self, address):
        r"""Set the recv reply socket if the address dosn't exist."""
        address = tools.bytes2str(address)
        if address not in self.reply_socket_recv:
            s = create_socket(self.context, zmq.REQ)
            s.setsockopt(zmq.IMMEDIATE, 1)
            s.connect(address)
            self.register_comm('REPLY_RECV_' + address, s)
            with self.reply_socket_lock:
                self._n_reply_recv[address] = 0
                self._n_zmq_recv[address] = 0
                self.reply_socket_recv[address] = s
            self.debug("new recv address: %s", address)
        return address

    def check_reply_socket_send(self, msg):
        r"""Append reply socket address if it

        Args:
            msg (str): Message that will be piggy backed on.

        Returns:
            str: Message with reply address if it has not been sent.


        """
        return msg
        
    def check_reply_socket_recv(self, msg):
        r"""Check incoming message for reply address.

        Args:
            msg (str): Incoming message to check.

        Returns:
            str: Messages with reply address removed if present.

        """
        assert(self.direction != 'send')
        # if self.direction == 'send':
        #     return msg, None
        header = self.serializer.parse_header(msg.split(_flag_zmq_filter)[-1])
        address = header.get('zmq_reply', None)
        if (address is None):
            address = self.reply_socket_address
        if address is not None:
            self.set_reply_socket_recv(address)
        return msg, address

    def _catch_eagain(self, function, *args, **kwargs):
        tries = 10
        error = BaseException('_catch_eagain')
        while (tries > 0):
            try:
                return function(*args, **kwargs)
            except zmq.ZMQError as e:  # pragma: debug
                if e.errno == zmq.EAGAIN:
                    tries -= 1
                    error = e
                    self.sleep()
                    continue
                raise
        raise error  # pragma: debug

    def _reply_handshake_send(self):
        r"""Do send side of handshake."""
        if (((self.reply_socket_send is None)
             or self.reply_socket_send.closed)):  # pragma: debug
            raise multitasking.BreakLoopException("SOCKET CLOSED")
        out = self.reply_socket_send.poll(timeout=1, flags=zmq.POLLIN)
        if out == 0:
            self.periodic_debug('_reply_handshake_send', period=1000)(
                'No reply handshake waiting')
            return False
        try:
            msg = self._catch_eagain(self.reply_socket_send.recv,
                                     flags=zmq.NOBLOCK)
        except zmq.ZMQError:  # pragma: debug
            self.periodic_debug('_reply_handshake_send', period=1000)(
                'Error receiving handshake.')
            return False
        if self.is_eof(msg):  # pragma: debug
            self.error("REPLY EOF RECV'D")
            return msg
        self._catch_eagain(self.reply_socket_send.send,
                           msg, flags=zmq.NOBLOCK)
        self._n_reply_sent += 1
        self.reply_socket_send.poll(timeout=self.zmq_sleeptime,
                                    flags=zmq.POLLIN)
        return msg

    def _reply_handshake_recv(self, msg_send, key):
        r"""Do recv side of handshake."""
        socket = self.reply_socket_recv.get(key, None)
        if socket is None or socket.closed:  # pragma: debug
            raise multitasking.BreakLoopError("SOCKET CLOSED: %s" % key)
        out = socket.poll(timeout=1, flags=zmq.POLLOUT)
        if out == 0:  # pragma: debug
            self.periodic_debug('_reply_handshake_recv', period=1000)(
                'Cannot initiate reply handshake')
            return False
        try:
            self._catch_eagain(socket.send, msg_send, flags=zmq.NOBLOCK)
        except zmq.ZMQError as e:  # pragma: debug
            raise multitasking.BreakLoopError(
                "_reply_handshake_recv (in send) => ZMQ Error(%s): %s"
                % (key, e))
        if self.is_eof(msg_send):  # pragma: debug
            self.error("REPLY EOF SENT")
            return True
        tries = 100
        out = 0
        while (out == 0) and (tries > 0):
            out = socket.poll(timeout=self.zmq_sleeptime,
                              flags=zmq.POLLIN)
            if out == 0:
                self.debug(
                    ("No response waiting (address=%s). "
                     "%d tries left."), key, tries)
                tries -= 1
        try:
            msg_recv = self._catch_eagain(socket.recv, flags=zmq.NOBLOCK)
        except zmq.ZMQError as e:  # pragma: debug
            raise multitasking.BreakLoopError(
                "_reply_handshake_recv (in recv) => ZMQ Error(%s): %s"
                % (key, e))
        assert(msg_recv == msg_send)
        self._n_reply_recv[key] += 1
        return True

    def _close_backlog(self, wait=False):
        r"""Close the backlog thread and the reply sockets."""
        with self.reply_socket_lock:
            if (self.reply_socket_send is not None):
                self.reply_socket_send.close(linger=0)  # self.zmq_sleeptime)
                self.unregister_comm("REPLY_SEND_" + self.reply_socket_address)
            for k, socket in self.reply_socket_recv.items():
                socket.close(linger=0)
                self.unregister_comm("REPLY_RECV_" + k)

    def _close(self, linger=False):
        r"""Close the connection.

        Args:
            linger (bool, optional): If True, drain messages before closing the
                comm. Defaults to False.

        """
        self.debug("")
        if not self.is_async:
            self._close_backlog(wait=linger)
        with self.socket_lock:
            self.debug("self.socket.closed = %s", str(self.socket.closed))
            back_messages = []
            if self.socket.closed:
                self._bound = False
                self._connected = False
            elif self.is_server and (self.cli_address is not None):
                # Requeue messages in transit during close
                # self._send_client_msg(ZMQProxy.server_signoff_msg)
                while self.is_message(zmq.POLLIN):  # pragma: debug
                    back_messages.append(self.socket.recv())
            # Ensure socket not still open
            self._openned = False
            if not self.socket.closed:
                if self._bound:
                    self.unbind()
                elif self._connected:
                    self.disconnect()
                self.socket.close(linger=0)
                # if self.protocol == 'ipc':
                #     print(self.host, os.path.isfile(self.host))
                # if (self.direction == 'recv') and (self.protocol == 'ipc'):
                #     if os.path.isfile(self.host):
                #         os.remove(self.host)
            self.unregister_comm(self.registry_key)
            if back_messages:  # pragma: debug
                # for x in back_messages:
                #     self._send_client_msg(x)
                raise RuntimeError("backlogged messages not supported: %s"
                                   % back_messages)
        super(ZMQComm, self)._close(linger=linger)
        if self.cli_socket is not None:
            self.cli_socket.disconnect(self.cli_address)
            self.cli_socket.close()
            self.cli_socket = None

    def server_exists(self, srv_address):
        r"""Determine if a server exists.

        Args:
            srv_address (str): Address of server comm.

        Returns:
            bool: True if a server with the provided address exists, False
                otherwise.

        """
        srv_param = parse_address(srv_address)
        if srv_param['port'] is None:
            return False
        return super(ZMQComm, self).server_exists(srv_address)

    def _send_client_msg(self, msg):
        if self.cli_address is not None:
            if self.cli_socket is None:
                self.cli_socket = create_socket(self.context, zmq.DEALER)
                self.cli_socket.connect(self.cli_address)
            self._catch_eagain(self.cli_socket.send, msg, flags=zmq.NOBLOCK)
            # cli_socket.disconnect(self.cli_address)
            # cli_socket.close()

    @property
    def is_open(self):
        r"""bool: True if the socket is open."""
        with self.socket_lock:
            return (self._openned and not self.socket.closed)

    def is_message(self, flags):
        r"""Poll the socket for a message.

        Args:
            flags (int): ZMQ poll flags.

        Returns:
            bool: True if there is a message matching the flags, False otherwise.

        """
        out = 0
        # with self._closing_thread.lock:
        with self.socket_lock:
            if self.is_open:
                try:
                    out = self.socket.poll(timeout=1, flags=flags)
                except zmq.ZMQError:  # pragma: debug
                    # self.exception('Error polling')
                    pass
        return bool(out)
        
    @property
    def n_msg_recv(self):
        r"""int: The number of incoming messages in the connection."""
        if self.is_open and (self.direction == 'recv'):
            return int(self.is_message(zmq.POLLIN))
        return 0

    @property
    def n_msg_send(self):
        r"""int: The number of outgoing messages in the connection."""
        if self.is_open and (self.direction == 'send'):
            return (self._n_zmq_sent - self._n_reply_sent)
        return 0

    @property
    def is_confirmed_recv(self):
        r"""bool: True if all received messages have been confirmed."""
        if not super(ZMQComm, self).is_confirmed_recv:
            return False
        if self.is_open and (self.direction == 'recv'):
            return (self._n_zmq_recv == self._n_reply_recv)
        return True  # pragma: debug

    @property
    def get_work_comm_kwargs(self):
        r"""dict: Keyword arguments for an existing work comm."""
        out = super(ZMQComm, self).get_work_comm_kwargs
        out['socket_type'] = 'PAIR'
        out['context'] = self.context
        return out

    @property
    def create_work_comm_kwargs(self):
        r"""dict: Keyword arguments for a new work comm."""
        out = super(ZMQComm, self).create_work_comm_kwargs
        out['socket_type'] = 'PAIR'
        out['context'] = self.context
        return out
    
    def workcomm2header(self, work_comm, **kwargs):
        r"""Get header information from a comm.

        Args:
            work_comm (:class:.CommBase): Work comm that header describes.
            **kwargs: Additional keyword arguments are added to the header.

        Returns:
            dict: Header information that will be sent with a message.

        """
        out = super(ZMQComm, self).workcomm2header(work_comm, **kwargs)
        if self.direction == 'send':
            out['zmq_reply_worker'] = work_comm.set_reply_socket_send()
        return out

    def header2workcomm(self, header, **kwargs):
        r"""Get a work comm based on header info.

        Args:
            header (dict): Information that will be sent in the message header
                to the work comm.
            **kwargs: Additional keyword arguments are passed to the parent method.

        Returns:
            :class:.CommBase: Work comm.

        """
        if ('zmq_reply_worker' in header) and (self.direction == 'recv'):
            kwargs['reply_socket_address'] = header['zmq_reply_worker']
        c = super(ZMQComm, self).header2workcomm(header, **kwargs)
        return c
    
    def prepare_message(self, *args, **kwargs):
        r"""Perform actions preparing to send a message.

        Args:
            *args: Components of the outgoing message.
            **kwargs: Keyword arguments are passed to the parent class's method.

        Returns:
            CommMessage: Serialized and annotated message.

        """
        kwargs.setdefault('header_kwargs', {})
        kwargs['header_kwargs']['zmq_reply'] = self.set_reply_socket_send()
        return super(ZMQComm, self).prepare_message(*args, **kwargs)
        
    def send(self, *args, **kwargs):
        r"""Send a message."""
        # Ensure that filter is not being used with REQ or REP socket
        # which cannot drop messages
        if self.filter and (self.socket_type_name in ['REQ', 'REP']):  # pragma: debug
            raise RuntimeError("Cannot use filters with REQ or REP "
                               "sockets since dropping messages "
                               "would break the requirement of "
                               "alternating send & receives.")
        return super(ZMQComm, self).send(*args, **kwargs)
        
    def recv(self, *args, **kwargs):
        r"""Receive a message."""
        # Ensure that filter is not being used with REQ or REP socket
        # which cannot drop messages
        if self.filter and (self.socket_type_name in ['REQ', 'REP']):  # pragma: debug
            raise RuntimeError("Cannot use filters with REQ or REP "
                               "sockets since dropping messages "
                               "would break the requirement of "
                               "alternating send & receives.")
        return super(ZMQComm, self).recv(*args, **kwargs)
        
    def _send(self, msg, topic='', identity=None, **kwargs):
        r"""Send a message.

        Args:
            msg (str, bytes): Message to be sent.
            topic (str, optional): Filter that should be sent with the
                message for 'PUB' sockets. Defaults to ''.
            identity (str, optional): Identify of identified worker that
                should be sent for 'ROUTER' sockets. Defaults to
                self.dealer_identity.
            **kwargs: Additional keyword arguments are passed to the
                ZeroMQ socket's send method.

        Returns:
            bool: Success or failure of send.

        """
        if identity is None:
            identity = self.dealer_identity
        topic = tools.str2bytes(topic)
        identity = tools.str2bytes(identity)
        if self.socket_type_name == 'PUB':
            total_msg = topic + _flag_zmq_filter + msg
        else:
            total_msg = msg
        total_msg = self.check_reply_socket_send(total_msg)
        kwargs.setdefault('flags', zmq.NOBLOCK)
        with self.socket_lock:
            try:
                if self.socket_type_name == 'ROUTER':
                    kwargs['flags'] |= zmq.SNDMORE
                    self.socket.send(identity, **kwargs)
                else:
                    self.socket.send(total_msg, **kwargs)
                TemporaryCommunicationError.reset((self.address, "zmq.EAGAIN"))
            except zmq.ZMQError as e:  # pragma: debug
                if e.errno == zmq.EAGAIN:
                    raise TemporaryCommunicationError(
                        "Socket not yet available.",
                        max_consecutive_allowed=(
                            100 if self._used else None),
                        registry_key=(self.address, "zmq.EAGAIN"))
                self.special_debug("Socket could not send. (errno=%d)", e.errno)
                raise
        if self.socket_type_name == 'ROUTER':
            # TODO: Need to wait here to prevent sending messages twice when
            # TemporaryCommunicationError is raised due to failure to send
            # total_msg after successfully sending identity
            kwargs['flags'] = 0
            self.socket.send(total_msg, **kwargs)
        self._n_zmq_sent += 1
        return True

    def _recv(self, **kwargs):
        r"""Receive a message from the ZMQ socket.

        Args:
            **kwargs: Additional keyword arguments are passed to socket send.

        Returns:
            tuple (bool, obj): Success or failure of receive and received
                message.

        """
        kwargs.setdefault('flags', zmq.NOBLOCK)
        while True:
            with self.socket_lock:
                try:
                    if self.socket.closed:  # pragma: debug
                        self.error("Socket closed")
                        return (False, self.empty_bytes_msg)
                    if self.socket_type_name == 'ROUTER':
                        [identity, total_msg] = self.socket.recv_multipart(**kwargs)
                        self._recv_identities.add(identity)
                    else:
                        total_msg = self.socket.recv(**kwargs)
                except zmq.ZMQError as e:
                    if e.errno == zmq.ETIMEDOUT:  # pragma: debug
                        raise NoMessages("No messages in socket.")
                    elif e.errno == zmq.EAGAIN:
                        raise TemporaryCommunicationError(
                            "Socket not yet available.")
                    self.special_debug(("Socket could not receive. "
                                        "(errno=%d)"), e.errno)  # pragma: debug
                    self.info("zmq error: %s", e)  # pragma: debug
                    raise
            # Check for server sign-on
            if total_msg.startswith(ZMQProxy.server_signon_msg):
                if self.cli_address is None:
                    self.debug("Server received signon: %s, msg=%s",
                               self.address, total_msg)
                    self.cli_address = total_msg.split(
                        ZMQProxy.server_signon_msg)[-1].decode('utf-8')
                self._send_client_msg(total_msg)
            else:
                break
        # Interpret headers
        total_msg, k = self.check_reply_socket_recv(total_msg)
        if self.socket_type_name == 'SUB':
            topic, msg = total_msg.split(_flag_zmq_filter)
            assert(topic == self.topic_filter)
        else:
            msg = total_msg
        # Confirm receipt
        if k is not None:
            self._n_zmq_recv[k] += 1
        else:  # pragma: debug
            self.info("No reply address.")
        return (True, msg)

    def drain_server_signon_messages(self, **kwargs):
        r"""Drain server signon messages. This should only be used
        for testing purposes."""
        super(ZMQComm, self).drain_server_signon_messages(**kwargs)
        if not ((self.direction == 'recv')
                and (self.is_server or self.allow_multiple_comms)):
            return
        # Wait for signon message
        T = self.start_timeout(10.0)
        while ((not T.is_out) and (self.n_msg == 0)):  # pragma: debug
            self.sleep()
        self.stop_timeout()
        # Drain signon messages
        T = self.start_timeout(10.0)
        while ((not T.is_out) and (self.n_msg > 0)):  # pragma: debug
            flag, msg = self.recv(timeout=0)
            assert(flag)
            assert(self.is_empty_recv(msg))
            self.sleep()
        self.stop_timeout()
        
    def confirm_send(self, noblock=False):
        r"""Confirm that sent message was received."""
        if noblock:
            if self.is_open and (self._n_zmq_sent != self._n_reply_sent):
                self._n_reply_sent = self._n_zmq_sent  # pragma: debug
            return True
        flag = True
        if self.is_open and (self._n_zmq_sent != self._n_reply_sent):
            self.verbose_debug("Confirming %d/%d sent messages",
                               self._n_reply_sent, self._n_zmq_sent)
            while (self._n_zmq_sent != self._n_reply_sent) and flag:
                with self.reply_socket_lock:
                    flag = self._reply_handshake_send()
                if flag:
                    self.debug("Send confirmed (%d/%d)",
                               self._n_reply_sent, self._n_zmq_sent)
        return flag

    def confirm_recv(self, noblock=False):
        r"""Confirm that message was received."""
        with self.reply_socket_lock:
            keys = [k for k in self.reply_socket_recv.keys()]
        if noblock:
            for k in keys:
                if self.is_open and (self._n_zmq_recv[k] != self._n_reply_recv[k]):
                    self._n_reply_recv[k] = self._n_zmq_recv[k]  # pragma: debug
            return True
        flag = True
        for k in keys:
            if self.is_open and (self._n_zmq_recv[k] != self._n_reply_recv[k]):
                self.debug("Confirming %d/%d received messages",
                           self._n_reply_recv[k], self._n_zmq_recv[k])
                while (self._n_zmq_recv[k] != self._n_reply_recv[k]) and flag:
                    with self.reply_socket_lock:
                        flag = self._reply_handshake_recv(_reply_msg, k)
                    if flag:
                        self.debug("Recv confirmed (%d/%d)",
                                   self._n_reply_recv[k], self._n_zmq_recv[k])
        return flag
