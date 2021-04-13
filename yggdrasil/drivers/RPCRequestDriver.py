from yggdrasil.drivers.ConnectionDriver import ConnectionDriver, run_remotely
from yggdrasil.communication import CommBase

# ----
# Client sends resquest to local client output comm
# Client recvs response from local client input comm
# ----
# Client request driver recvs from local client output comm
# Client request driver creates client response driver
# Client request driver sends to server request comm (w/ response comm header)
# ----
# Client response driver recvs from client response comm
# Client response driver sends to local client input comm
# ----
# Server recvs request from local server input comm
# Server sends response to local server output comm
# ----
# Server request driver recvs from server request comm
# Server request driver creates server response driver
# Server request driver sends to local server input comm
# ----
# Server response driver recvs from local server output comm
# Server response driver sends to client response comm
# ----


YGG_CLIENT_INI = b'YGG_BEGIN_CLIENT'
YGG_CLIENT_EOF = b'YGG_END_CLIENT'


class RPCRequestDriver(ConnectionDriver):
    r"""Class for handling client side RPC type communication.

    Args:
        model_request_name (str): The name of the channel used by the client
            model to send requests.
        **kwargs: Additional keyword arguments are passed to parent class.

    """

    _connection_type = 'rpc_request'

    def __init__(self, model_request_name, **kwargs):
        # Input communicator
        inputs = kwargs.get('inputs', [{}])
        # inputs[0]['name'] = model_request_name + '.client_model_request'
        kwargs['inputs'] = inputs
        # Output communicator
        outputs = kwargs.get('outputs', [{}])
        # outputs[0]['name'] = model_request_name + '.server_model_request'
        outputs[0]['is_client'] = True
        outputs[0]['close_on_eof_send'] = False
        kwargs['outputs'] = outputs
        # Parent and attributes
        super(RPCRequestDriver, self).__init__(model_request_name, **kwargs)

    @property
    @run_remotely
    def clients(self):
        r"""list: Clients that are connected."""
        return self.models['input'].copy()

    @property
    @run_remotely
    def nclients(self):
        r"""int: Number of clients that are connected."""
        return len(self.clients)

    @property
    def model_env(self):
        r"""dict: Mapping between model name and opposite comm
        environment variables that need to be provided to the model."""
        out = super(RPCRequestDriver, self).model_env
        # Add is_rpc flag to output model env variables
        for k in self.ocomm.model_env.keys():
            out[k]['YGG_IS_SERVER'] = 'True'
        return out
        
    @run_remotely
    def remove_model(self, direction, name):
        r"""Remove a model from the list of models.

        Args:
            direction (str): Direction of model.
            name (str): Name of model exiting.

        Returns:
            bool: True if all of the input/output models have signed
                off; False otherwise.

        """
        with self.lock:
            if (direction == "input") and (name in self.clients):
                super(RPCRequestDriver, self).send_message(
                    CommBase.CommMessage(args=YGG_CLIENT_EOF,
                                         flag=CommBase.FLAG_SUCCESS),
                    header_kwargs={'raw': True, 'model': name},
                    skip_processing=True)
            out = super(RPCRequestDriver, self).remove_model(
                direction, name)
            if out:
                self.send_eof()
            return out
        
    def on_eof(self, msg):
        r"""On EOF, decrement number of clients. Only send EOF if the number
        of clients drops to 0.

        Args:
            msg (CommMessage): Message object that provided the EOF.

        Returns:
            CommMessage, bool: Value that should be returned by recv_message on EOF.

        """
        with self.lock:
            self.remove_model('input', msg.header.get('model', ''))
            if self.nclients == 0:
                self.debug("All clients have signed off (EOF).")
                return super(RPCRequestDriver, self).on_eof(msg)
        return CommBase.CommMessage(flag=CommBase.FLAG_EMPTY,
                                    args=self.icomm.empty_obj_recv)

    def before_loop(self):
        r"""Send client sign on to server response driver."""
        super(RPCRequestDriver, self).before_loop()
        self.ocomm._send_serializer = True

    def send_message(self, msg, **kwargs):
        r"""Move response arguments to new header.

        Args:
            msg (CommMessage): Message being sent.
            **kwargs: Keyword arguments are passed to parent class send_message.

        Returns:
            bool: Success or failure of send.

        """
        if self.ocomm.is_closed:
            return False
        if msg.flag != CommBase.FLAG_EOF:
            # Send response address in header
            kwargs.setdefault('header_kwargs', {})
            kwargs['header_kwargs'].setdefault(
                'response_address', msg.header['response_address'])
            kwargs['header_kwargs'].setdefault('request_id', msg.header['request_id'])
            kwargs['header_kwargs'].setdefault('model', msg.header.get('model', ''))
        return super(RPCRequestDriver, self).send_message(msg, **kwargs)
