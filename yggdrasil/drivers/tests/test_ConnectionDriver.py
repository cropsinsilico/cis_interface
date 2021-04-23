import pytest
import unittest
from yggdrasil import tools, platform
from yggdrasil.tests import MagicTestError, assert_raises, timeout
from yggdrasil.schema import get_schema
from yggdrasil.components import import_component
from yggdrasil.drivers.tests import test_Driver as parent
from yggdrasil.drivers.ConnectionDriver import ConnectionDriver
from yggdrasil.communication import (
    new_comm, CommBase, ZMQComm, IPCComm, RMQComm, MPIComm)


_default_comm = tools.get_default_comm()
_zmq_installed = ZMQComm.ZMQComm.is_installed(language='python')
_ipc_installed = IPCComm.IPCComm.is_installed(language='python')
_rmq_installed = RMQComm.RMQComm.is_installed(language='python')
_mpi_installed = MPIComm.MPIComm.is_installed(language='python')


@unittest.skipIf(platform._is_win, ("Temp skip connection tests on windows for "
                                    "time's sake."))
class TestConnectionParam(parent.TestParam):
    r"""Test parameters for the ConnectionDriver class."""

    comm_name = _default_comm
    icomm_name = _default_comm
    ocomm_name = _default_comm
    testing_option_kws = {}
    driver = 'ConnectionDriver'
    
    def __init__(self, *args, **kwargs):
        super(TestConnectionParam, self).__init__(*args, **kwargs)
        self.attr_list += ['icomm_kws', 'ocomm_kws', 'icomm', 'ocomm',
                           'nrecv', 'nproc', 'nsent', 'state', 'translator']
        # self.timeout = 1.0

    @property
    def description_prefix(self):
        r"""String prefix to prepend docstr test message with."""
        out = super(TestConnectionParam, self).description_prefix
        return '%s(%s, %s)' % (out, self.icomm_name, self.ocomm_name)

    @property
    def maxMsgSize(self):
        r"""int: Maximum message size."""
        return min(self.instance.icomm.maxMsgSize,
                   self.instance.ocomm.maxMsgSize)

    @property
    def is_output(self):
        r"""bool: True if the connection is for output."""
        return (self.ocomm_name != self.comm_name)
    
    def map_sent2recv(self, obj):
        r"""Convert a sent object into a received one."""
        return obj

    def assert_msg_equal(self, x, y):
        r"""Assert that two messages are equivalent."""
        if not self.send_comm.is_eof(y):
            y = self.map_sent2recv(y)
        self.assert_equal(x, y)

    def assert_msg_lists_equal(self, x, y):
        r"""Assert that two lists of messages are equivalent."""
        self.assert_equal(len(x), len(y))
        for ix, iy in zip(x, y):
            self.assert_msg_equal(ix, iy)

    def recv_message_list(self, recv_inst, expected_result=None,
                          break_on_empty=False):
        r"""Continue receiving from a receive instance until flag is False (or
        an empty messages is received and break_on_empty is True). On receipt of
        a False flag, the recieved message is checked against the EOF message.

        Args:
            recv_inst (yggdrasil.communication.CommBase.CommBase): Communication
                instance that should be received from.
            expected_result (list, optional): A list of messages that the
                recieved messages should be compared against. Defaults to None
                and is ignored.
            break_on_empty (bool, optional): If True, messages will stop being
                received from the communication instance when an empty message
                is received. Defaults to False.

        Returns:
            list: Received messages.

        """
        flag = True
        msg_list = []
        timeout = 10.0
        Tout = self.instance.start_timeout(timeout, key_suffix='.stoptest')
        while flag and (not Tout.is_out):
            flag, msg_recv = recv_inst.recv(self.timeout)
            if flag:
                if break_on_empty and recv_inst.is_empty_recv(msg_recv):
                    break  # pragma: no cover
                msg_list.append(msg_recv)
            else:
                self.assert_equal(msg_recv, recv_inst.eof_msg)
        self.instance.stop_timeout(key_suffix='.stoptest')
        if expected_result is not None:
            self.assert_msg_lists_equal(msg_list, expected_result)
        return msg_list

    def get_options(self):
        r"""Get testing options."""
        if self.is_output:
            out = self.ocomm_import_cls.get_testing_options(
                **self.testing_option_kws)
        else:
            out = self.icomm_import_cls.get_testing_options(
                **self.testing_option_kws)
        return out
    
    @property
    def cleanup_comm_classes(self):
        r"""list: Comm classes that should be cleaned up following the test."""
        comms = set([self.comm_name, self.icomm_name, self.ocomm_name])
        return comms

    @property
    def inputs(self):
        r"""list: List of keyword arguments for connection input comms."""
        out = [{'name': self.icomm_name, 'commtype': self.icomm_name}]
        if not self.is_output:
            out[0].update(self.testing_options['kwargs'])
        return out

    @property
    def outputs(self):
        r"""list: List of keyword arguments for connection output comms."""
        out = [{'name': self.ocomm_name, 'commtype': self.ocomm_name}]
        if self.is_output:
            out[0].update(self.testing_options['kwargs'])
        return out

    @property
    def icomm_import_cls(self):
        r"""class: Class used for connection input comm."""
        return import_component('comm', self.icomm_name)

    @property
    def ocomm_import_cls(self):
        r"""class: Class used for connection output comm."""
        return import_component('comm', self.ocomm_name)

    @property
    def send_comm_kwargs(self):
        r"""dict: Keyword arguments for send comm."""
        out = self.instance.icomm.opp_comm_kwargs()
        if self.icomm_name == 'value':
            out['direction'] = 'recv'
        return out

    @property
    def recv_comm_kwargs(self):
        r"""dict: Keyword arguments for recv comm."""
        return self.instance.ocomm.opp_comm_kwargs()

    @property
    def inst_kwargs(self):
        r"""dict: Keyword arguments for tested class."""
        out = super(TestConnectionParam, self).inst_kwargs
        out['inputs'] = self.inputs
        out['outputs'] = self.outputs
        return out

    @property
    def test_msg(self):
        r"""str: Test message that should be used for any send/recv tests."""
        return self.testing_options['msg']

    @property
    def msg_long(self):
        r"""str: Small test message for sending."""
        msg_short = self.test_msg
        if isinstance(msg_short, bytes):
            out = msg_short + (self.maxMsgSize * b'0')
        else:  # pragma: debug
            out = msg_short
        # return self.testing_options['msg_long']
        return out
    
    def setup(self, *args, **kwargs):
        r"""Initialize comm object pair."""
        super(TestConnectionParam, self).setup(*args, **kwargs)
        if not self.skip_init:
            send_kws = self.send_comm_kwargs
            recv_kws = self.recv_comm_kwargs
            if self.skip_start:
                send_kws['dont_open'] = True
                recv_kws['dont_open'] = True
            self.send_comm = new_comm(self.name, **send_kws)
            self.recv_comm = new_comm(self.name, **recv_kws)

    def teardown(self, *args, **kwargs):
        r"""Destroy comm object pair."""
        if not self.skip_init:
            self.send_comm.close()
            self.recv_comm.close()
            assert(self.send_comm.is_closed)
            assert(self.recv_comm.is_closed)
        super(TestConnectionParam, self).teardown(*args, **kwargs)

    def create_error_instance(self, comm=None, inst_class=None, args=None,
                              kwargs=None, error_class=None, error_on_init=False):
        r"""Create a new instance of the class where one or both comms is
        wrapped in ErrorClass."""
        if inst_class is None:
            inst_class = self.import_cls
        if args is None:
            args = [self.get_fresh_name()]
            if self.args is not None:
                args.append(self.args)
        if kwargs is None:
            kwargs = self.inst_kwargs
        # Adjust kwargs
        if comm in ['ocomm', 'both']:
            for x in kwargs['outputs']:
                x.update(base_commtype=self.ocomm_name,
                         commtype='ErrorComm',
                         error_on_init=error_on_init)
        if comm in ['icomm', 'both']:
            for x in kwargs['inputs']:
                x.update(base_commtype=self.icomm_name,
                         commtype='ErrorComm',
                         error_on_init=error_on_init)
        # Get error class
        if (error_class is None) and (comm in ['ocomm', 'icomm', 'both']):
            error_class = inst_class
        out = super(TestConnectionParam, self).create_error_instance(
            inst_class=inst_class, args=args, kwargs=kwargs,
            error_class=error_class, error_on_init=error_on_init)
        if (not error_on_init) and (comm is not None):
            out.icomm._first_send_done = True
        return out
            

class TestConnectionDriverNoStart(TestConnectionParam, parent.TestDriverNoStart):
    r"""Test class for the ConnectionDriver class without start."""

    def test_manipulate_shared_event(self):
        r"""Test setting and clearing events in the shared dictionary."""
        self.instance.set_flag_attr('_skip_after_loop')
        assert(self.instance.check_flag_attr('_skip_after_loop'))
        self.instance.clear_flag_attr('_skip_after_loop')
        assert(not self.instance.check_flag_attr('_skip_after_loop'))

    def test_send_recv(self):
        r"""Test sending/receiving with queues closed."""
        self.instance.close_comm()
        self.send_comm.close()
        self.recv_comm.close()
        assert(self.instance.is_comm_closed)
        assert(self.send_comm.is_closed)
        assert(self.recv_comm.is_closed)
        flag = self.instance.send_message(CommBase.CommMessage(args=self.test_msg))
        assert(not flag)
        flag = self.instance.recv_message()
        if self.instance.icomm._commtype != 'value':
            assert(not flag)
        # Short
        if self.instance.icomm._commtype != 'value':
            flag = self.send_comm.send(self.test_msg)
            assert(not flag)
        flag, ret = self.recv_comm.recv()
        if self.instance.icomm._commtype != 'value':
            assert(not flag)
            self.assert_equal(ret, None)
        # Long
        if self.instance.icomm._commtype != 'value':
            flag = self.send_comm.send_nolimit(self.test_msg)
            assert(not flag)
        flag, ret = self.recv_comm.recv_nolimit()
        if self.instance.icomm._commtype != 'value':
            assert(not flag)
            self.assert_equal(ret, None)
        self.instance.confirm_output(timeout=1.0)

        
class TestConnectionDriverNoInit(TestConnectionParam):
    r"""Test class for the ConnectionDriver class without init."""
    
    def test_error_init_ocomm(self):
        r"""Test forwarding of error from init of ocomm."""
        self.create_error_instance(comm='ocomm', error_on_init=True)

    def test_error_open_icomm(self):
        r"""Test fowarding of error from open of icomm."""
        inst = self.create_error_instance(comm='icomm')
        inst.icomm.error_replace('open')
        self.assert_raises(MagicTestError, inst.open_comm)
        assert(inst.icomm.is_closed)
        inst.icomm.restore_all()

    def test_error_close_icomm(self):
        r"""Test forwarding of error from close of icomm."""
        inst = self.create_error_instance(comm='icomm')
        inst.open_comm()
        inst.icomm.error_replace('close')
        self.assert_raises(MagicTestError, inst.close_comm)
        assert(inst.ocomm.is_closed)
        inst.icomm.restore_all()
        inst.icomm.close()
        assert(inst.icomm.is_closed)
        
    def test_error_close_ocomm(self):
        r"""Test forwarding of error from close of ocomm."""
        inst = self.create_error_instance(comm='ocomm')
        inst.open_comm()
        inst.ocomm.error_replace('close')
        self.assert_raises(MagicTestError, inst.close_comm)
        assert(inst.icomm.is_closed)
        inst.ocomm.restore_all()
        inst.ocomm.close()
        assert(inst.ocomm.is_closed)

    def test_error_open_fails(self):
        r"""Test error raised when comms fail to open."""
        inst = self.create_error_instance(comm='both')
        old_timeout = inst.timeout
        inst.icomm.empty_replace('open')
        inst.ocomm.empty_replace('open')
        inst.timeout = inst.sleeptime / 2.0
        self.assert_raises(Exception, inst.start)
        inst.timeout = old_timeout
        inst.icomm.restore_all()
        inst.ocomm.restore_all()
        inst.close_comm()
        assert(inst.is_comm_closed)


class TestConnectionDriver(TestConnectionParam, parent.TestDriver):
    r"""Test class for the ConnectionDriver class."""

    def setup(self, *args, **kwargs):
        r"""Initialize comm object pair."""
        super(TestConnectionDriver, self).setup(*args, **kwargs)
        # CommBase is dummy class that never opens
        if (self.send_comm._commtype is not None):
            assert(self.send_comm.is_open)
        if (self.recv_comm._commtype is not None):
            assert(self.recv_comm.is_open)
        self.nmsg_recv = 1
        if self.instance.icomm._commtype == 'value':
            self.nmsg_recv = self.get_options()['kwargs']['count']
        T = self.instance.start_timeout()
        while ((not T.is_out) and (not self.instance.is_valid)):
            self.instance.sleep()  # pragma: debug
        self.instance.stop_timeout()
        self.recv_comm.drain_server_signon_messages()

    def test_init_del(self):
        r"""Test driver creation and deletion."""
        self.instance.printStatus(verbose=True)

    def test_early_close(self):
        r"""Test early deletion of message queue."""
        self.instance.close_comm()
        self.instance.open_comm()
        assert(self.instance.is_comm_closed)

    @timeout(timeout=600)
    def test_send_recv(self):
        r"""Test sending/receiving small message."""
        try:
            if self.instance.icomm._commtype != 'value':
                flag = self.send_comm.send(self.test_msg)
                if self.comm_name != 'CommBase':
                    assert(flag)
            # self.instance.sleep()
            # if self.comm_name != 'CommBase':
            #     self.assert_equal(self.recv_comm.n_msg, 1)
            for i in range(self.nmsg_recv):
                flag, msg_recv = self.recv_comm.recv(timeout=self.timeout)
                if self.comm_name != 'CommBase':
                    assert(flag)
                    self.assert_msg_equal(msg_recv, self.test_msg)
            if (self.comm_name != 'CommBase') and (self.icomm_name != 'value'):
                self.assert_equal(self.instance.n_msg, 0)
        except BaseException:  # pragma: debug
            self.send_comm.printStatus()
            self.instance.printStatus(verbose=True)
            self.recv_comm.printStatus()
            raise

    @timeout(timeout=600)
    def test_send_recv_nolimit(self):
        r"""Test sending/receiving large message."""
        try:
            if self.instance.icomm._commtype != 'value':
                assert(len(self.msg_long) > self.maxMsgSize)
                flag = self.send_comm.send_nolimit(self.msg_long)
                if self.comm_name != 'CommBase':
                    assert(flag)
            for i in range(self.nmsg_recv):
                flag, msg_recv = self.recv_comm.recv_nolimit(timeout=self.timeout)
                if self.comm_name != 'CommBase':
                    assert(flag)
                    self.assert_msg_equal(msg_recv, self.msg_long)
        except BaseException:  # pragma: debug
            self.send_comm.printStatus()
            self.instance.printStatus(verbose=True)
            self.recv_comm.printStatus()
            raise

    def assert_before_stop(self, check_open=True):
        r"""Assertions to make before stopping the driver instance."""
        super(TestConnectionDriver, self).assert_before_stop()
        if (((self.comm_name != 'CommBase') and (self.icomm_name != 'value')
             and check_open)):
            assert(self.instance.is_comm_open)

    def run_before_terminate(self):
        r"""Commands to run while the instance is running, before terminate."""
        super(TestConnectionDriver, self).run_before_terminate()
        # TODO: This fails with ZMQ
        # self.send_comm.send(self.test_msg)

    def assert_after_terminate(self):
        r"""Assertions to make after terminating the driver instance."""
        super(TestConnectionDriver, self).assert_after_terminate()
        assert(self.instance.is_comm_closed)


class TestConnectionDriverFork(TestConnectionDriver):
    r"""Test class for the ConnectionDriver class between fork comms."""

    def setup(self, *args, **kwargs):
        r"""Initialize comm object pair."""
        self.ncomm_input = 2
        self.ncomm_output = 1
        super(TestConnectionDriverFork, self).setup(*args, **kwargs)
        self.nmsg_recv = self.ncomm_input * self.ncomm_output

    @property
    def inst_kwargs(self):
        r"""dict: Keyword arguments for tested class."""
        out = super(TestConnectionDriverFork, self).inst_kwargs
        out['inputs'] = [None for i in range(self.ncomm_input)]
        return out


invalid_translate = True


class TestConnectionDriverTranslate(TestConnectionDriver):
    r"""Test class for the ConnectionDriver class with translator."""

    test_send_recv_nolimit = None

    @property
    def inst_kwargs(self):
        r"""dict: Keyword arguments for tested class."""
        out = super(TestConnectionDriverTranslate, self).inst_kwargs
        out['translator'] = {'transformtype': 'select_fields',
                             'selected': ['a'],
                             'single_as_scalar': True}
        out['onexit'] = 'printStatus'
        return out

    @property
    def test_msg(self):
        r"""str: Test message that should be used for any send/recv tests."""
        return {'a': int(1), 'b': float(2)}

    def map_sent2recv(self, obj):
        r"""Convert a sent object into a received one."""
        return obj['a']
    

class TestConnectionDriverIterate(TestConnectionDriver):
    r"""Test class for the ConnectionDriver class with iteration."""

    test_send_recv_nolimit = None

    @property
    def inst_kwargs(self):
        r"""dict: Keyword arguments for tested class."""
        out = super(TestConnectionDriverIterate, self).inst_kwargs
        out['translator'] = [{'transformtype': 'select_fields',
                              'selected': ['a', 'b']},
                             {'transformtype': 'iterate'}]
        out['onexit'] = 'printStatus'
        return out

    @property
    def test_msg(self):
        r"""str: Test message that should be used for any send/recv tests."""
        return {'a': int(1), 'b': 'hello', 'c': float(2)}

    @timeout(timeout=600)
    def test_send_recv(self):
        r"""Test sending/receiving small message."""
        msg = self.test_msg
        flag = self.send_comm.send(msg)
        assert(flag)
        for imsg in [v for k, v in msg.items() if k in ['a', 'b']]:
            flag, msg_recv = self.recv_comm.recv(self.timeout)
            assert(flag)
            self.assert_msg_equal(msg_recv, imsg)
        self.assert_equal(self.instance.n_msg, 0)


class TestConnectionDriverProcess(TestConnectionDriver):
    r"""Test class for the TestConnectionDriver using process."""

    icomm_name = 'buffer'
    
    @property
    def inst_kwargs(self):
        r"""dict: Keyword arguments for tested class."""
        out = super(TestConnectionDriverProcess, self).inst_kwargs
        out['task_method'] = 'process'
        return out


def test_ConnectionDriverOnexit_errors():
    r"""Test that errors are raised for invalid onexit."""
    assert_raises(ValueError, ConnectionDriver, 'test',
                  onexit='invalid')


def test_ConnectionDriverTranslate_errors():
    r"""Test that errors are raised for invalid translators."""
    assert(not hasattr(invalid_translate, '__call__'))
    assert_raises(ValueError, ConnectionDriver, 'test',
                  translator=invalid_translate)

    
# Dynamically create tests based on registered comm classes
s = get_schema()
comm_types = s['comm'].subtypes
for k in comm_types:
    if k in _default_comm:  # pragma: debug
        continue
    # Output
    ocls = type('Test%sOutputDriver' % k.title(),
                (TestConnectionDriver, ), {'ocomm_name': k,
                                           'driver': 'OutputDriver',
                                           'args': 'test'})
    # Input
    icls = type('Test%sInputDriver' % k.title(),
                (TestConnectionDriver, ), {'icomm_name': k,
                                           'driver': 'InputDriver',
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
    elif k in ['MPIComm', 'mpi']:
        flag_func = [unittest.skipIf(not _mpi_installed,
                                     "MPI library not installed"),
                     pytest.mark.mpi(min_size=2)]
    if flag_func is not None:
        if not isinstance(flag_func, list):
            flag_func = [flag_func]
        for x in flag_func:
            ocls = x(ocls)
            icls = x(icls)
    # Add class to globals
    if k != 'value':
        globals()[ocls.__name__] = ocls
    globals()[icls.__name__] = icls
    del ocls, icls
