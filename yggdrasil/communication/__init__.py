import subprocess
import os
from contextlib import contextmanager
from yggdrasil.components import import_component


_temp_error_registry = {}


class TemporaryCommunicationError(Exception):
    r"""Raised when the comm is open, but send/recv is temporarily disabled.

    Args:
        msg (str): Error message.
        max_consecutive_allowed (int, optional): Maximum number of times this
            error should be raised as a TemporaryCommunicationError before
            being elevated to a FatalCommunicationError. Defaults to None and
            is never elevated.
        registry_key (str, optional): Key that should be used to register the
            error. Defaults to msg.

    Raises:
        FatalCommunicationError: If the error is raised more than the number
            of times specified via max_consecutive_allowed.

    """

    def __init__(self, msg, max_consecutive_allowed=None,
                 registry_key=None, **kwargs):
        super(TemporaryCommunicationError, self).__init__(msg, **kwargs)
        self.max_consecutive_allowed = max_consecutive_allowed
        if max_consecutive_allowed is not None:
            global _temp_error_registry
            assert(registry_key is not None)
            _temp_error_registry.setdefault(registry_key, 0)
            _temp_error_registry[registry_key] += 1
            if ((_temp_error_registry[registry_key]
                 > max_consecutive_allowed)):  # pragma: debug
                raise FatalCommunicationError(msg, **kwargs)

    @classmethod
    def reset(cls, registry_key):
        r"""Reset the registry for a TemporaryCommunicationError."""
        global _temp_error_registry
        _temp_error_registry.pop(registry_key, None)


class NoMessages(TemporaryCommunicationError):
    r"""Raised when the comm is open, but there are no messages waiting."""
    pass


class FatalCommunicationError(Exception):
    r"""Raised when the comm cannot recover."""
    pass


def import_comm(commtype=None):
    r"""Import a comm class from its component subtype.

    Args:
        commtype (str, optional): Communication class subtype. Defaults to
            the default comm type for the current OS.

    Returns:
        CommBase: Associated communication class.

    """
    if commtype in ['server', 'client', 'fork']:
        commtype = '%sComm' % commtype.title()
    return import_component('comm', commtype)


def determine_suffix(no_suffix=False, reverse_names=False,
                     direction='send', **kwargs):
    r"""Determine the suffix that should be used for the comm name.

    Args:
        no_suffix (bool, optional): If True, the suffix will be an empty
            string. Defaults to False.
        reverse_names (bool, optional): If True, the suffix will be
            opposite that indicated by the direction. Defaults to False.
        direction (str, optional): The direction that the comm will
            processing messages. Defaults to 'send'.
        **kwargs: Additional keyword arguments are ignored.

    Returns:
        str: Suffix that will be added to the comm name when producing
            the name of the environment variable where information about
            the comm will be stored.

    Raises:
        ValueError: If the direction is not 'recv' or 'send'.

    """
    if direction not in ['send', 'recv']:
        raise ValueError("Unrecognized message direction: %s" % direction)
    if no_suffix:
        suffix = ''
    else:
        if ((((direction == 'send') and (not reverse_names))
             or ((direction == 'recv') and reverse_names))):
            suffix = '_OUT'
        else:
            suffix = '_IN'
    return suffix


def new_comm(name, commtype=None, use_async=False, **kwargs):
    r"""Return a new communicator, creating necessary components for
    communication (queues, sockets, channels, etc.).

    Args:
        name (str): Communicator name.
        commtype (str, list, optional): Name of communicator type or a list
            of specifiers for multiple communicators that should be joined.
            Defaults to None.
        use_async (bool, optional): If True, send/recv operations will
            be performed asynchronously on new threads. Defaults to
            False.
        **kwargs: Additional keyword arguments are passed to communicator
            class method new_comm.

    Returns:
        Comm: Communicator of given class.

    """
    assert('comm' not in kwargs)
    if isinstance(commtype, list):
        if len(commtype) == 1:
            kwargs.update(commtype[0])
            kwargs.setdefault('name', name)
            kwargs.setdefault('use_async', use_async)
            return new_comm(**kwargs)
        else:
            kwargs['comm_list'] = commtype
            commtype = 'fork'
    if (commtype is None) and kwargs.get('filetype', None):
        commtype = kwargs.pop('filetype')
    if commtype in ['ErrorComm', 'error']:
        kwargs['commtype'] = commtype
        commtype = kwargs['base_commtype']
    comm_cls = import_comm(commtype)
    if kwargs.get('is_interface', False):
        use_async = False
    async_kws = {}
    if use_async:
        from yggdrasil.communication.AsyncComm import AsyncComm
        async_kws = {k: kwargs.pop(k) for k in AsyncComm._async_kws
                     if k in kwargs}
    if use_async:
        kwargs['is_async'] = True
    out = comm_cls.new_comm(name, **kwargs)
    if use_async and (out._commtype not in [None, 'client',
                                            'server', 'fork']):
        from yggdrasil.communication.AsyncComm import AsyncComm
        out = AsyncComm(out, **async_kws)
    return out


def get_comm(name, **kwargs):
    r"""Return communicator for existing comm components.

    Args:
        name (str): Communicator name.
        **kwargs: Additional keyword arguments are passed to new_comm.

    Returns:
        Comm: Communicator of given class.

    """
    kwargs['dont_create'] = True
    return new_comm(name, **kwargs)
    

def cleanup_comms(commtype=None):
    r"""Call cleanup_comms for the appropriate communicator class.

    Args:
        commtype (str, optional): Name of communicator class. Defaults to
            'default' if not provided.

    Returns:
        int: Number of comms closed.

    """
    return import_comm(commtype).cleanup_comms()


@contextmanager
def open_file_comm(fname, mode, filetype='binary', **kwargs):
    r"""Context manager to open a file comm in a way similar to how
    Python opens file descriptors.

    Args:
        fname (str): Path to file that should be opened.
        mode (str): Mode that file should be opened in. Supported values
            include 'r', 'w', and 'a'.
        filetype (str, optional): Type of file being opened. Defaults to
            'binary'.

    Returns:
        CommBase: File comm.

    """
    comm = None
    try:
        comm_cls = import_component('file', filetype)
        if mode == 'r':
            kwargs['direction'] = 'recv'
        elif mode in ['w', 'a']:
            kwargs['direction'] = 'send'
            if mode == 'a':
                kwargs['append'] = True
        else:
            raise ValueError("Unsupported mode: '%s'" % mode)
        comm = comm_cls('file', address=fname, **kwargs)
        yield comm
    finally:
        if comm is not None:
            comm.close()


def get_open_fds():  # pragma: debug
    '''
    return the number of open file descriptors for current process
    
    .. warning: will only work on UNIX-like os-es.
    '''
    procs = subprocess.check_output(["lsof", '-w', "-p", str(os.getpid())])
    nprocs = len(procs.split(b'\n'))
    # nprocs = len(
    #     list(filter(
    #         lambda s: s and s[ 0 ] == b'f' and s[1: ].isdigit(),
    #         procs.split( b'\n' ) ) )
    # )
    return nprocs


__all__ = ['new_comm', 'get_comm', 'cleanup_comms']
