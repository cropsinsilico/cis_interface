import os
import uuid
from yggdrasil.tests import (
    generate_component_tests, generate_component_subtests,
    assert_equal, assert_raises)
from yggdrasil.communication import open_file_comm
from yggdrasil.communication.tests.test_FileComm import TestFileComm


generate_component_tests('file', TestFileComm, globals(), __file__,
                         class_attr='comm')
generate_component_subtests('comm', 'Async', globals(),
                            'yggdrasil.communication.tests',
                            new_attr={'use_async': True},
                            skip_subtypes=['default', 'mpi'])


def test_open_file_comm():
    r"""Test file comm context manager."""
    fname = os.path.join(os.path.dirname(__file__),
                         '%s.txt' % str(uuid.uuid4()))
    try:
        msg = b'Test message'
        with open_file_comm(fname, 'w') as comm:
            flag = comm.send(msg)
            assert(flag)
        with open_file_comm(fname, 'a') as comm:
            flag = comm.send(msg)
            assert(flag)
        with open_file_comm(fname, 'r') as comm:
            flag, res = comm.recv()
            assert(flag)
        assert_equal(res, 2 * msg)
    finally:
        if os.path.isfile(fname):
            os.remove(fname)
    with assert_raises(ValueError):
        with open_file_comm(fname, 'invalid') as comm:  # pragma: debug
            pass


__all__ = []
