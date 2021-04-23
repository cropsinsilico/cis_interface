import pytest
from yggdrasil.tests import assert_equal
from yggdrasil.communication import CommBase
from yggdrasil.communication.tests import test_CommBase


_tag = 0


@pytest.mark.mpi(min_size=2)
class TestMPIComm(test_CommBase.TestCommBase):
    r"""Test class for MPIComm."""
    # Rank 0 sends, rank 1 receives

    comm = 'MPIComm'
    test_error_send = None
    test_error_recv = None
    test_invalid_direction = None

    def __init__(self, *args, **kwargs):
        from mpi4py import MPI
        self.mpi_comm = MPI.COMM_WORLD
        self.mpi_rank = self.mpi_comm.Get_rank()
        self._recv_kws = {}
        super(TestMPIComm, self).__init__(*args, **kwargs)

    @property
    def inst_kwargs(self):
        r"""dict: Keyword arguments for tested class."""
        global _tag
        if self.mpi_rank == 0:
            out = self.send_inst_kwargs
            out['start_tag'] = _tag
            out['partner_mpi_ranks'] = [1]
        elif self.mpi_rank == 1:
            out = self._recv_kws
            out['start_tag'] = _tag
            out['commtype'] = self.commtype
        _tag += 1
        return out
    
    @property
    def recv_instance(self):
        r"""Alias for instance."""
        if self.mpi_rank == 1:
            return self.instance

    @property
    def send_instance(self):
        r"""Alias for instance."""
        if self.mpi_rank == 0:
            return self.instance
        
    def setup(self, *args, **kwargs):
        r"""Initialize comm object pair."""
        global _tag
        assert(self.is_installed)
        sleep_after_connect = kwargs.pop('sleep_after_connect', False)
        kwargs.setdefault('nprev_comm', self.comm_count)
        kwargs.setdefault('nprev_fd', self.fd_count)
        init_tag = _tag
        _tag += 1
        if self.mpi_rank == 1:
            self._recv_kws = self.mpi_comm.recv(source=0, tag=init_tag)
        super(test_CommBase.TestCommBase, self).setup(*args, **kwargs)
        if self.mpi_rank == 0:
            recv_kws = self.instance.opp_comm_kwargs()
            self.mpi_comm.send(recv_kws, dest=1, tag=init_tag)
        if sleep_after_connect:
            self.instance.sleep()
        assert(self.instance.is_open)
        if self.instance.direction == 'recv':
            self.instance.drain_server_signon_messages()

    def sync(self, check_equal=False):
        global _tag
        all_tag = self.mpi_comm.alltoall(
            [self.instance.tag] * self.mpi_comm.Get_size())
        if check_equal:
            assert(all((x == self.instance.tag) for x in all_tag))
        _tag = all_tag[self.mpi_rank]
        return all_tag

    def teardown(self, *args, **kwargs):
        r"""Destroy comm object pair."""
        # Even up send/recv calls since the same comm will be used for
        # subsequent tests
        global _tag
        if self.use_async and (self.instance.direction == 'recv'):
            # Don't keep receiving or there will never be a balence
            # between receive requests and sent messages
            self.instance._close_backlog(wait=True)
        all_tag = self.sync()
        if self.instance.direction == 'send':
            for _ in range(max(all_tag) - all_tag[self.mpi_rank]):
                self.instance.tag += 1
                # self.instance.send_eof()
            if self.use_async:
                self.instance.wait_for_confirm(timeout=60.0)
        self.sync(check_equal=True)
        super(test_CommBase.TestCommBase, self).teardown(*args, **kwargs)

    def test_send_recv_after_close(self):
        r"""Test that opening twice dosn't cause errors and that send/recv after
        close returns false."""
        self.instance.open()
        self.instance.close()
        assert(self.instance.is_closed)
        if self.instance.direction == 'send':
            flag = self.instance.send(self.test_msg)
        elif self.instance.direction == 'recv':
            flag, msg_recv = self.instance.recv()
        assert(not flag)

    def test_attributes(self):
        r"""Assert that the instance has all of the required attributes."""
        for a in self.attr_list:
            if not hasattr(self.instance, a):  # pragma: debug
                raise AttributeError("%s comm does not have attribute %s"
                                     % (self.instance.direction, a))
            getattr(self.instance, a)
        self.instance.debug('maxMsgSize: %d, %d', self.maxMsgSize,
                            self.instance.maxMsgSize)
        self.instance.opp_comm_kwargs()
        assert(not self.import_cls.is_installed(language='invalid'))

    def test_work_comm(self):
        r"""Test creating/removing a work comm."""
        pass
        # wc_send = self.instance.create_work_comm()
        # self.assert_raises(KeyError, self.instance.add_work_comm, wc_send)
        # # Create recv instance in way that tests new_comm
        # header_recv = dict(id=self.uuid + '1', address=wc_send.address)
        # recv_kwargs = self.instance.get_work_comm_kwargs
        # recv_kwargs.pop('async_recv_kwargs', None)
        # recv_kwargs['work_comm_name'] = 'test_worker_%s' % header_recv['id']
        # recv_kwargs['commtype'] = wc_send._commtype
        # if isinstance(wc_send.opp_address, str):
        #     os.environ[recv_kwargs['work_comm_name']] = wc_send.opp_address
        # else:
        #     recv_kwargs['address'] = wc_send.opp_address
        # wc_recv = self.instance.create_work_comm(**recv_kwargs)
        # # wc_recv = self.instance.get_work_comm(header_recv)
        # flag = wc_send.send(self.test_msg)
        # assert(flag)
        # flag, msg_recv = wc_recv.recv(self.timeout)
        # assert(flag)
        # self.assert_equal(msg_recv, self.test_msg)
        # # Assert errors on second attempt
        # # self.assert_raises(RuntimeError, wc_send.send, self.test_msg)
        # self.assert_raises(RuntimeError, wc_recv.recv)
        # self.instance.remove_work_comm(wc_send.uuid)
        # self.instance.remove_work_comm(wc_recv.uuid)
        # self.instance.remove_work_comm(wc_recv.uuid)
        # # Create work comm that should be cleaned up on teardown
        # self.instance.create_work_comm()

    def assert_msg_equal(self, x, y):
        r"""Assert that two messages are equivalent."""
        if not self.instance.is_eof(y):
            y = self.map_sent2recv(y)
        self.assert_equal(x, y)

    def do_send_recv(self, send_meth='send', recv_meth='recv',
                     msg_send=None, msg_recv=None,
                     n_msg_send_meth='n_msg_send', n_msg_recv_meth='n_msg_recv',
                     reverse_comms=False, send_kwargs=None, recv_kwargs=None,
                     n_send=1, n_recv=1, print_status=False,
                     close_on_send_eof=None, close_on_recv_eof=None,
                     no_recv=False, recv_timeout=None,
                     n_send_init=0, n_recv_init=0):
        r"""Generic send/recv of a message."""
        assert(not reverse_comms)
        is_eof_send = (('eof' in send_meth) or self.instance.is_eof(msg_send))
        if msg_send is None:
            if is_eof_send:
                msg_send = self.instance.eof_msg
            else:
                msg_send = self.test_msg
        if msg_recv is None:
            msg_recv = msg_send
        if self.instance.direction == 'send':
            self.do_send(send_meth=send_meth, msg_send=msg_send,
                         n_msg_send_meth=n_msg_send_meth,
                         send_kwargs=send_kwargs, n_send=n_send,
                         print_status=print_status,
                         close_on_send_eof=close_on_send_eof,
                         n_send_init=n_send_init,
                         is_eof_send=is_eof_send)
        else:
            self.do_recv(recv_meth=recv_meth, msg_recv=msg_recv,
                         n_msg_recv_meth=n_msg_recv_meth,
                         recv_kwargs=recv_kwargs, n_recv=n_recv,
                         print_status=print_status,
                         close_on_recv_eof=close_on_recv_eof,
                         no_recv=no_recv, recv_timeout=recv_timeout,
                         n_recv_init=n_recv_init,
                         is_eof_send=is_eof_send)
        
    def do_send(self, send_meth='send', msg_send=None,
                n_msg_send_meth='n_msg_send',
                send_kwargs=None, n_send=1, print_status=False,
                close_on_send_eof=None, n_send_init=0, is_eof_send=False):
        r"""Generic send of a message."""
        assert(self.mpi_rank == 0)
        tkey = '.do_send'
        if send_kwargs is None:
            send_kwargs = dict()
        if is_eof_send:
            send_args = tuple()
        else:
            send_args = (msg_send,)
        self.assert_equal(getattr(self.send_instance, n_msg_send_meth), n_send_init)
        self.sync()
        send_instance = self.send_instance
        if close_on_send_eof is None:
            close_on_send_eof = send_instance.close_on_eof_send
        send_instance.close_on_eof_send = close_on_send_eof
        fsend_meth = getattr(send_instance, send_meth)
        for i in range(n_send):
            flag = fsend_meth(*send_args, **send_kwargs)
            assert(flag)
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
        # Confirm recept of messages
        if not is_eof_send:
            send_instance.wait_for_confirm(timeout=self.timeout)
            assert(send_instance.is_confirmed)
            send_instance.confirm(noblock=True)
        self.assert_equal(getattr(send_instance, n_msg_send_meth), 0)
        self.sync()

    def do_recv(self, recv_meth='recv', msg_recv=None,
                n_msg_recv_meth='n_msg_recv',
                recv_kwargs=None, n_recv=1, print_status=False,
                close_on_recv_eof=None, no_recv=False, recv_timeout=None,
                n_recv_init=0, is_eof_send=False):
        r"""Generic recv of a message."""
        assert(self.mpi_rank == 1)
        tkey = '.do_send_recv'
        is_eof_recv = (is_eof_send or self.recv_instance.is_eof(msg_recv))
        if recv_timeout is None:
            recv_timeout = self.timeout
        if recv_kwargs is None:
            recv_kwargs = dict()
        self.assert_equal(getattr(self.recv_instance, n_msg_recv_meth), n_recv_init)
        self.sync()
        recv_instance = self.recv_instance
        if close_on_recv_eof is None:
            close_on_recv_eof = recv_instance.close_on_eof_recv
        recv_instance.close_on_eof_recv = close_on_recv_eof
        frecv_meth = getattr(recv_instance, recv_meth)
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
        # Print status of comms
        if print_status:
            recv_instance.printStatus()
        # Confirm recept of messages
        if not is_eof_send:
            recv_instance.wait_for_confirm(timeout=self.timeout)
            assert(recv_instance.is_confirmed)
            recv_instance.confirm(noblock=True)
        self.assert_equal(getattr(recv_instance, n_msg_recv_meth), 0)
        self.sync()

    def test_cleanup_comms(self):
        r"""Test cleanup_comms for comm class."""
        self.instance.cleanup_comms()
        assert(len(self.instance.comm_registry()) == 0)

    def test_drain_messages(self):
        r"""Test waiting for messages to drain."""
        self.instance.drain_messages(timeout=self.timeout)
        self.assert_equal(
            getattr(self.instance,
                    'n_msg_%s_drain' % self.instance.direction), 0)
        self.assert_raises(ValueError, self.instance.drain_messages,
                           variable='n_msg_invalid')

    def test_recv_nomsg(self):
        r"""Test recieve when there is no waiting message."""
        if self.instance.direction == 'recv':
            flag, msg_recv = self.recv_instance.recv(timeout=self.sleeptime)
            assert(flag)
            assert(not msg_recv)

    def setup_filters(self):
        r"""Add filters to send/recv instances for testing filters."""
        if self.instance.direction == 'send':
            self.add_filter(self.send_instance,
                            self.get_filter_statement(self.msg_filter_send,
                                                      'send'))
        else:
            self.add_filter(self.recv_instance,
                            self.get_filter_function(self.msg_filter_recv,
                                                     'recv'))

    def test_send_recv_raw(self):
        r"""Test send/recv of a small message."""
        def dummy(msg):
            print(msg)
            msg.msg = b''
            msg.args = b''
            msg.length = 0
            return msg

        if self.instance.direction == 'send':
            assert(self.send_instance.send(self.test_msg))
        else:
            msg = self.recv_instance.recv(
                timeout=60.0, skip_deserialization=True,
                return_message_object=True, after_finalize_message=[dummy])
            assert(msg.finalized)
            assert_equal(self.recv_instance.finalize_message(msg), msg)
            msg.finalized = False
            assert(self.recv_instance.is_empty_recv(msg.args))
            msg = self.recv_instance.finalize_message(msg)
            assert_equal(msg.flag, CommBase.FLAG_EMPTY)

    def test_purge(self, nrecv=1, nrecv_init=0, nsend_init=0):
        r"""Test purging messages from the comm."""
        if self.instance.direction == 'send':
            self.assert_equal(self.send_instance.n_msg, nsend_init)
            if self.send_instance.is_async:
                self.assert_equal(self.send_instance.n_msg_direct, 0)
            self.sync()
            flag = self.send_instance.send(self.test_msg)
            assert(flag)
            # self.send_instance.purge()
            # self.assert_equal(self.send_instance.n_msg, 0)
            self.sync()
        else:
            self.assert_equal(self.recv_instance.n_msg, nrecv_init)
            if self.recv_instance.is_async:
                self.assert_equal(self.recv_instance.n_msg_direct, 0)
            self.sync()
            T = self.recv_instance.start_timeout()
            while ((not T.is_out) and (self.recv_instance.n_msg
                                       != nrecv)):  # pragma: debug
                self.recv_instance.sleep()
            self.recv_instance.stop_timeout()
            self.assert_greater(self.recv_instance.n_msg, 0)
            self.recv_instance.purge()
            self.assert_equal(self.recv_instance.n_msg, 0)
            # Purge recv while closed
            self.recv_instance.close()
            self.recv_instance.purge()
            self.sync()


@pytest.mark.mpi(min_size=2)
class TestMPICommAsync(TestMPIComm):
    r"""Test class for asynchronous MPIComm."""

    use_async = True
