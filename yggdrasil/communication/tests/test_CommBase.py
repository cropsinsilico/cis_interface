import os
import uuid
import unittest
from yggdrasil.tests import YggTestClassInfo, assert_equal
from yggdrasil.communication import new_comm, get_comm, CommBase
from yggdrasil.communication.filters.StatementFilter import StatementFilter
from yggdrasil.communication.filters.FunctionFilter import FunctionFilter


def test_registry():
    r"""Test registry of comm."""
    comm_class = 'CommBase'
    key = 'key1'
    value = None
    assert(not CommBase.is_registered(comm_class, key))
    assert(not CommBase.unregister_comm(comm_class, key))
    assert_equal(CommBase.get_comm_registry(None), {})
    assert_equal(CommBase.get_comm_registry(comm_class), {})
    CommBase.register_comm(comm_class, key, value)
    assert(key in CommBase.get_comm_registry(comm_class))
    assert(CommBase.is_registered(comm_class, key))
    assert(not CommBase.unregister_comm(comm_class, key, dont_close=True))
    CommBase.register_comm(comm_class, key, value)
    assert(not CommBase.unregister_comm(comm_class, key))


class TestCommBase(YggTestClassInfo):
    r"""Tests for CommBase communication class.

    Attributes:
        send_inst_kwargs (dict): Keyword arguments for send half of the comm
            pair.

    """

    comm = 'CommBase'
    attr_list = ['name', 'address', 'direction',
                 'serializer', 'recv_timeout',
                 'close_on_eof_recv', 'opp_address', 'opp_comms',
                 'maxMsgSize']
    use_async = False
    
    @property
    def cleanup_comm_classes(self):
        r"""list: Comm classes that should be cleaned up following the test."""
        return set([self.commtype, self.comm, self.send_inst_kwargs['commtype']])

    @property
    def commtype(self):
        r"""str: Subtype associated with comm class."""
        out = self.import_cls._commtype
        if out is None:
            out = self.comm
        return out

    @property
    def name(self):
        r"""str: Name of the test connection."""
        return 'Test%s_%s' % (self.cls, self.uuid)

    @property
    def cls(self):
        r"""str: Communication class."""
        return self.comm

    @property
    def mod(self):
        r"""str: Absolute module import."""
        return 'yggdrasil.communication.%s' % self.cls

    @property
    def is_installed(self):
        r"""bool: Is the communication class installed."""
        return self.import_cls.is_installed(language='python')

    @property
    def send_inst_kwargs(self):
        r"""dict: Keyword arguments for send instance."""
        out = {'commtype': self.commtype, 'reverse_names': True,
               'direction': 'send', 'use_async': self.use_async}
        out.update(self.testing_options['kwargs'])
        return out

    @property
    def inst_args(self):
        r"""list: Arguments for tested class."""
        return [self.name]

    @property
    def inst_kwargs(self):
        r"""dict: Keyword arguments for tested class."""
        out = self.send_instance.opp_comm_kwargs()
        out['commtype'] = self.commtype
        return out

    @property
    def recv_instance(self):
        r"""Alias for instance."""
        return self.instance

    @property
    def maxMsgSize(self):
        r"""int: Maximum message size."""
        return self.instance.maxMsgSize

    @property
    def test_msg_array(self):
        r"""str: Test message that should be used for any send/recv tests."""
        return self.testing_options.get('msg_array', None)
    
    @property
    def test_msg(self):
        r"""str: Test message that should be used for any send/recv tests."""
        return self.testing_options['msg']

    @property
    def msg_long(self):
        r"""str: Small test message for sending."""
        out = self.test_msg
        if isinstance(out, bytes):
            out += (self.maxMsgSize * b'0')
        return out
            
    def setup(self, *args, **kwargs):
        r"""Initialize comm object pair."""
        assert(self.is_installed)
        sleep_after_connect = kwargs.pop('sleep_after_connect', False)
        send_inst_kwargs = self.send_inst_kwargs
        kwargs.setdefault('nprev_comm', self.comm_count)
        kwargs.setdefault('nprev_fd', self.fd_count)
        self.send_instance = new_comm(self.name, **send_inst_kwargs)
        super(TestCommBase, self).setup(*args, **kwargs)
        if sleep_after_connect:
            self.send_instance.sleep()
        # CommBase is dummy class that never opens
        if self.comm in ['CommBase', 'AsyncComm']:
            assert(not self.send_instance.is_open)
            assert(not self.recv_instance.is_open)
        else:
            assert(self.send_instance.is_open)
            assert(self.recv_instance.is_open)
        self.recv_instance.drain_server_signon_messages()

    def teardown(self, *args, **kwargs):
        r"""Destroy comm object pair."""
        self.remove_instance(self.send_instance)
        super(TestCommBase, self).teardown(*args, **kwargs)

    def create_instance(self):
        r"""Create a new instance of the class."""
        inst = get_comm(*self.inst_args, **self.inst_kwargs)
        assert(isinstance(inst, self.import_cls))
        return inst

    def remove_instance(self, inst):
        r"""Remove an instance."""
        inst.close()
        inst.disconnect()
        assert(inst.is_closed)
        super(TestCommBase, self).remove_instance(inst)

    def get_fresh_error_instance(self, recv=False):
        r"""Get comm instance with ErrorClass parent class."""
        try:
            send_kwargs = self.send_inst_kwargs
            base_commtype = send_kwargs['commtype']
            err_kwargs = dict(base_commtype=base_commtype,
                              commtype='ErrorComm')
            err_name = self.name + '_' + self.uuid
            if not recv:
                send_kwargs.update(**err_kwargs)
            send_inst = new_comm(err_name, **send_kwargs)
            recv_kwargs = send_inst.opp_comm_kwargs()
            recv_kwargs['commtype'] = base_commtype
            if recv:
                recv_kwargs.update(**err_kwargs)
            recv_inst = new_comm(err_name, **recv_kwargs)
        except BaseException as e:  # pragma: debug
            print(e)
            raise
        return send_inst, recv_inst

    def test_empty_obj_recv(self):
        r"""Test identification of empty message."""
        msg = self.instance.empty_obj_recv
        assert(self.instance.is_empty_recv(msg))
        assert(not self.instance.is_empty_recv(self.instance.eof_msg))
            
    def test_error_name(self):
        r"""Test error on missing address."""
        self.assert_raises(RuntimeError, self.import_cls, 'test%s' % uuid.uuid4())

    def test_error_send(self):
        r"""Test error on send."""
        send_inst, recv_inst = self.get_fresh_error_instance()
        send_inst._first_send_done = True
        send_inst.error_replace('_safe_send')
        flag = send_inst.send(self.test_msg)
        assert(not flag)
        send_inst.restore_all()
        send_inst.close()
        recv_inst.close()

    def test_error_recv(self):
        r"""Test error on recv."""
        self.fd_count
        send_inst, recv_inst = self.get_fresh_error_instance(recv=True)
        self.fd_count
        recv_inst.error_replace('_safe_recv')
        if recv_inst.is_async:
            nloop = max(1, recv_inst.backlog_thread.loop_count + 1)
            recv_inst.backlog_thread.wait_for_loop(timeout=10.0,
                                                   key="error_recv",
                                                   nloop=nloop)
        flag, msg_recv = recv_inst.recv(timeout=5.0)
        self.fd_count
        assert(not flag)
        recv_inst.restore_all()
        send_inst.close()
        recv_inst.close()
        self.fd_count

    def test_send_recv_after_close(self):
        r"""Test that opening twice dosn't cause errors and that send/recv after
        close returns false."""
        self.send_instance.open()
        self.recv_instance.open()
        if self.comm in ['RMQComm', 'RMQAsyncComm']:
            self.send_instance.bind()
            self.recv_instance.bind()
        self.send_instance.close()
        self.recv_instance.close()
        assert(self.send_instance.is_closed)
        assert(self.recv_instance.is_closed)
        flag = self.send_instance.send(self.test_msg)
        assert(not flag)
        flag, msg_recv = self.recv_instance.recv()
        assert(not flag)

    def test_attributes(self):
        r"""Assert that the instance has all of the required attributes."""
        for a in self.attr_list:
            if not hasattr(self.send_instance, a):  # pragma: debug
                raise AttributeError("Send comm does not have attribute %s" % a)
            if not hasattr(self.recv_instance, a):  # pragma: debug
                raise AttributeError("Recv comm does not have attribute %s" % a)
            getattr(self.send_instance, a)
            getattr(self.recv_instance, a)
        self.instance.debug('maxMsgSize: %d, %d, %d', self.maxMsgSize,
                            self.send_instance.maxMsgSize,
                            self.recv_instance.maxMsgSize)
        self.instance.opp_comm_kwargs()
        assert(not self.import_cls.is_installed(language='invalid'))

    def test_invalid_direction(self):
        r"""Check that error raised for invalid direction."""
        kwargs = self.send_inst_kwargs
        kwargs['direction'] = 'invalid'
        self.assert_raises(ValueError, new_comm, self.name + "_" + self.uuid,
                           **kwargs)

    def test_work_comm(self):
        r"""Test creating/removing a work comm."""
        if self.comm in ['CommBase', 'AsyncComm']:
            self.assert_raises(CommBase.IncompleteBaseComm,
                               self.instance.create_work_comm)
            self.assert_raises(CommBase.IncompleteBaseComm, getattr,
                               self.instance, 'get_work_comm_kwargs')
            return
        wc_send = self.instance.create_work_comm()
        self.assert_raises(KeyError, self.instance.add_work_comm, wc_send)
        # Create recv instance in way that tests new_comm
        header_recv = dict(id=self.uuid + '1', address=wc_send.address)
        recv_kwargs = self.instance.get_work_comm_kwargs
        recv_kwargs.pop('async_recv_kwargs', None)
        recv_kwargs['work_comm_name'] = 'test_worker_%s' % header_recv['id']
        recv_kwargs['commtype'] = wc_send._commtype
        if isinstance(wc_send.opp_address, str):
            os.environ[recv_kwargs['work_comm_name']] = wc_send.opp_address
        else:
            recv_kwargs['address'] = wc_send.opp_address
        wc_recv = self.instance.create_work_comm(**recv_kwargs)
        # wc_recv = self.instance.get_work_comm(header_recv)
        flag = wc_send.send(self.test_msg)
        assert(flag)
        flag, msg_recv = wc_recv.recv(self.timeout)
        assert(flag)
        self.assert_equal(msg_recv, self.test_msg)
        # Assert errors on second attempt
        # self.assert_raises(RuntimeError, wc_send.send, self.test_msg)
        self.assert_raises(RuntimeError, wc_recv.recv)
        self.instance.remove_work_comm(wc_send.uuid)
        self.instance.remove_work_comm(wc_recv.uuid)
        self.instance.remove_work_comm(wc_recv.uuid)
        # Create work comm that should be cleaned up on teardown
        self.instance.create_work_comm()

    def map_sent2recv(self, obj):
        r"""Convert a sent object into a received one."""
        return obj

    def assert_msg_equal(self, x, y):
        r"""Assert that two messages are equivalent."""
        if not self.send_instance.is_eof(y):
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
        while flag:
            flag, msg_recv = recv_inst.recv()
            if flag:
                if break_on_empty and recv_inst.is_empty_recv(msg_recv):
                    break
                msg_list.append(msg_recv)
            else:
                self.assert_equal(msg_recv, recv_inst.eof_msg)
        if expected_result is not None:
            self.assert_msg_lists_equal(msg_list, expected_result)
        return msg_list

    def do_send_recv(self, send_meth='send', recv_meth='recv',
                     msg_send=None, msg_recv=None,
                     n_msg_send_meth='n_msg_send', n_msg_recv_meth='n_msg_recv',
                     reverse_comms=False, send_kwargs=None, recv_kwargs=None,
                     n_send=1, n_recv=1, print_status=False,
                     close_on_send_eof=None, close_on_recv_eof=None,
                     no_recv=False, recv_timeout=None,
                     n_send_init=0, n_recv_init=0):
        r"""Generic send/recv of a message."""
        tkey = '.do_send_recv'
        is_eof_send = (('eof' in send_meth) or self.send_instance.is_eof(msg_send))
        is_eof_recv = (is_eof_send or self.recv_instance.is_eof(msg_recv))
        if recv_timeout is None:
            recv_timeout = self.timeout
        if msg_send is None:
            if is_eof_send:
                msg_send = self.send_instance.eof_msg
            else:
                msg_send = self.test_msg
        if msg_recv is None:
            msg_recv = msg_send
        if send_kwargs is None:
            send_kwargs = dict()
        if recv_kwargs is None:
            recv_kwargs = dict()
        if is_eof_send:
            send_args = tuple()
        else:
            send_args = (msg_send,)
        self.assert_equal(getattr(self.send_instance, n_msg_send_meth), n_send_init)
        self.assert_equal(getattr(self.recv_instance, n_msg_recv_meth), n_recv_init)
        if reverse_comms:
            send_instance = self.recv_instance
            recv_instance = self.send_instance
            send_instance.direction = 'send'
            recv_instance.direction = 'recv'
        else:
            send_instance = self.send_instance
            recv_instance = self.recv_instance
        if close_on_recv_eof is None:
            close_on_recv_eof = recv_instance.close_on_eof_recv
        if close_on_send_eof is None:
            close_on_send_eof = send_instance.close_on_eof_send
        recv_instance.close_on_eof_recv = close_on_recv_eof
        send_instance.close_on_eof_send = close_on_send_eof
        if self.comm == 'ForkComm':
            for x in recv_instance.comm_list:
                x.close_on_eof_recv = close_on_recv_eof
            for x in send_instance.comm_list:
                x.close_on_eof_send = close_on_send_eof
        fsend_meth = getattr(send_instance, send_meth)
        frecv_meth = getattr(recv_instance, recv_meth)
        if self.comm in ['CommBase', 'AsyncComm']:
            flag = fsend_meth(*send_args, **send_kwargs)
            assert(not flag)
            flag, msg_recv0 = frecv_meth(**recv_kwargs)
            assert(not flag)
        else:
            for i in range(n_send):
                flag = fsend_meth(*send_args, **send_kwargs)
                assert(flag)
            # Wait for messages to be received
            for i in range(n_recv):
                if not (is_eof_recv or no_recv):
                    T = recv_instance.start_timeout(recv_timeout, key_suffix=tkey)
                    while ((not T.is_out) and (not recv_instance.is_closed)
                           and (getattr(recv_instance,
                                        n_msg_recv_meth) == 0)):  # pragma: debug
                        recv_instance.sleep()
                    recv_instance.stop_timeout(key_suffix=tkey)
                    assert(getattr(recv_instance, n_msg_recv_meth) >= 1)
                    # IPC nolimit sends multiple messages
                    # self.assert_equal(recv_instance.n_msg_recv, 1)
                flag, msg_recv0 = frecv_meth(timeout=recv_timeout, **recv_kwargs)
                if is_eof_recv and close_on_recv_eof:
                    assert(not flag)
                    assert(recv_instance.is_closed)
                else:
                    assert(flag)
                self.assert_msg_equal(msg_recv0, msg_recv)
            # Wait for send to close
            if is_eof_send and close_on_send_eof:
                T = send_instance.start_timeout(self.timeout, key_suffix=tkey)
                while (not T.is_out) and (not send_instance.is_closed):  # pragma: debug
                    send_instance.sleep()
                send_instance.stop_timeout(key_suffix=tkey)
                assert(send_instance.is_closed)
        # Make sure no messages outgoing
        T = send_instance.start_timeout(self.timeout, key_suffix=tkey)
        while ((not T.is_out) and (getattr(send_instance,
                                           n_msg_send_meth) != 0)):  # pragma: debug
            send_instance.sleep()
        send_instance.stop_timeout(key_suffix=tkey)
        # Print status of comms
        if print_status:
            send_instance.printStatus()
            recv_instance.printStatus()
        # else:
        #     send_instance.get_status_message()
        #     recv_instance.get_status_message()
        # Confirm recept of messages
        if not (is_eof_send or reverse_comms):
            send_instance.wait_for_confirm(timeout=self.timeout)
            recv_instance.wait_for_confirm(timeout=self.timeout)
            assert(send_instance.is_confirmed)
            assert(recv_instance.is_confirmed)
            send_instance.confirm(noblock=True)
            recv_instance.confirm(noblock=True)
        self.assert_equal(getattr(send_instance, n_msg_send_meth), 0)
        self.assert_equal(getattr(recv_instance, n_msg_recv_meth), 0)
        if reverse_comms:
            send_instance.direction = 'recv'
            recv_instance.direction = 'send'

    def test_cleanup_comms(self):
        r"""Test cleanup_comms for comm class."""
        self.recv_instance.cleanup_comms()
        assert(len(self.recv_instance.comm_registry()) == 0)

    def test_drain_messages(self):
        r"""Test waiting for messages to drain."""
        self.send_instance.drain_messages(timeout=self.timeout)
        self.assert_equal(self.send_instance.n_msg_send_drain, 0)
        if not self.recv_instance.is_file:
            self.recv_instance.drain_messages(timeout=self.timeout)
            self.assert_equal(self.recv_instance.n_msg_recv_drain, 0)
        self.assert_raises(ValueError, self.send_instance.drain_messages,
                           variable='n_msg_invalid')
        self.assert_raises(ValueError, self.recv_instance.drain_messages,
                           variable='n_msg_invalid')

    def test_recv_nomsg(self):
        r"""Test recieve when there is no waiting message."""
        flag, msg_recv = self.recv_instance.recv(timeout=self.sleeptime)
        if self.comm in ['CommBase', 'AsyncComm']:
            assert(not flag)
        else:
            assert(flag)
        assert(not msg_recv)

    def add_filter(self, comm, filter=None):
        r"""Add a filter to a comm.

        Args:
            comm (CommBase): Communication instance to add a filter to.
            filter (FilterBase, optional): Filter class. Defaults to None and is ignored.

        """
        comm.filter = filter

    @property
    def msg_filter_send(self):
        r"""object: Message to filter out on the send side."""
        objs = self.get_options()['objects']
        if len(objs) < 1:  # pragma: debug
            raise unittest.SkipTest("There arn't enough objects.")
        return objs[0]

    @property
    def msg_filter_recv(self):
        r"""object: Message to filter out on the recv side."""
        objs = self.get_options()['objects']
        if len(objs) < 2:  # pragma: debug
            raise unittest.SkipTest("There arn't enough objects.")
        return objs[1]

    @property
    def msg_filter_pass(self):
        r"""object: Message that won't be filtered out on send or recv."""
        objs = self.get_options()['objects']
        out = None
        if len(objs) > 2:
            out = objs[2]
            assert(out != objs[0])
            assert(out != objs[1])
        return out

    def get_filter_statement(self, msg, direction):
        r"""Get a filter statement that filters out the provided message.

        Args:
            msg (object): Message to filter out.
            direction (str): Direction that messages will pass through the filter.

        Returns:
            str: Filter statement.

        """
        # Uncomment this if statements are ever used on the
        # receiving side during tests
        # if direction == 'recv':
        #     msg = self.map_sent2recv(msg)
        if isinstance(msg, (str, bytes)):
            statement = '%x% != ' + repr(msg)
        else:
            statement = 'repr(%x%) != r"""' + repr(msg) + '"""'
        return StatementFilter(statement=statement)

    def get_filter_function(self, msg, direction):
        r"""Get a filter function that filters out the provided message.

        Args:
            msg (object): Message to filter out.
            direction (str): Direction that messages will pass through the filter.

        Returns:
            function: Filter function.

        """
        if direction == 'recv':
            msg = self.map_sent2recv(msg)

        def fcond(x):
            try:
                self.assert_equal(x, msg)
                return False
            except AssertionError:
                return True
        return FunctionFilter(function=fcond)

    def setup_filters(self):
        r"""Add filters to send/recv instances for testing filters."""
        self.add_filter(self.send_instance,
                        self.get_filter_statement(self.msg_filter_send, 'send'))
        self.add_filter(self.recv_instance,
                        self.get_filter_function(self.msg_filter_recv, 'recv'))

    def test_send_recv_filter_eof(self, **kwargs):
        r"""Test send/recv of EOF with filter."""
        if self.comm in ['CommBase', 'AsyncComm']:
            return
        self.setup_filters()
        self.do_send_recv(send_meth='send_eof', **kwargs)

    def test_send_recv_filter_pass(self, **kwargs):
        r"""Test send/recv with filter that passes both messages."""
        if self.comm in ['CommBase', 'AsyncComm']:
            return
        if not self.msg_filter_pass:
            return
        self.setup_filters()
        kwargs.setdefault('msg_send', self.msg_filter_pass)
        kwargs.setdefault('msg_recv', self.msg_filter_pass)
        self.do_send_recv(**kwargs)
        
    def test_send_recv_filter_send_filter(self, **kwargs):
        r"""Test send/recv with filter that blocks send."""
        if self.comm in ['CommBase', 'AsyncComm']:
            return
        self.setup_filters()
        kwargs.setdefault('msg_send', self.msg_filter_send)
        kwargs.setdefault('msg_recv', self.instance.empty_obj_recv)
        kwargs.setdefault('recv_timeout', self.sleeptime)
        kwargs.setdefault('no_recv', True)
        self.do_send_recv(**kwargs)
        
    def test_send_recv_filter_recv_filter(self, **kwargs):
        r"""Test send/recv with filter that blocks recv."""
        if self.comm in ['CommBase', 'AsyncComm']:
            return
        self.setup_filters()
        kwargs.setdefault('msg_send', self.msg_filter_recv)
        kwargs.setdefault('msg_recv', self.instance.empty_obj_recv)
        kwargs.setdefault('recv_timeout', 10 * self.sleeptime)
        if self.instance.is_async:
            kwargs.setdefault('no_recv', True)
        self.do_send_recv(**kwargs)

    def test_send_recv(self):
        r"""Test send/recv of a small message."""
        self.do_send_recv(print_status=True)

    def test_send_recv_raw(self):
        r"""Test send/recv of a small message."""
        if self.comm in ['CommBase', 'AsyncComm', 'ValueComm', 'ForkComm',
                         'ServerComm', 'ClientComm']:
            return

        def dummy(msg):
            print(msg)
            msg.msg = b''
            msg.args = b''
            msg.length = 0
            return msg

        assert(self.send_instance.send(self.test_msg))
        msg = self.recv_instance.recv(
            timeout=60.0, skip_deserialization=True,
            return_message_object=True, after_finalize_message=[dummy])
        assert(msg.finalized)
        assert_equal(self.recv_instance.finalize_message(msg), msg)
        msg.finalized = False
        assert(self.recv_instance.is_empty_recv(msg.args))
        msg = self.recv_instance.finalize_message(msg)
        assert_equal(msg.flag, CommBase.FLAG_EMPTY)

    def test_send_recv_nolimit(self):
        r"""Test send/recv of a large message."""
        assert(len(self.msg_long) > self.maxMsgSize)
        self.do_send_recv('send_nolimit', 'recv_nolimit', self.msg_long,
                          send_kwargs=dict(header_kwargs=dict(x=self.msg_long)),
                          print_status=True)

    def test_send_recv_array(self):
        r"""Test send/recv of a array message."""
        msg_send = getattr(self, 'test_msg_array', None)
        self.do_send_recv('send_array', 'recv_array', msg_send=msg_send)

    def test_eof(self):
        r"""Test send/recv of EOF message."""
        self.do_send_recv(send_meth='send_eof')

    def test_eof_no_close(self):
        r"""Test send/recv of EOF message with no close."""
        self.do_send_recv(send_meth='send_eof', close_on_recv_eof=False)

    def test_purge(self, nrecv=1, nrecv_init=0, nsend_init=0):
        r"""Test purging messages from the comm."""
        self.assert_equal(self.send_instance.n_msg, nsend_init)
        self.assert_equal(self.recv_instance.n_msg, nrecv_init)
        if self.send_instance.is_async:
            self.assert_equal(self.send_instance.n_msg_direct, 0)
        if self.recv_instance.is_async:
            self.assert_equal(self.recv_instance.n_msg_direct, 0)
        # Purge recv while open
        if self.comm not in ['CommBase', 'AsyncComm']:
            flag = self.send_instance.send(self.test_msg)
            assert(flag)
            T = self.recv_instance.start_timeout()
            while ((not T.is_out) and (self.recv_instance.n_msg
                                       != nrecv)):  # pragma: debug
                self.recv_instance.sleep()
            self.recv_instance.stop_timeout()
            self.assert_greater(self.recv_instance.n_msg, 0)
        self.recv_instance.purge()
        # Uni-directional comms can't know about messages sent
        # self.assert_equal(self.send_instance.n_msg, 0)
        self.assert_equal(self.recv_instance.n_msg, 0)
        # Purge recv while closed
        self.recv_instance.close()
        self.recv_instance.purge()

    def test_send_recv_dict(self):
        r"""Test send/recv message as dict."""
        msg_send = self.testing_options['dict']
        if msg_send:
            self.do_send_recv(send_meth='send_dict',
                              recv_meth='recv_dict',
                              msg_send=msg_send)
        
    def test_send_recv_dict_names(self):
        r"""Test send/recv message as dict with names."""
        msg_send = self.testing_options['dict']
        field_order = self.testing_options.get('field_names', None)
        if field_order is not None:
            self.do_send_recv(send_meth='send_dict', recv_meth='recv_dict',
                              msg_send=msg_send,
                              send_kwargs={'field_order': field_order},
                              recv_kwargs={'field_order': field_order})
