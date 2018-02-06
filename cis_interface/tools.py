"""This modules offers various tools."""
from __future__ import print_function
import threading
import logging
import os
import sys
import inspect
import time
import signal
import yaml
import pystache
import warnings
from cis_interface.backwards import sio
import subprocess
from cis_interface import platform
from cis_interface import backwards
from cis_interface.config import cis_cfg, cfg_logging


def locate_path(fname, basedir=os.path.abspath(os.sep)):
    r"""Find the full path to a file using where on Windows."""
    try:
        if platform._is_win:
            out = subprocess.check_output(["dir", fname, "/s/b"], shell=True,
                                          cwd=basedir)
            # out = subprocess.check_output(["where", fname])
        else:
            # find . -name "filetofind" 2>&1 | grep -v 'permission denied'
            out = subprocess.check_output(["find", basedir, "-name", fname])  # ,
            # "2>&1", "|", "grep", "-v", "'permission denied'"])
            # out = subprocess.check_output(["locate", "-b", "--regex",
            #                                "^%s" % fname])
    except subprocess.CalledProcessError:
        return False
    if out.isspace():
        return False
    out = out.decode('utf-8').splitlines()
    # out = backwards.bytes2unicode(out.splitlines()[0])
    return out


def is_ipc_installed():
    r"""Determine if the IPC libraries are installed.

    Returns:
        bool: True if the IPC libraries are installed, False otherwise.

    """
    return (platform._is_linux or platform._is_osx)


def is_zmq_installed():
    r"""Determine if the libczmq & libzmq libraries are installed.

    Returns:
        bool: True if both libraries are installed, False otherwise.

    """
    # Check existence of config paths for windows
    if platform._is_win:
        opts = ['libzmq_include', 'libzmq_static',  # 'libzmq_dynamic',
                'czmq_include', 'czmq_static']  # , 'czmq_dynamic']
        for o in opts:
            if not cis_cfg.get('windows', o, None):
                warnings.warn("Config option %s not set." % o)
                return False
        return True
    else:
        process = subprocess.Popen(['gcc', '-lzmq', '-lczmq'],
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)
        outs, errs = process.communicate()
        # Python 3
        # try:
        #     outs, errs = process.communicate(timeout=15)
        # except subprocess.TimeoutExpired:
        #     process.kill()
        #     outs, errs = process.communicate()
        return (backwards.unicode2bytes('zmq') not in errs)


_ipc_installed = is_ipc_installed()
_zmq_installed = is_zmq_installed()
if not (_ipc_installed or _zmq_installed):  # pragma: debug
    raise Exception('Neither ZMQ or IPC installed.')
CIS_MSG_EOF = backwards.unicode2bytes("EOF!!!")
CIS_MSG_BUF = 1024 * 2


def get_default_comm():
    r"""Get the default comm that should be used for message passing."""
    if 'CIS_DEFAULT_COMM' in os.environ:
        _default_comm = os.environ['CIS_DEFAULT_COMM']
        if _default_comm not in ['ZMQComm', 'IPCComm', 'RMQComm']:  # pragma: debug
            raise Exception('Unrecognized default comm %s set by CIS_DEFAULT_COMM' % (
                _default_comm))
    elif _zmq_installed:
        _default_comm = 'ZMQComm'
    elif _ipc_installed:
        _default_comm = 'IPCComm'
    else:  # pragma: debug
        raise Exception('Neither ZMQ or IPC installed.')
    return _default_comm


def get_CIS_MSG_MAX():
    r"""Get the maximum message size for the default comm."""
    _default_comm = get_default_comm()
    if _default_comm == 'IPCComm':
        # OS X limit is 2kb
        out = 1024 * 2
    else:
        out = 2**20
    return out


CIS_MSG_MAX = get_CIS_MSG_MAX()


# https://stackoverflow.com/questions/35772001/
# how-to-handle-the-signal-in-python-on-windows-machine
def kill(pid, signum):
    r"""Kill process by mapping signal number.

    Args:
        pid (int): Process ID.
        signum (int): Signal that should be sent.

    """
    if platform._is_win:
        sigmap = {signal.SIGINT: signal.CTRL_C_EVENT,
                  signal.SIGBREAK: signal.CTRL_BREAK_EVENT}
        if False:
            import win32api
            ret = win32api.GenerateConsoleCtrlEvent(sigmap[signum], pid)
            print("Generated signal", sigmap[signum])
            return ret
        if False:
            import ctypes
            ret = ctypes.windll.kernel32.GenerateConsoleCtrlEvent(sigmap[signum], pid)
            print("Generated signal", sigmap[signum])
            return ret
        if signum in sigmap and pid == os.getpid() and False:
            # we don't know if the current process is a
            # process group leader, so just broadcast
            # to all processes attached to this console.
            pid = 0
        thread = threading.current_thread()
        handler = signal.getsignal(signum)
        # work around the synchronization problem when calling
        # kill from the main thread.
        if (((signum in sigmap) and (thread.name == 'MainThread') and
             callable(handler) and ((pid == os.getpid()) or (pid == 0)))):
            event = threading.Event()

            def handler_set_event(signum, frame):
                event.set()
                return handler(signum, frame)

            signal.signal(signum, handler_set_event)
            try:
                os.kill(pid, sigmap[signum])
                # busy wait because we can't block in the main
                # thread, else the signal handler can't execute.
                while not event.is_set():
                    pass
            finally:
                signal.signal(signum, handler)
        else:
            os.kill(pid, sigmap.get(signum, signum))
    else:
        os.kill(pid, signum)


def sleep(interval):
    r"""Sleep for a specified number of seconds.

    Args:
        interval (float): Time in seconds that process should sleep.

    """
    if platform._is_win and backwards.PY2:
        while True:
            try:
                t = time.time()
                time.sleep(interval)
            except IOError as e:
                import errno
                if e.errno != errno.EINTR:
                    raise
            # except InterruptedError:
            #     import errno
            #     print(e.errno)
            #     print(e)
            interval -= time.time() - t
            if interval <= 0:
                break
    else:
        time.sleep(interval)


def parse_yaml(fname):
    r"""Parse a yaml file defining a run.

    Args:
        fname (str): Path to the yaml file.

    Returns:
        dict: Contents of yaml file.

    """
    # Open file and parse yaml
    with open(fname, 'r') as f:
        # Mustache replace vars
        yamlparsed = f.read()
        yamlparsed = pystache.render(
            sio.StringIO(yamlparsed).getvalue(), dict(os.environ))
        yamlparsed = yaml.safe_load(yamlparsed)
    return yamlparsed

    
def eval_kwarg(x):
    r"""If x is a string, eval it. Otherwise just return it.

    Args:
        x (str, obj): String to be evaluated as an object or an object.

    Returns:
        obj: Result of evaluated string or the input object.

    """
    if isinstance(x, str):
        try:
            return eval(x)
        except NameError:
            return x
    return x


class CisPopen(subprocess.Popen):
    r"""Uses Popen to open a process without a buffer. If not already set,
    the keyword arguments 'bufsize', 'stdout', and 'stderr' are set to
    0, subprocess.PIPE, and subprocess.STDOUT respectively. This sets the
    output stream to unbuffered and directs both stdout and stderr to the
    stdout pipe. In addition this class overrides Popen.kill() to allow
    processes to be killed with CTRL_BREAK_EVENT on windows.

    Args:
        args (list, str): Shell command or list of arguments that should be
            run.
        forward_signals (bool, optional): If True, flags will be set such
            that signals received by the spawning process will be forwarded
            to the child process. If False, the signals will not be forwarded.
            Defaults to True.
        **kwargs: Additional keywords arguments are passed to Popen.

    """
    def __init__(self, cmd_args, forward_signals=True, **kwargs):
        # stdbuf only for linux
        if platform._is_linux:
            stdbuf_args = ['stdbuf', '-o0', '-e0']
            if isinstance(cmd_args, str):
                cmd_args = ' '.join(stdbuf_args + [cmd_args])
            else:
                cmd_args = stdbuf_args + cmd_args
        kwargs.setdefault('bufsize', 0)
        kwargs.setdefault('stdout', subprocess.PIPE)
        kwargs.setdefault('stderr', subprocess.STDOUT)
        if not forward_signals:
            if platform._is_win:
                kwargs.setdefault('preexec_fn', None)
                kwargs.setdefault('creationflags', subprocess.CREATE_NEW_PROCESS_GROUP)
            else:
                kwargs.setdefault('preexec_fn', os.setpgrp)
        # if platform._is_win:
        #     kwargs.setdefault('universal_newlines', True)
        super(CisPopen, self).__init__(cmd_args, **kwargs)

    def kill(self, *args, **kwargs):
        r"""On windows using CTRL_BREAK_EVENT to kill the process."""
        if platform._is_win:
            self.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            super(CisPopen, self).kill(*args, **kwargs)


def popen_nobuffer(*args, **kwargs):
    r"""Uses Popen to open a process without a buffer. If not already set,
    the keyword arguments 'bufsize', 'stdout', and 'stderr' are set to
    0, subprocess.PIPE, and subprocess.STDOUT respectively. This sets the
    output stream to unbuffered and directs both stdout and stderr to the
    stdout pipe.

    Args:
        args (list, str): Shell command or list of arguments that should be
            run.
        forward_signals (bool, optional): If True, flags will be set such
            that signals received by the spawning process will be forwarded
            to the child process. If False, the signals will not be forwarded.
            Defaults to True.
        **kwargs: Additional keywords arguments are passed to Popen.

    Returns:
        CisPopen: Process that was started.

    """
    return CisPopen(*args, **kwargs)


def print_encoded(msg, *args, **kwargs):
    r"""Print bytes to stdout, encoding if possible.

    Args:
        msg (str, bytes): Message to print.
        *args: Additional arguments are passed to print.
        **kwargs: Additional keyword arguments are passed to print.


    """
    try:
        print(backwards.bytes2unicode(msg), *args, **kwargs)
    except UnicodeEncodeError:  # pragma: debug
        logging.debug("sys.stdout.encoding = %s, cannot print unicode",
                      sys.stdout.encoding)
        kwargs.pop('end', None)
        try:
            print(msg, *args, **kwargs)
        except UnicodeEncodeError:  # pragma: debug
            print(backwards.unicode2bytes(msg), *args, **kwargs)


class TimeOut(object):
    r"""Class for checking if a period of time has been elapsed.

    Args:
        max_time (float, bbol): Maximum period of time that should elapse before
            'is_out' returns True. If False, 'is_out' will never return True.
            Providing 0 indicates that 'is_out' should immediately return True.

    Attributes:
        max_time (float): Maximum period of time that should elapsed before
            'is_out' returns True.
        start_time (float): Result of time.time() at start.

    """

    def __init__(self, max_time):
        self.max_time = max_time
        self.start_time = backwards.clock_time()

    @property
    def elapsed(self):
        r"""float: Total time that has elapsed since the start."""
        return backwards.clock_time() - self.start_time
    
    @property
    def is_out(self):
        r"""bool: True if there is not any time remaining. False otherwise."""
        if self.max_time is False:
            return False
        return (self.elapsed > self.max_time)


class CisClass(object):
    r"""Base class for CiS classes.

    Args:
        name (str): Class name.
        workingDir (str, optional): Working directory. If not provided, the
            current working directory is used.
        timeout (float, optional): Maximum time (in seconds) that should be
            spent waiting on a process. Defaults to 60.
        sleeptime (float, optional): Time that class should sleep for when
            sleep is called. Defaults to 0.01.
        **kwargs: Additional keyword arguments are assigned to the extra_kwargs
            dictionary.

    Attributes:
        name (str): Class name.
        sleeptime (float): Time that class should sleep for when sleep called.
        longsleep (float): Time that the class will sleep for when waiting for
            longer tasks to complete (10x longer than sleeptime).
        timeout (float): Maximum time that should be spent waiting on a process.
        workingDir (str): Working directory.
        errors (list): List of errors.
        extra_kwargs (dict): Keyword arguments that were not parsed.
        sched_out (obj): Output from the last scheduled task with output.
        logger (logging.Logger): Logger object for this object.
        suppress_special_debug (bool): If True, special_debug log messages
            are suppressed.

    """
    def __init__(self, name, workingDir=None, timeout=60.0, sleeptime=0.01,
                 **kwargs):
        self.name = name
        self.sleeptime = sleeptime
        self.longsleep = self.sleeptime * 10
        self.timeout = timeout
        self._timeouts = {}
        # Set defaults
        if workingDir is None:
            workingDir = os.getcwd()
        # Assign things
        self.workingDir = workingDir
        self.errors = []
        self.extra_kwargs = kwargs
        self.sched_out = None
        self.suppress_special_debug = False
        self.logger = logging.getLogger(self.__module__)
        self._old_loglevel = None
        self._old_encoding = None
        self.debug_flag = False

    def debug_log(self):  # pragma: debug
        r"""Turn on debugging."""
        self._old_loglevel = cis_cfg.get('debug', 'psi')
        cis_cfg.set('debug', 'psi', 'DEBUG')
        cfg_logging()

    def reset_log(self):  # pragma: debug
        r"""Resetting logging to prior value."""
        if self._old_loglevel is not None:
            cis_cfg.set('debug', 'psi', self._old_loglevel)
            cfg_logging()
            self._old_loglevel = None

    def set_utf8_encoding(self):
        r"""Set the encoding to utf-8 if it is not already."""
        old_lang = os.environ.get('LANG', '')
        if 'UTF-8' not in old_lang:  # pragma: debug
            self._old_encoding = old_lang
            os.environ['LANG'] = 'en_US.UTF-8'
            
    def reset_encoding(self):
        r"""Reset the encoding to the original value before the test."""
        if self._old_encoding is not None:  # pragma: debug
            os.environ['LANG'] = self._old_encoding
            self._old_encoding = None

    def print_encoded(self, msg, *args, **kwargs):
        r"""Print bytes to stdout, encoding if possible.

        Args:
            msg (str, bytes): Message to print.
            *args: Additional arguments are passed to print.
            **kwargs: Additional keyword arguments are passed to print.


        """
        return print_encoded(msg, *args, **kwargs)

    def printStatus(self):
        r"""Print the class status."""
        self.logger.error('%s(%s): state:', self.__module__, self.name)

    def _task_with_output(self, func, *args, **kwargs):
        self.sched_out = func(*args, **kwargs)

    def sched_task(self, t, func, args=[], kwargs={}, store_output=False):
        r"""Schedule a task that will be executed after a certain time has
        elapsed.

        Args:
            t (float): Number of seconds that should be waited before task
                is executed.
            func (object): Function that should be executed.
            args (list, optional): Arguments for the provided function.
                Defaults to [].
            kwargs (dict, optional): Keyword arguments for the provided
                function. Defaults to {}.
            store_output (bool, optional): If True, the output from the
                scheduled task is stored in self.sched_out. Otherwise, it is not
                stored. Defaults to False.

        """
        self.sched_out = None
        if store_output:
            tobj = threading.Timer(t, self._task_with_output,
                                   args=[func] + args, kwargs=kwargs)
        else:
            tobj = threading.Timer(t, func, args=args, kwargs=kwargs)
        tobj.start()

    @property
    def logger_prefix(self):
        r"""Prefix to add to logger messages."""
        stack = inspect.stack()
        the_class = os.path.splitext(os.path.basename(
            stack[2][0].f_globals["__file__"]))[0]
        the_line = stack[2][2]
        the_func = stack[2][3]
        return '%s(%s).%s[%d]: ' % (the_class, self.name, the_func, the_line)

    def as_str(self, obj):
        r"""Return str version of object if it is not already a string.

        Args:
            obj (object): Object that should be turned into a string.

        Returns:
            str: String version of provided object.

        """
        if not isinstance(obj, str):
            obj_str = str(obj)
        else:
            obj_str = obj
        return obj_str
            
    def sleep(self, t=None):
        r"""Have the class sleep for some period of time.

        Args:
            t (float, optional): Time that class should sleep for. If not
                provided, the attribute 'sleeptime' is used.

        """
        if t is None:
            t = self.sleeptime
        sleep(t)

    @property
    def timeout_key(self):
        r"""str: Key identifying calling object and method."""
        # stack = inspect.stack()
        # fcn = stack[2][3]
        # cls = os.path.splitext(os.path.basename(stack[2][1]))[0]
        # key = '%s(%s).%s' % (cls, self.name, fcn)
        # return key
        return self.get_timeout_key()

    def get_timeout_key(self, key_level=0):
        r"""Return a key for a given level in the stack, relative to the
        function calling get_timeout_key.

        Args:
            key_level (int, optional): Positive integer indicating the level of
                the calling class and function/method that should be used to
                key the timeout. 0 is the class and function/method that is 2
                steps higher in the stack. Higher values use classes and
                function/methods further up in the stack. Defaults to 0.

        Returns:
            str: Key identifying calling object and method.

        """
        stack = inspect.stack()
        fcn = stack[key_level + 2][3]
        cls = os.path.splitext(os.path.basename(stack[key_level + 2][1]))[0]
        key = '%s(%s).%s' % (cls, self.name, fcn)
        return key

    def start_timeout(self, t=None, key=None, key_level=0):
        r"""Start a timeout for the calling function/method.

        Args:
            t (float, optional): Maximum time that the calling function should
                wait before timeing out. If not provided, the attribute
                'timeout' is used.
            key (str, optional): Key that should be associated with the timeout
                that is created. Defaults to None and is set by the calling
                class and function/method (See `get_timeout_key`).
            key_level (int, optional): Positive integer indicating the level of
                the calling class and function/method that should be used to
                key the timeout. 0 is the class and function/method that called
                start_timeout. Higher values use classes and function/methods
                further up in the stack. Defaults to 0.

        Raises:
            KeyError: If the key already exists.

        """
        if t is None:
            t = self.timeout
        if key is None:
            key = self.get_timeout_key(key_level=key_level)
        if key in self._timeouts:
            raise KeyError("Timeout already registered for %s" % key)
        self._timeouts[key] = TimeOut(t)
        return self._timeouts[key]

    def check_timeout(self, key=None, key_level=0):
        r"""Check timeout for the calling function/method.

        Args:
            key (str, optional): Key for timeout that should be checked.
                Defaults to None and is set by the calling class and
                function/method (See `timeout_key`).
            key_level (int, optional): Positive integer indicating the level of
                the calling class and function/method that should be used to
                key the timeout. 0 is the class and function/method that called
                start_timeout. Higher values use classes and function/methods
                further up in the stack. Defaults to 0.

        Raises:
            KeyError: If there is not a timeout registered for the specified
                key.

        """
        if key is None:
            key = self.get_timeout_key(key_level=key_level)
        if key not in self._timeouts:
            raise KeyError("No timeout registered for %s" % key)
        t = self._timeouts[key]
        return t.is_out
        
    def stop_timeout(self, key=None, key_level=0):
        r"""Stop a timeout for the calling function method.

        Args:
            key (str, optional): Key for timeout that should be stopped.
                Defaults to None and is set by the calling class and
                function/method (See `timeout_key`).
            key_level (int, optional): Positive integer indicating the level of
                the calling class and function/method that should be used to
                key the timeout. 0 is the class and function/method that called
                start_timeout. Higher values use classes and function/methods
                further up in the stack. Defaults to 0.

        Raises:
            KeyError: If there is not a timeout registered for the specified
                key.

        """
        if key is None:
            key = self.get_timeout_key(key_level=key_level)
        if key not in self._timeouts:
            raise KeyError("No timeout registered for %s" % key)
        t = self._timeouts[key]
        if t.is_out and t.max_time > 0:
            self.error("Timeout for %s at %5.2f s" % (key, t.elapsed))
            print("Stopped %s at %f/%f" % (key, t.elapsed, t.max_time))
        del self._timeouts[key]

    def display(self, fmt_str='', *args):
        r"""Log a message at level 1000 that is prepended with the class
        and name. These messages will always be printed.

        Args:
            fmt_str (str, optional): Format string.
            \*args: Additional arguments are formated using the format string.

        """
        print(self.logger_prefix + self.as_str(fmt_str) % args)

    def info(self, fmt_str='', *args):
        r"""Log an info message that is prepended with the class and name.

        Args:
            fmt_str (str, optional): Format string.
            \*args: Additional arguments are formated using the format string.

        """
        self.logger.info(self.logger_prefix + self.as_str(fmt_str), *args)

    def debug(self, fmt_str='', *args):
        r"""Log a debug message that is prepended with the class and name.

        Args:
            fmt_str (str, optional): Format string.
            \*args: Additional arguments are formated using the format string.

        """
        self.logger.debug(self.logger_prefix + self.as_str(fmt_str), *args)

    def special_debug(self, fmt_str='', *args):
        r"""Log a debug message that is prepended with the class and name, but
        only if self.suppress_special_debug is not True.

        Args:
            fmt_str (str, optional): Format string.
            \*args: Additional arguments are formated using the format string.

        """
        if not self.suppress_special_debug:
            self.logger.debug(self.logger_prefix + self.as_str(fmt_str), *args)

    def verbose_debug(self, fmt_str='', *args):
        r"""Log a verbose debug message that is prepended with the class and name.

        Args:
            fmt_str (str, optional): Format string.
            \*args: Additional arguments are formated using the format string.

        """
        self.logger.log(9, self.logger_prefix + self.as_str(fmt_str), *args)
        
    def critical(self, fmt_str='', *args):
        r"""Log a critical message that is prepended with the class and name.

        Args:
            fmt_str (str, optional): Format string.
            \*args: Additional arguments are formated using the format string.

        """
        self.logger.critical(self.logger_prefix + self.as_str(fmt_str), *args)

    def warn(self, fmt_str='', *args):
        r"""Log a warning message that is prepended with the class and name.

        Args:
            fmt_str (str, optional): Format string.
            \*args: Additional arguments are formated using the format string.

        """
        self.logger.warn(self.logger_prefix + self.as_str(fmt_str), *args)

    def error(self, fmt_str='', *args):
        r"""Log an error message that is prepended with the class and name.

        Args:
            fmt_str (str, optional): Format string.
            \*args: Additional arguments are formated using the format string.

        """
        fmt_str = self.as_str(fmt_str)
        self.logger.error(self.logger_prefix + fmt_str, *args)
        self.errors.append((self.logger_prefix + fmt_str) % args)

    def exception(self, fmt_str='', *args):
        r"""Log an exception message that is prepended with the class name.

        Args:
            fmt_str (str, optional): Format string.
            \*args: Additional arguments are formated using the format string.

        """
        fmt_str = self.as_str(fmt_str)
        exc_info = sys.exc_info()
        if exc_info is not None and exc_info != (None, None, None):
            self.logger.exception(self.logger_prefix + fmt_str, *args)
        else:
            self.logger.error(self.logger_prefix + fmt_str, *args)
        self.errors.append((self.logger_prefix + fmt_str) % args)

    def raise_error(self, e):
        r"""Raise an exception, logging it first.

        Args:
            e (Exception): Exception to raise.

        Raises:
            The provided exception.

        """
        self.errors.append(repr(e))
        raise e


class CisThread(threading.Thread, CisClass):
    r"""Thread for CiS that tracks when the thread is started and joined.

    Attributes:
        lock (threading.RLock): Lock for accessing the sockets from multiple
            threads.
        start_event (threading.Event): Event indicating that the thread was
            started.
        terminate_event (threading.Event): Event indicating that the thread
            should be terminated. The target must exit when this is set.

    """
    def __init__(self, name=None, **kwargs):
        thread_kwargs = dict(name=name)
        for k in ['group', 'target', 'args', 'kwargs']:
            if k in kwargs:
                thread_kwargs[k] = kwargs.pop(k)
        super(CisThread, self).__init__(**thread_kwargs)
        CisClass.__init__(self, self.name, **kwargs)
        self.debug()
        self.lock = threading.RLock()
        self.start_event = threading.Event()
        self.terminate_event = threading.Event()
        self.start_flag = False
        self.terminate_flag = False
        self.setDaemon(True)
        self.daemon = True

    def set_started_flag(self):
        r"""Set the started flag for the thread to True."""
        # self.start_event.set()
        self.start_flag = True

    def set_terminated_flag(self):
        r"""Set the terminated flag for the thread to True."""
        # self.terminate_event.set()
        self.terminate_flag = True

    def unset_started_flag(self):
        r"""Set the started flag for the thread to False."""
        # self.start_event.clear()
        self.start_flag = False

    def unset_terminated_flag(self):
        r"""Set the terminated flag for the thread to False."""
        # self.terminate_event.clear()
        self.terminated_flag = False

    @property
    def was_started(self):
        r"""bool: True if the thread was started. False otherwise."""
        # return self.start_event.is_set()
        return self.start_flag

    @property
    def was_terminated(self):
        r"""bool: True if the thread was terminated. False otherwise."""
        # return self.terminate_event.is_set()
        return self.terminate_flag

    def start(self, *args, **kwargs):
        r"""Start thread and print info."""
        self.debug()
        if not self.was_terminated:
            self.set_started_flag()
            self.before_start()
        super(CisThread, self).start(*args, **kwargs)

    def before_start(self):
        r"""Actions to perform on the main thread before starting the thread."""
        self.debug()

    def wait(self, timeout=None):
        r"""Wait until thread finish to return using sleeps rather than
        blocking.

        Args:
            timeout (float, optional): Maximum time that should be waited for
                the driver to finish. Defaults to None and is infinite.

        """
        T = self.start_timeout(timeout)
        while self.is_alive() and not T.is_out:
            self.debug('Waiting for thread to finish...')
            self.sleep()
        self.stop_timeout()

    def terminate(self, no_wait=False):
        r"""Set the terminate event and wait for the thread to stop.

        Args:
            no_wait (bool, optional): If True, terminate will not block until
                the thread stops. Defaults to False and blocks.

        Raises:
            AssertionError: If no_wait is False and the thread has not stopped
                after the timeout.

        """
        self.debug()
        with self.lock:
            self.set_terminated_flag()
        if not no_wait:
            # if self.is_alive():
            #     self.join(self.timeout)
            self.wait(timeout=self.timeout)
            assert(not self.is_alive())


class CisThreadLoop(CisThread):
    r"""Thread that will run a loop until the terminate event is called."""
    def __init__(self, *args, **kwargs):
        super(CisThreadLoop, self).__init__(*args, **kwargs)

    def before_loop(self):
        r"""Actions performed before the loop."""
        self.debug()

    def run_loop(self, *args, **kwargs):
        r"""Actions performed on each loop iteration."""
        if self._target:
            self._target(*self._args, **self._kwargs)
        else:
            self.set_terminated_flag()

    def after_loop(self):
        r"""Actions performed after the loop."""
        self.debug()

    def run(self, *args, **kwargs):
        r"""Continue running until terminate event set."""
        self.debug("Starting loop")
        self.before_loop()
        try:
            while not self.was_terminated:
                self.run_loop()
        except:
            self.set_terminated_flag()
            raise
        finally:
            for k in ['_target', '_args', '_kwargs']:
                if hasattr(self, k):
                    delattr(self, k)
            # del self._target, self._args, self._kwargs
        self.after_loop()
