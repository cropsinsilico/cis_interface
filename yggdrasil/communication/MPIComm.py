import logging
import numpy as np
from yggdrasil.multitasking import _on_mpi, MPI
from yggdrasil.communication import (
    CommBase, NoMessages)
logger = logging.getLogger(__name__)


class MPIRequest(object):
    r"""Container for MPI request."""

    __slots__ = ['comm', 'address', 'direction', 'tag', 'size_req',
                 'req', 'size', 'data', '_complete']

    def __init__(self, comm, direction, address, tag, **kwargs):
        if isinstance(address, list):
            if len(address) == 1:
                address = address[0]
            else:
                assert(direction == 'send')
                address = address[tag % len(address)]
        self.comm = comm
        self.address = address
        self.direction = direction
        self.tag = tag
        self._complete = False
        self.size = np.zeros(1, dtype='i')
        self.data = None
        self.size_req = None
        self.req = self.make_request(**kwargs)

    def make_request(self, payload=None):
        r"""Complete a request."""
        kwargs = dict(tag=self.tag)
        if self.direction == 'send':
            method = 'Isend'
            args = ([payload, MPI.CHAR], )
            kwargs['dest'] = self.address
            # Send size of message
            self.size[0] = len(payload)
            self.size_req = self.comm.Isend([self.size, MPI.INT], **kwargs)
        else:
            method = 'Irecv'
            args = ([self.size, MPI.INT], )
            kwargs['source'] = self.address
        logger.debug("rank = %d, method = %s, args = %s, kwargs = %s",
                     self.comm.Get_rank(), method, args, kwargs)
        return getattr(self.comm, method)(*args, **kwargs)

    @property
    def complete(self):
        r"""bool: True if the request has been completed, False otherwise."""
        if not self._complete:
            data = self.req.test()
            if data[0]:
                if self.direction == 'recv':
                    buf = np.zeros(self.size[0], dtype='c')
                    self.comm.Recv([buf, MPI.CHAR],
                                   source=self.address, tag=self.tag)
                    data = (data[0], buf.tobytes())
                self._complete = True
                self.data = data[1]
        return self._complete

    def cancel(self):
        r"""Cancel a request."""
        if not self._complete:
            if self.direction == 'send':
                self.size_req.Cancel()
            self.req.Cancel()
            self._complete = True


class MPIMultiRequest(MPIRequest):
    r"""Container for MPI request for multiple partner comms."""

    __slots__ = ["remainder"]

    def __init__(self, *args, **kwargs):
        self.remainder = {}
        super(MPIMultiRequest, self).__init__(*args, **kwargs)

    def make_request(self, comm, previous_requests=None):
        r"""Complete a request."""
        out = previous_requests
        if out is None:
            out = {}
        for x in self.address:
            if x not in out:
                out[x] = MPIRequest(comm, self.direction, x, self.tag)
        return out

    @property
    def complete(self):
        r"""bool: True if the request has been completed, False otherwise."""
        if not self._complete:
            for k, v in self.req.items():
                if v.complete:
                    self._complete = True
                    self.data = v.data
                    for k2, v2 in self.req.items():
                        if k2 != k:
                            self.remainder[k2] = v2
                    break
        return self._complete


class MPIComm(CommBase.CommBase):
    r"""Class for handling I/O via MPI communicators.

    Args:
        tag_start (int, optional): Tag that MPI messages should start with.
            Defaults to 0.
        tag_stride (int, optional): Amount that tag should be advanced after
            each message to avoid conflicts w/ other MPIComm communicators.
            Defaults to 1.
        partner_mpi_ranks (list, optional): Rank of MPI processes that partner
            models are running on. Defaults to None.

    Attributes:
        tag (int): Tag that should be used for the next MPI message.
        tag_stride (int): Amount that tag should be advanced after each
            each message to avoid conflicts w/ other MPIComm communicators.

    """

    _commtype = 'mpi'
    _schema_subtype_description = 'MPI communicator.'
    address_description = "The partner communicator ID(s)."

    def __init__(self, *args, tag_start=0, tag_stride=1, **kwargs):
        assert(_on_mpi)
        if kwargs.get('partner_mpi_ranks', []):
            assert(kwargs.get('address', 'generate') == 'generate')
            kwargs['address'] = kwargs['partner_mpi_ranks']
        self.requests = []
        self.tag = tag_start
        self.tag_start = tag_start
        self.tag_stride = tag_stride
        self.requires_disconnect = False
        self.last_request = None
        self.mpi_comm = MPI.COMM_WORLD
        self._is_open = False
        kwargs['no_suffix'] = True
        super(MPIComm, self).__init__(*args, **kwargs)

    @classmethod
    def new_comm_kwargs(cls, *args, **kwargs):
        r"""Initialize communication with new queue."""
        if 'address' not in kwargs:
            kwargs.setdefault('address', 'generate')
        return args, kwargs

    def bind(self):
        r"""Bind to random queue if address is generate."""
        if isinstance(self.address, str):
            self.address = tuple([int(x) for x in self.address.split(',')])
        super(MPIComm, self).bind()

    @property
    def model_env(self):
        r"""dict: Mapping between model name and opposite comm
        environment variables that need to be provided to the model."""
        return {}
    
    @property
    def mpi_model_kws(self):
        r"""dict: Mapping between model name and opposite comm keyword
        arguments that need to be provided to the model for the MPI
        connection."""
        out = {}
        if self.partner_model is not None:
            out[self.partner_model] = [
                {'name': '%s_mpi_%s' % (self.name, self.direction),
                 'driver': 'ConnectionDriver'}]
            opp = self.opp_comm_kwargs()
            opp['env'] = self.opp_comms
            if opp['direction'] == 'recv':
                out[self.partner_model][0]['inputs'] = [opp]
                out[self.partner_model][0]['outputs'] = [
                    {'name': self.name,
                     'partner_model': self.partner_model,
                     'partner_language': self.partner_language}]
            else:
                out[self.partner_model][0]['outputs'] = [opp]
                out[self.partner_model][0]['inputs'] = [
                    {'name': self.name,
                     'partner_model': self.partner_model,
                     'partner_language': self.partner_language}]
        return out
        
    @property
    def opp_address(self):
        r"""str: Address for opposite comm."""
        return str(self.mpi_comm.Get_rank())
        
    def opp_comm_kwargs(self):
        r"""Get keyword arguments to initialize communication with opposite
        comm object.

        Returns:
            dict: Keyword arguments for opposite comm object.

        """
        out = super(MPIComm, self).opp_comm_kwargs()
        out['tag_start'] = self.tag_start
        out['tag_stride'] = self.tag_stride
        return out
        
    def open(self):
        r"""Open the queue."""
        # TODO: Handle group
        super(MPIComm, self).open()
        if not self.is_open:
            self._is_open = True
            assert(self.mpi_comm.Get_rank() not in self.address)
            
    def _close(self, linger=False):
        r"""Close the queue."""
        for x in self.requests:
            if not x.complete:
                x.cancel()
                self.tag -= self.tag_stride
        if self.requires_disconnect and self.is_open:
            self.mpi_comm.Disconnect()
        self.mpi_comm = None
        super(MPIComm, self)._close(linger=linger)
        
    @property
    def is_open(self):
        r"""bool: True if the queue is not None."""
        return (self.mpi_comm is not None) and self._is_open
        
    def confirm_send(self, noblock=False):
        r"""Confirm that sent message was received."""
        if noblock:
            return True
        return (self.n_msg_send == 0)

    def confirm_recv(self, noblock=False):
        r"""Confirm that message was received."""
        if noblock:
            return True
        return (self.n_msg_recv == 0)

    @property
    def n_msg_send(self):
        r"""int: Number of messages in the queue to send."""
        if self.is_open and self.requests:
            return sum([(not x.complete) for x in self.requests])
        else:
            return 0
        
    @property
    def n_msg_recv(self):
        r"""int: Number of messages in the queue to recv."""
        if self.is_open and (not self.requests):
            self.add_request()
        if self.is_open and self.requests:
            return sum([x.complete for x in self.requests])
        else:
            return 0

    def add_request(self, **kwargs):
        r"""Add a request to the queue."""
        args = (self.mpi_comm, self.direction, self.address, self.tag)
        if (len(self.address) == 1) or (self.direction == 'send'):
            cls = MPIRequest
        else:
            if self.last_request:
                kwargs['previous_requests'] = self.last_request.remainder
            cls = MPIMultiRequest
        self.requests.append(cls(*args, **kwargs))
        self.tag += self.tag_stride

    def _send(self, payload):
        r"""Send a message.

        Args:
            payload (str): Message to send.

        Returns:
            bool: Success or failure of sending the message.

        """
        self.add_request(payload=payload)
        return True
        
    def _recv(self):
        r"""Receive a message from the MPI communicator.

        Returns:
            tuple (bool, str): The success or failure of receiving a message
                and the message received.

        """
        if not self.requests:
            self.add_request()
        if not self.requests[0].complete:
            raise NoMessages("No messages in communicator.")
        self.last_request = self.requests.pop(0)
        return (True, self.last_request.data)

    def purge(self):
        r"""Purge all messages from the comm."""
        super(MPIComm, self).purge()
        while self.n_msg_recv > 0:
            self._recv()
