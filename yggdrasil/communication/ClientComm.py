import uuid
from collections import OrderedDict
from yggdrasil.communication import CommBase, new_comm, get_comm, import_comm


class ClientComm(CommBase.CommBase):
    r"""Class for handling Client side communication.

    Args:
        name (str): The environment variable where communication address is
            stored.
        request_commtype (str, optional): Comm class that should be used for
            the request comm. Defaults to None.
        response_kwargs (dict, optional): Keyword arguments for the response
            comm. Defaults to empty dict.
        direct_connection (bool, optional): If True, the comm will be
            directly connected to a ServerComm. Defaults to False.
        **kwargs: Additional keywords arguments are passed to the output comm.

    Attributes:
        response_kwargs (dict): Keyword arguments for the response comm.
        request_order (list): Order of request IDs.
        responses (dict): Mapping between request IDs and response messages.
        ocomm (Comm): Request comm.
        icomm (Comm): Response comm.

    """

    _commtype = 'client'
    _dont_register = True
    
    def __init__(self, name, request_commtype=None, response_kwargs=None,
                 dont_open=False, is_async=False, direct_connection=False,
                 **kwargs):
        if response_kwargs is None:
            response_kwargs = dict()
        ocomm_name = name
        ocomm_kwargs = kwargs
        ocomm_kwargs['direction'] = 'send'
        ocomm_kwargs['dont_open'] = True
        ocomm_kwargs['commtype'] = request_commtype
        ocomm_kwargs.setdefault('use_async', is_async)
        if direct_connection:
            ocomm_kwargs.setdefault('is_client', True)
        self.direct_connection = direct_connection
        self.response_kwargs = response_kwargs
        self.ocomm = get_comm(ocomm_name, **ocomm_kwargs)
        self.icomm = None
        self.request_order = []
        self.responses = OrderedDict()
        self.response_kwargs.setdefault('is_interface', self.ocomm.is_interface)
        self.response_kwargs.setdefault('commtype', self.ocomm._commtype)
        self.response_kwargs.setdefault('recv_timeout', self.ocomm.recv_timeout)
        self.response_kwargs.setdefault('language', self.ocomm.language)
        self.response_kwargs.setdefault('use_async', self.ocomm.is_async)
        self.response_kwargs.setdefault('env', self.ocomm.env)
        super(ClientComm, self).__init__(self.ocomm.name, dont_open=dont_open,
                                         recv_timeout=self.ocomm.recv_timeout,
                                         is_interface=self.ocomm.is_interface,
                                         direction='send', no_suffix=True,
                                         address=self.ocomm.address,
                                         is_async=self.ocomm.is_async,
                                         env=self.ocomm.env)

    def get_status_message(self, nindent=0, **kwargs):
        r"""Return lines composing a status message.
        
        Args:
            nindent (int, optional): Number of tabs that should
                be used to indent each line. Defaults to 0.
            *kwargs: Additional arguments are passed to the
                parent class's method.
                
        Returns:
            tuple(list, prefix): Lines composing the status message and the
                prefix string used for the last message.

        """
        lines, prefix = super(ClientComm, self).get_status_message(
            nindent=nindent, **kwargs)
        lines.append('%s%-15s:' % (prefix, 'request comm'))
        lines += self.ocomm.get_status_message(nindent=(nindent + 1))[0]
        lines.append('%s%-15s:' % (prefix, 'response comms'))
        lines += self.icomm.get_status_message(nindent=(nindent + 1))[0]
        return lines, prefix
    
    @classmethod
    def is_installed(cls, language=None):
        r"""Determine if the necessary libraries are installed for this
        communication class.

        Args:
            language (str, optional): Specific language that should be checked
                for compatibility. Defaults to None and all languages supported
                on the current platform will be checked.

        Returns:
            bool: Is the comm installed.

        """
        return import_comm().is_installed(language=language)

    @property
    def maxMsgSize(self):
        r"""int: Maximum size of a single message that should be sent."""
        return self.ocomm.maxMsgSize
        
    @classmethod
    def underlying_comm_class(self):
        r"""str: Name of underlying communication class."""
        return import_comm().underlying_comm_class()

    @classmethod
    def comm_count(cls):
        r"""int: Number of communication connections."""
        return import_comm().comm_count()

    @classmethod
    def new_comm_kwargs(cls, name, request_commtype=None, **kwargs):
        r"""Initialize communication with new comms.

        Args:
            name (str): Name for new comm.
            request_commtype (str, optional): Name of class for new output
                comm. Defaults to None.

        """
        args = [name]
        ocomm_class = import_comm(request_commtype)
        kwargs['direction'] = 'send'
        if 'address' not in kwargs:
            oargs, kwargs = ocomm_class.new_comm_kwargs(name, **kwargs)
        kwargs['request_commtype'] = request_commtype
        return args, kwargs

    @property
    def opp_address(self):
        r"""str: Address for opposite comm."""
        return self.ocomm.opp_address
        
    @property
    def opp_comms(self):
        r"""dict: Name/address pairs for opposite comms."""
        out = super(ClientComm, self).opp_comms
        out.update(**self.ocomm.opp_comms)
        return out

    def opp_comm_kwargs(self):
        r"""Get keyword arguments to initialize communication with opposite
        comm object.

        Returns:
            dict: Keyword arguments for opposite comm object.

        """
        kwargs = super(ClientComm, self).opp_comm_kwargs()
        kwargs['commtype'] = "server"
        kwargs['request_commtype'] = self.ocomm._commtype
        kwargs['response_kwargs'] = self.response_kwargs
        kwargs['direct_connection'] = self.direct_connection
        return kwargs
        
    def open(self):
        r"""Open the connection."""
        super(ClientComm, self).open()
        self.ocomm.open()

    def close(self, *args, **kwargs):
        r"""Close the connection."""
        self.ocomm.close(*args, **kwargs)
        if self.icomm is not None:
            self.icomm.close(*args, **kwargs)
        super(ClientComm, self).close(*args, **kwargs)

    @property
    def is_open(self):
        r"""bool: True if the connection is open."""
        return self.ocomm.is_open

    @property
    def is_closed(self):
        r"""bool: True if the connection is closed."""
        return self.ocomm.is_closed

    @property
    def n_msg_send(self):
        r"""int: The number of messages in the connection."""
        return self.ocomm.n_msg_send

    @property
    def n_msg_send_drain(self):
        r"""int: The number of outgoing messages in the connection to drain."""
        return self.ocomm.n_msg_send_drain

    def atexit(self):  # pragma: debug
        r"""Close operations."""
        self.send_eof()
        super(ClientComm, self).atexit()
        
    # RESPONSE COMM
    def create_response_comm(self):
        r"""Create a response comm based on information from the last header."""
        header = dict(request_id=str(uuid.uuid4()))
        while header['request_id'] in self.request_order:  # pragma: debug
            header['request_id'] += str(uuid.uuid4())
        if self.icomm is None:
            comm_kwargs = dict(direction='recv', is_response_client=True,
                               **self.response_kwargs)
            if comm_kwargs.get('use_async', False):
                comm_kwargs['async_recv_method'] = 'recv_message'
            self.icomm = new_comm(self.name + '.client_response_comm', **comm_kwargs)
        header['response_address'] = self.icomm.address
        self.request_order.append(header['request_id'])
        return header

    # SEND METHODS
    def prepare_message(self, *args, **kwargs):
        r"""Perform actions preparing to send a message.

        Args:
            *args: Components of the outgoing message.
            **kwargs: Keyword arguments are passed to the request comm's
                prepare_message method.

        Returns:
            CommMessage: Serialized and annotated message.

        """
        def add_response_address(msg):
            if msg.flag == CommBase.FLAG_SUCCESS:
                if msg.header is None:
                    msg.header = {}
                msg.header.update(self.create_response_comm())
            return msg
        kwargs.setdefault('after_prepare_message', [])
        kwargs['after_prepare_message'].append(add_response_address)
        return self.ocomm.prepare_message(*args, **kwargs)
        
    def send_message(self, msg, **kwargs):
        r"""Send a message encapsulated in a CommMessage object.

        Args:
            msg (CommMessage): Message to be sent.
            **kwargs: Additional keyword arguments are passed to the request
                comm's send_message method.

        Returns:
            bool: Success or failure of send.
        
        """
        out = self.ocomm.send_message(msg, **kwargs)
        self.errors += self.ocomm.errors
        return out
        
    # RECV METHODS
    def recv_message(self, *args, **kwargs):
        r"""Receive a message.

        Args:
            *args: Arguments are passed to the response comm's recv_message method.
            **kwargs: Keyword arguments are passed to the response comm's recv_message
                method.

        Returns:
            CommMessage: Received message.

        """
        if not self.request_order:  # pragma: debug
            raise RuntimeError("There are not any requests registered.")
        while self.responses.get(self.request_order[0], None) is None:
            msg = self.icomm.recv_message(*args, **kwargs)
            self.errors += self.icomm.errors
            if msg.flag != CommBase.FLAG_SUCCESS:
                break
            assert(msg.header['request_id'] not in self.responses)
            self.responses[msg.header['request_id']] = msg
        if self.request_order[0] in self.responses:
            msg = self.responses.pop(self.request_order[0])
            self.request_order.pop(0)
        return msg

    def finalize_message(self, msg, **kwargs):
        r"""Perform actions to decipher a message.

        Args:
            msg (CommMessage): Initial message object to be finalized.
            **kwargs: Keyword arguments are passed to the response comm's
                finalize_message method.

        Returns:
            CommMessage: Deserialized and annotated message.

        """
        if self.icomm is None:  # pragma: debug
            raise RuntimeError("There are not any registered response comms.")
        return self.icomm.finalize_message(msg, **kwargs)
        
    # CALL
    def call(self, *args, **kwargs):
        r"""Do RPC call. The request message is sent to the output comm and the
        response is received from the input comm.

        Args:
            *args: Arguments are passed to output comm send method.
            **kwargs: Keyword arguments are passed to output comm send method

        Returns:
            obj: Output from input comm recv method.

        """
        flag = self.send(*args, **kwargs)
        if not flag:  # pragma: debug
            return (False, self.empty_obj_recv)
        return self.recv(timeout=False)

    def call_nolimit(self, *args, **kwargs):
        r"""Alias for call."""
        return self.call(*args, **kwargs)

    # OLD STYLE ALIASES
    def rpcSend(self, *args, **kwargs):
        r"""Alias for RPCComm.send"""
        return self.send(*args, **kwargs)

    def rpcRecv(self, *args, **kwargs):
        r"""Alias for RPCComm.recv"""
        return self.recv(*args, **kwargs)
    
    def rpcCall(self, *args, **kwargs):
        r"""Alias for RPCComm.call"""
        return self.call(*args, **kwargs)
    
    def drain_messages(self, direction='send', **kwargs):
        r"""Sleep while waiting for messages to be drained."""
        if direction == 'send':
            self.ocomm.drain_messages(direction='send', **kwargs)
