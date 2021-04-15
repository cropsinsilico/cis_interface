import unittest
from yggdrasil.schema import get_schema
from yggdrasil.tests import assert_raises, assert_equal
import yggdrasil.drivers.tests.test_ConnectionDriver as parent
from yggdrasil.drivers.tests.test_ConnectionDriver import (
    _default_comm, _zmq_installed, _ipc_installed, _rmq_installed)


class TestRPCRequestParam(parent.TestConnectionParam):
    r"""Test parameters for RPCRequestDriver class."""

    def __init__(self, *args, **kwargs):
        super(TestRPCRequestParam, self).__init__(*args, **kwargs)
        self.driver = 'RPCRequestDriver'
        self.args = None
        self.attr_list += ['response_drivers', 'clients']
        # Increased to allow forwarding between IPC comms on MacOS
        self.timeout = 5.0
        self.route_timeout = 2 * self.timeout
        # if tools.get_default_comm() == "IPCComm":
        #     self.route_timeout = 120.0
        # self.debug_flag = True
        # self.sleeptime = 0.5
        # self.timeout = 10.0
            
    @property
    def send_comm_kwargs(self):
        r"""dict: Keyword arguments for send comm."""
        out = self.instance.icomm.opp_comm_kwargs()
        out['request_commtype'] = out['commtype']
        out['commtype'] = 'client'
        return out

    @property
    def recv_comm_kwargs(self):
        r"""dict: Keyword arguments for recv comm."""
        out = self.instance.ocomm.opp_comm_kwargs()
        out['request_commtype'] = out['commtype']
        out['commtype'] = 'server'
        return out

    
class TestRPCRequestDriverNoStart(TestRPCRequestParam,
                                  parent.TestConnectionDriverNoStart):
    r"""Test class for RPCRequestDriver class without start."""
    
    def test_error_attributes(self):
        r"""Test error raised when trying to access attributes set on recv."""
        err_attr = ['request_id', 'response_address']
        for k in err_attr:
            assert_raises(AttributeError, getattr, self.instance, k)


class TestRPCRequestDriverNoInit(TestRPCRequestParam,
                                 parent.TestConnectionDriverNoInit):
    r"""Test class for RPCRequestDriver class without init."""
    pass
            

class TestRPCRequestDriver(TestRPCRequestParam,
                           parent.TestConnectionDriver):
    r"""Test class for RPCRequestDriver class."""

    def test_send_recv(self, msg_send=None):
        r"""Test routing of a short message between client and server."""
        try:
            if msg_send is None:
                msg_send = self.test_msg
            T = self.instance.start_timeout()
            while ((not T.is_out) and (not self.instance.is_valid)):
                self.instance.sleep()  # pragma: debug
            self.instance.stop_timeout()
            # Send a message to local output
            flag = self.send_comm.send(msg_send)
            assert(flag)
            # Receive on server side, then send back
            flag, srv_msg = self.recv_comm.recv(timeout=self.route_timeout)
            assert(flag)
            assert_equal(srv_msg, msg_send)
            self.instance.printStatus()
            flag = self.recv_comm.send(srv_msg)
            assert(flag)
            # Receive response on client side
            flag, cli_msg = self.send_comm.recv(timeout=self.route_timeout)
            assert(flag)
            assert_equal(cli_msg, msg_send)
        except BaseException:  # pragma: debug
            self.send_comm.printStatus()
            self.instance.printStatus(verbose=True)
            self.recv_comm.printStatus()
            raise

    def test_send_recv_nolimit(self):
        r"""Test routing of a large message between client and server."""
        self.test_send_recv(msg_send=self.msg_long)


# Dynamically create tests based on registered comm classes
s = get_schema()
comm_types = list(s['comm'].schema_subtypes.keys())
for k in comm_types:
    if k in [_default_comm, 'ValueComm', 'value',
             'BufferComm', 'buffer']:  # pragma: debug
        continue
    tcls = type('Test%sRPCRequestDriver' % k,
                (TestRPCRequestDriver, ), {'ocomm_name': k,
                                           'icomm_name': k,
                                           'driver': 'RPCRequestDriver',
                                           'args': 'test'})
    # Flags
    flag_func = None
    if k in ['RMQComm', 'RMQAsyncComm', 'rmq', 'rmq_async']:
        flag_func = unittest.skipIf(not _rmq_installed,
                                    "RMQ Server not running")
    elif k in ['ZMQComm', 'zmq']:
        flag_func = unittest.skipIf(not _zmq_installed,
                                    "ZMQ library not installed")
    elif k in ['IPCComm', 'ipc']:
        flag_func = unittest.skipIf(not _ipc_installed,
                                    "IPC library not installed")
    if flag_func is not None:
        tcls = flag_func(tcls)
    # Add class to globals
    globals()[tcls.__name__] = tcls
    del tcls
