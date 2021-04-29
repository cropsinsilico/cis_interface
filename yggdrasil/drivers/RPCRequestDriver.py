from yggdrasil.drivers.ConnectionDriver import ConnectionDriver, run_remotely
from yggdrasil.drivers.RPCResponseDriver import RPCResponseDriver
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

    Attributes:
        response_drivers (dict): Response drivers created for each request.

    """

    _connection_type = 'rpc_request'

    def __init__(self, model_request_name, response_kwargs=None, **kwargs):
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
        if response_kwargs is None:
            response_kwargs = {}
        self.response_kwargs = response_kwargs
        # Parent and attributes
        super(RPCRequestDriver, self).__init__(model_request_name, **kwargs)
        self.response_kwargs.setdefault('commtype', self.ocomm._commtype)
        self.response_drivers = {}
        self._block_response = False

    @property
    def servers_recvd(self):
        r"""list: Names of server models that have returned responses."""
        out = {}
        for x in self.response_drivers.values():
            for k, v in x.models_recvd.items():
                out.setdefault(k, 0)
                out[k] += v
        return out

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
        
    def close_response_drivers(self):
        r"""Close response driver."""
        with self.lock:
            self.debug("Closing response drivers.")
            self._block_response = True
            for x in self.response_drivers.values():
                x.terminate()
            self.response_drivers = {}

    def close_comm(self):
        r"""Close response drivers."""
        self.close_response_drivers()
        super(RPCRequestDriver, self).close_comm()
            
    def printStatus(self, *args, **kwargs):
        r"""Also print response drivers."""
        super(RPCRequestDriver, self).printStatus(*args, **kwargs)
        for x in self.response_drivers.values():
            x.printStatus(*args, **kwargs)

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
                if self.ocomm.partner_copies > 1:
                    self.ocomm.partner_copies = len(self.servers_recvd)
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
        r"""Start a response driver for a request message and send message with
        header.

        Args:
            msg (CommMessage): Message being sent.
            **kwargs: Keyword arguments are passed to parent class send_message.

        Returns:
            bool: Success or failure of send.

        """
        if self.ocomm.is_closed:
            return False
        # Start response driver
        if msg.flag != CommBase.FLAG_EOF:
            with self.lock:
                if (not self.is_comm_open) or self._block_response:  # pragma: debug
                    self.debug("Comm closed, not creating response driver.")
                    return False
                
                if msg.header['response_address'] in self.response_drivers:
                    response_driver = self.response_drivers[
                        msg.header['response_address']]
                else:
                    drv_args = [msg.header['response_address'],
                                msg.header['request_id']]
                    drv_kwargs = dict(
                        request_name=self.name,
                        inputs=[self.response_kwargs.copy()],
                        outputs=[{'commtype': msg.header["commtype"]}])
                    self.debug("Creating response comm: address = %s, request_id = %s",
                               msg.header['response_address'],
                               msg.header['request_id'])
                    try:
                        response_driver = RPCResponseDriver(
                            *drv_args, **drv_kwargs)
                        self.response_drivers[
                            msg.header['response_address']] = response_driver
                        response_driver.start()
                        self.debug("Started response comm: address = %s, request_id = %s",
                                   msg.header['response_address'],
                                   msg.header['request_id'])
                    except BaseException:  # pragma: debug
                        self.exception("Could not create/start response driver.")
                        return False
            # Send response address in header
            kwargs.setdefault('header_kwargs', {})
            kwargs['header_kwargs'].setdefault(
                'response_address', response_driver.response_address)
            kwargs['header_kwargs'].setdefault('request_id', msg.header['request_id'])
            kwargs['header_kwargs'].setdefault('model', msg.header.get('model', ''))
        return super(RPCRequestDriver, self).send_message(msg, **kwargs)

    def run_loop(self):
        r"""Run the driver. Continue looping over messages until there are not
        any left or the communication channel is closed.
        """
        super(RPCRequestDriver, self).run_loop()
        if not self.was_break:
            self.prune_response_drivers()

    def prune_response_drivers(self):
        r"""Remove response drivers that are no longer being used."""
        with self.lock:
            # remove_idx = []
            # for i, x in enumerate(self.response_drivers):
            for x in self.response_drivers.values():
                self.errors += x.errors
            #     if (((not x.is_alive())
            #          and x.icomm.is_confirmed_recv
            #          and x.ocomm.is_confirmed_send)):
            #         x.cleanup()
            #         remove_idx.append(i)
            # for i in remove_idx[::-1]:
            #     self.response_drivers.pop(i)
