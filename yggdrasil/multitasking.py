import os
import six
import weakref
import threading
import queue
import multiprocessing
from yggdrasil.tools import YggClass
mp_ctx = multiprocessing.get_context()
mp_ctx_spawn = multiprocessing.get_context("spawn")
_main_thread = threading.main_thread()


class SafeThread(threading.Thread):
    r"""Thread that sets Event on error."""

    def __init__(self, *args, **kwargs):
        self._errored = threading.Event()
        super(SafeThread, self).__init__(*args, **kwargs)

    def run(self, *args, **kwargs):
        try:
            super(SafeThread, self).run(*args, **kwargs)
        except BaseException:
            self._errored.set()
            raise

    @property
    def exitcode(self):
        r"""int: Exit code. 1 if error, 0 otherwise."""
        if (not self._started.is_set()) or self.is_alive():
            return None
        return int(self._errored.is_set())

    @property
    def pid(self):
        r"""Process ID."""
        return os.getpid()


class AliasCleanupError(RuntimeError):
    pass


def add_aliased_attribute(cls, name, with_lock=False):
    r"""Factory to alias an attribute so that it refers to the wrapped
    object.

    Args:
        name (str): Name of attribute to alias.
        with_lock (bool, optional): If True, the class's lock will be
            acquired before getting the attribute. Defaults to False.

    """
    def alias_wrapper(self):
        self.check_for_base(name)
        lock_acquired = False
        if ((with_lock and hasattr(self, 'lock')
             and (name not in self._unlocked_attr))):
            self.lock.acquire()
            lock_acquired = True
        try:
            out = getattr(self._base, name)
        finally:
            if lock_acquired:
                self.lock.release()
        return out
    alias_wrapper.__name__ = name
    setattr(cls, name, property(alias_wrapper))


def add_aliased_method(cls, name, with_lock=False):
    r"""Factory to alias a method so that it refers to the wrapped
    object.

    Args:
        name (str): Name of method to alias.
        with_lock (bool, optional): If True, the class's lock will be
            acquired before executing the method. Defaults to False.

    """
    def alias_wrapper(self, *args, **kwargs):
        self.check_for_base(name)
        lock_acquired = False
        if ((with_lock and hasattr(self, 'lock')
             and (name not in self._unlocked_attr))):
            self.lock.acquire()
            lock_acquired = True
        try:
            out = getattr(self._base, name)(*args, **kwargs)
        finally:
            if lock_acquired:
                self.lock.release()
        return out
    alias_wrapper.__name__ = name
    setattr(cls, name, alias_wrapper)


class AliasMeta(type):
    r"""Meta class for adding aliased methods to the class."""

    def __new__(meta, name, bases, class_dict):
        cls = type.__new__(meta, name, bases, class_dict)
        for k in cls._base_meth:
            assert(not hasattr(cls, k))
            add_aliased_method(cls, k, with_lock=cls._base_locked)
        for k in cls._base_attr:
            assert(not hasattr(cls, k))
            add_aliased_attribute(cls, k, with_lock=cls._base_locked)
        cls._base_meth = []
        cls._base_attr = []
        return cls


@six.add_metaclass(AliasMeta)
class AliasObject(object):
    r"""Alias object that calls to attribute.

    Args:
        dont_initialize_base (bool, optional): If True the base object
            will not be initialized. Defaults to False.

    """

    _base_class = None
    _base_attr = []
    _base_meth = []
    _base_locked = False
    _unlocked_attr = []

    def __init__(self, *args, dont_initialize_base=False, **kwargs):
        self._base = None
        if (not dont_initialize_base) and (self._base_class is not None):
            self._base = self._base_class(*args, **kwargs)

    @classmethod
    def from_base(cls, base, *args, **kwargs):
        r"""Create an instance by creating a based from the provided
        base class."""
        if base is not None:
            kwargs['dont_initialize_base'] = True
            out = cls(*args, **kwargs)
            out._base = base
        else:
            out = cls(*args, **kwargs)
        return out

    def __getstate__(self):
        out = self.__dict__.copy()
        out.pop('_base_class', None)
        return out

    def __setstate__(self, state):
        self.__dict__.update(state)

    def check_for_base(self, attr):
        r"""Raise an error if the aliased object has been cleaned up."""
        if self._base is None:
            raise AliasCleanupError(
                ("Aliased object has been cleaned up so "
                 "'%s' is no longer available.") % attr)

    @property
    def dummy_copy(self):
        r"""Dummy copy of base."""
        return None

    def cleanup(self):
        r"""Cleanup the class."""
        if self._base is not None:
            self._base = self.dummy_copy

        
class MultiObject(AliasObject):
    r"""Concurrent/parallel processing object using either threads
    or processes."""

    def __init__(self, *args, task_method="threading", **kwargs):
        self.task_method = task_method
        if task_method in ["thread", "threading", "concurrent"]:
            self.parallel = False
        elif task_method in ["process", "multiprocessing", "parallel"]:
            self.parallel = True
        else:  # pragma: debug
            raise ValueError(("Unsupported method for concurrency/"
                              "parallelism: '%s'") % task_method)
        super(MultiObject, self).__init__(*args, **kwargs)

    def disconnect(self):
        r"""Disconnect by ending any synchronization between threads
        or processes."""
        self.cleanup()


class Context(MultiObject):
    r"""Context for managing threads/processes."""

    def __init__(self, task_method='thread', dont_initialize_base=False):
        super(Context, self).__init__(dont_initialize_base=True,
                                      task_method=task_method)
        if not dont_initialize_base:
            if self.parallel:
                self._base = mp_ctx_spawn
            else:
                self._base = threading

    def __getstate__(self):
        state = super(Context, self).__getstate__()
        if self.parallel:
            state['_base'] = state['_base']._name
        else:
            state['_base'] = None
        return state

    def __setstate__(self, state):
        if state['_base'] is None:
            state['_base'] = threading
        else:
            # Use the existing context?
            # state['_base'] = mp_ctx_spawn
            state['_base'] = multiprocessing.get_context(state['_base'])
        super(Context, self).__setstate__(state)

    def RLock(self, *args, **kwargs):
        r"""Get a recursive lock in this context."""
        kwargs['task_context'] = self
        return RLock(*args, **kwargs)

    def Event(self, *args, **kwargs):
        r"""Get an event in this context."""
        kwargs['task_context'] = self
        return Event(*args, **kwargs)

    def Task(self, *args, **kwargs):
        r"""Get a task in this context."""
        kwargs['task_context'] = self
        return Task(*args, **kwargs)

    def Queue(self, *args, **kwargs):
        r"""Get a queue in this context."""
        kwargs['task_context'] = self
        return Queue(*args, **kwargs)

    def Dict(self, *args, **kwargs):
        r"""Get a shared dictionary in this context."""
        kwargs['task_context'] = self
        return Dict(*args, **kwargs)

    def current_task(self):
        r"""Current task (process/thread)."""
        if self.parallel:
            return self._base.current_process()
        else:
            return self._base.current_thread()

    def main_task(self):
        r"""Main task (process/thread)."""
        if self.parallel:
            out = None
            if hasattr(self._base, 'parent_process'):  # pragma: no cover
                out = self._base.parent_process()
            if out is None:
                out = self.current_task()
            return out
        else:
            return _main_thread


class DummyContextObject(object):

    @property
    def context(self):
        return None

    def cleanup(self):
        pass


class ContextObject(MultiObject):
    r"""Base class for object intialized in a context."""

    def __init__(self, *args, task_method='threading',
                 task_context=None, **kwargs):
        self._cleanup_context = None
        if task_context is None:
            task_context = Context(task_method=task_method)
            self._cleanup_context = task_context
        task_method = task_context.task_method
        self._context = weakref.ref(task_context)
        self._base_class = self.get_base_class(task_context)
        super(ContextObject, self).__init__(
            *args, task_method=task_method, **kwargs)

    def __getstate__(self):
        state = super(ContextObject, self).__getstate__()
        state['_context'] = None
        return state

    def __setstate__(self, state):
        if state['_cleanup_context'] is None:
            state['_cleanup_context'] = Context(task_method=state['task_method'])
        state['_context'] = weakref.ref(state['_cleanup_context'])
        super(ContextObject, self).__setstate__(state)
        
    @classmethod
    def get_base_class(cls, context):
        r"""Get instance of base class that will be represented."""
        name = cls.__name__
        context.check_for_base(name)
        return getattr(context._base, name)

    def cleanup(self):
        r"""Cleanup the class."""
        super(ContextObject, self).cleanup()
        if self._cleanup_context is not None:
            self._cleanup_context.cleanup()
            self._cleanup_context = None

    @property
    def context(self):
        r"""Context: Context used to create this object."""
        return self._context()


class RLock(ContextObject):
    r"""Recursive lock. Acquiring the lock after cleanup is called
    through use as a context will not raise an error, but will not
    do anything."""

    _base_meth = ['acquire', 'release']

    def __getstate__(self):
        state = super(RLock, self).__getstate__()
        if not self.parallel:
            state['_base'] = None
        return state

    def __setstate__(self, state):
        if state['_base'] is None:
            state['_base'] = threading.RLock()
        super(RLock, self).__setstate__(state)
        
    def __enter__(self, *args, **kwargs):
        if self._base is None:
            return self
        else:
            return self._base.__enter__(*args, **kwargs)

    def __exit__(self, *args, **kwargs):
        if self._base is None:
            return
        else:
            return self._base.__exit__(*args, **kwargs)


class DummyEvent(DummyContextObject):  # pragma: no cover

    def __init__(self, value):
        self._value = value

    def is_set(self):
        return self._value

    def set(self):
        self._value = True

    def clear(self):
        self._value = False

    def wait(self, *args, **kwargs):
        if self._value:
            return
        raise RuntimeError("DummyEvent will never change to True.")


class Event(ContextObject):
    r"""Multiprocessing/threading event."""

    _base_attr = (ContextObject._base_attr
                  + ['is_set', 'set', 'clear', 'wait'])

    @property
    def dummy_copy(self):
        r"""Dummy copy of base."""
        return DummyEvent(self._base.is_set())
        
    def __getstate__(self):
        state = super(Event, self).__getstate__()
        if not self.parallel:
            state['_base'] = state['_base'].is_set()
        return state

    def __setstate__(self, state):
        if isinstance(state['_base'], bool):
            val = state['_base']
            state['_base'] = threading.Event()
            if val:
                state['_base'].set()
        super(Event, self).__setstate__(state)


class DummyTask(DummyContextObject):  # pragma: no cover

    def __init__(self, name, exitcode, daemon):
        self.name = name
        self.exitcode = exitcode
        self.daemon = daemon
        super(DummyTask, self).__init__()

    def join(self, *args, **kwargs):
        return

    def is_alive(self):
        return False

    def terminate(self):
        pass
    

class Task(ContextObject):
    r"""Multiprocessing/threading process."""

    _base_attr = ['name', 'daemon', 'authkey', 'sentinel', 'exitcode',
                  'pid']
    _base_meth = ['start', 'run', 'join',
                  # Thread only
                  'getName', 'setName', 'isDaemon', 'setDaemon',
                  # Process only
                  'terminate']

    @classmethod
    def get_base_class(cls, context):
        r"""Get instance of base class that will be represented."""
        if context.parallel:
            return context._base.Process
        else:
            return SafeThread

    @property
    def dummy_copy(self):
        r"""Dummy copy of base."""
        return DummyTask(name=self._base.name,
                         exitcode=self._base.exitcode,
                         daemon=self._base.daemon)
        
    def __getstate__(self):
        state = super(Task, self).__getstate__()
        if not self.parallel:
            state['_base'] = {
                'name': state['_base']._name, 'group': None,
                'daemon': state['_base'].daemon,
                'target': state['_base']._target,
                'args': state['_base']._args,
                'kwargs': state['_base']._kwargs}
        return state

    def __setstate__(self, state):
        if isinstance(state['_base'], dict):
            state['_base'] = SafeThread(**state['_base'])
        super(Task, self).__setstate__(state)

    def is_alive(self):
        r"""Determine if the process/thread is alive."""
        out = self._base.is_alive()
        if out is None:
            out = False
        return out

    # Called before cleanup called
    @property
    def ident(self):
        r"""Process ID."""
        if self.parallel:
            return self._base.pid
        else:
            return self._base.ident


class DummyQueue(DummyContextObject):  # pragma: no cover

    def empty(self):
        return True

    def full(self):
        return False

    def get(self, *args, **kwargs):
        raise RuntimeError("There are no messages in a DummyQueue.")

    def get_nowait(self, *args, **kwargs):
        raise RuntimeError("There are no messages in a DummyQueue.")

    def put(self, *args, **kwargs):
        raise RuntimeError("Cannot put messages in a DummyQueue.")

    def put_nowait(self, *args, **kwargs):
        raise RuntimeError("Cannot put messages in a DummyQueue.")

    def qsize(self):
        return 0

    def join(self, *args, **kwargs):
        return

    def join_thread(self, *args, **kwargs):
        return
    
    def close(self):
        pass


class Queue(ContextObject):
    r"""Multiprocessing/threading queue."""

    _base_meth = ['empty', 'full', 'get', 'get_nowait', 'join_thread',
                  'put', 'put_nowait', 'qsize']
    
    @classmethod
    def get_base_class(cls, context):
        r"""Get instance of base class that will be represented."""
        if context.parallel:
            return context._base.Queue
        else:
            return queue.Queue

    @property
    def dummy_copy(self):
        r"""Dummy copy of base."""
        return DummyQueue()

    def join(self, *args, **kwargs):
        self.check_for_base('join')
        if self.parallel:
            self._base.close()
            return self._base.join_thread(*args, **kwargs)
        else:
            return self._base.join(*args, **kwargs)

    def cleanup(self):
        r"""Cleanup the class."""
        self.join()
        super(Queue, self).cleanup()


class Dict(ContextObject):
    r"""Multiprocessing/threading shared dictionary."""

    _base_meth = ['clear', 'copy', 'get', 'items', 'keys',
                  'pop', 'popitem', 'setdefault', 'update', 'values',
                  '__contains__', '__delitem__', '__getitem__',
                  '__iter__', '__len__', '__setitem__']
    
    @classmethod
    def get_base_class(cls, context):
        r"""Get instance of base class that will be represented."""
        if context.parallel:
            manager = context._base.Manager()
            return manager.dict
        else:
            return LockedDict

    # Don't define this so that is is not called after manager is
    # shut down.
    # @property
    # def dummy_copy(self):
    #     r"""Dummy copy of base."""
    #     return self._base.copy()
        
    def cleanup(self):
        r"""Cleanup the class."""
        try:
            final_value = self._base.copy()
        except BaseException:
            final_value = {}
        if isinstance(self._base, LockedDict):
            self._base.cleanup()
        if getattr(self._base, '_manager', None) is not None:
            self._base._manager.shutdown()
        if hasattr(self._base, '_close'):
            self._base._close()
        super(Dict, self).cleanup()
        self._base = final_value


class LockedObject(AliasObject):
    r"""Container that provides a lock that is acquired before accessing
    the object."""

    _base_locked = True
    
    def __init__(self, *args, task_method='process',
                 task_context=None, **kwargs):
        self.lock = RLock(task_method=task_method,
                          task_context=task_context)
        if issubclass(self._base_class, ContextObject):
            kwargs['task_method'] = task_method
            kwargs['task_context'] = task_context
        super(LockedObject, self).__init__(*args, **kwargs)

    def cleanup(self):
        r"""Cleanup the class."""
        super(LockedObject, self).cleanup()
        self.lock.cleanup()


# class LockedList(LockedObject):
#     r"""List intended to be shared between threads."""

#     def __init__(self, *args, **kwargs):
#         base = list(*args, **kwargs)
#         super(LockedList, self).__init__(base)


class LockedDict(LockedObject):
    r"""Dictionary that can be shared between threads."""

    _base_class = dict
    _base_meth = ['clear', 'copy', 'get', 'items', 'keys',
                  'pop', 'popitem', 'setdefault', 'update', 'values',
                  '__contains__', '__delitem__', '__getitem__',
                  '__iter__', '__len__', '__setitem__']
    
    def add_subdict(self, key):
        r"""Add a subdictionary."""
        self[key] = {}

    @property
    def dummy_copy(self):
        r"""Dummy copy of base."""
        try:
            out = self._base.copy()
        except BaseException:
            out = {}
        return out


class LockedWeakValueDict(LockedDict):
    r"""Dictionary of weakrefs that can be shared between threads."""

    _base_class = weakref.WeakValueDictionary
    _base_attr = ['data']
    _base_meth = ['itervaluerefs', 'valuerefs']
    
    def __init__(self, *args, **kwargs):
        self._dict_refs = {}
        super(LockedWeakValueDict, self).__init__(*args, **kwargs)

    def add_subdict(self, key):
        r"""Add a subdictionary."""
        self._dict_refs[key] = weakref.WeakValueDictionary()
        self[key] = self._dict_refs[key]


class LockedQueue(LockedObject):
    r"""Locked queue."""

    _base_class = Queue
    _base_meth = ['empty', 'full', 'get', 'get_nowait', 'join_thread',
                  'put', 'put_nowait', 'qsize', 'join']
    _unlocked_attr = ['empty', 'full', 'get', 'get_nowait',
                      'join_thread', 'put', 'put_nowait', 'join']

    @property
    def context(self):
        r"""Context: Context used to create this object."""
        return self._base.context

    @property
    def dummy_copy(self):
        r"""Dummy copy of base."""
        return DummyQueue()
        
    def cleanup(self):
        r"""Cleanup the class."""
        self._base.cleanup()
        super(LockedQueue, self).cleanup()


class YggTask(YggClass):
    r"""Class for managing Ygg thread/process."""

    _cleanup_attr = (YggClass._cleanup_attr
                     + ['context', 'lock', 'process_instance',
                        'error_flag', 'start_flag', 'terminate_flag'])
    
    def __init__(self, name=None, target=None, args=(), kwargs=None,
                 daemon=False, group=None, task_method='thread',
                 context=None, with_pipe=False, **ygg_kwargs):
        global _lock_registry
        if kwargs is None:
            kwargs = {}
        if (target is not None) and ('target' in self._schema_properties):
            ygg_kwargs['target'] = target
            target = None
        self.context = Context.from_base(task_method=task_method,
                                         base=context)
        self.as_process = self.context.parallel
        if self.as_process:
            self.in_process = False
            self.pipe = None
            self.send_pipe = None
            if with_pipe:
                self.pipe = self.context._base.Pipe()
                kwargs['send_pipe'] = self.pipe[1]
        else:
            self.in_process = True
        process_kwargs = dict(
            name=name, group=group, daemon=daemon,
            target=self.run)
        self.process_instance = self.context.Task(**process_kwargs)
        self._ygg_target = target
        self._ygg_args = args
        self._ygg_kwargs = kwargs
        self.lock = self.context.RLock()
        self.create_flag_attr('error_flag')
        self.create_flag_attr('start_flag')
        self.create_flag_attr('terminate_flag')
        self._calling_thread = None
        super(YggTask, self).__init__(name, **ygg_kwargs)
        # if not self.as_process:
        #     _thread_registry[self.name] = self
        #     _lock_registry[self.name] = self.lock
        #     atexit.register(self.atexit)

    def __getstate__(self):
        out = super(YggTask, self).__getstate__()
        out.pop('_input_args', None)
        out.pop('_input_kwargs', None)
        return out
        
    def create_flag_attr(self, attr):
        r"""Create a flag."""
        setattr(self, attr, self.context.Event())

    def set_flag_attr(self, attr):
        r"""Set a flag."""
        getattr(self, attr).set()

    def unset_flag_attr(self, attr):
        r"""Unset a flag."""
        getattr(self, attr).unset()

    def check_flag_attr(self, attr):
        r"""Determine if a flag is set."""
        flag = getattr(self, attr, None)
        if flag is None:
            return False
        else:
            return flag.is_set()

    def wait_flag_attr(self, attr, timeout=None):
        r"""Wait until a flag is True."""
        return getattr(self, attr).wait(timeout=timeout)

    def start(self, *args, **kwargs):
        r"""Start thread/process and print info."""
        if not self.was_terminated:
            self.set_started_flag()
            self.before_start()
        self.process_instance.start(*args, **kwargs)
        # self._calling_thread = self.get_current_task()

    def before_start(self):
        r"""Actions to perform on the main thread/process before
        starting the thread/process."""
        self.debug('')

    def run(self, *args, **kwargs):
        r"""Continue running until terminate event set."""
        self.debug("Starting method")
        try:
            self.run_init()
            self.call_target()
        except BaseException:  # pragma: debug
            self.run_error()
        finally:
            self.run_finally()

    def run_init(self):
        r"""Actions to perform at beginning of run."""
        # atexit.register(self.atexit)
        self.debug('pid = %s, ident = %s', self.pid, self.ident)
        self.in_process = True
        if self.as_process and ('send_pipe' in self._ygg_kwargs):
            self.send_pipe = self._ygg_kwargs.pop('send_pipe')

    def call_target(self):
        r"""Call target."""
        if self._ygg_target:
            self._ygg_target(*self._ygg_args, **self._ygg_kwargs)

    def run_error(self):
        r"""Actions to perform on error in try/except wrapping run."""
        self.exception("%s ERROR", self.context.task_method.upper())
        self.set_flag_attr('error_flag')

    def run_finally(self):
        r"""Actions to perform in finally clause of try/except wrapping
        run."""
        if self.as_process:
            if self.send_pipe is not None:
                self.send_pipe.close()
        for k in ['_ygg_target', '_ygg_args', '_ygg_kwargs']:
            if hasattr(self, k):
                delattr(self, k)

    def join(self, *args, **kwargs):
        r"""Join the process/thread."""
        return self.process_instance.join(*args, **kwargs)

    def is_alive(self, *args, **kwargs):
        r"""Determine if the process/thread is alive."""
        return self.process_instance.is_alive(*args, **kwargs)

    @property
    def pid(self):
        r"""Process ID."""
        return self.process_instance.pid

    @property
    def ident(self):
        r"""Process ID."""
        return self.process_instance.ident

    @property
    def daemon(self):
        r"""bool: Indicates whether the thread/process is daemonic or not."""
        return self.process_instance.daemon
        
    @property
    def exitcode(self):
        r"""Exit code."""
        if self.as_process:
            return self.process_instance.exitcode
        else:
            return int(self.check_flag_attr('error_flag'))

    @property
    def returncode(self):
        r"""Return code."""
        return self.exitcode

    def kill(self, *args, **kwargs):
        r"""Kill the process."""
        if self.as_process:
            return self.terminate(*args, **kwargs)
        else:
            return self.process_instance.kill(*args, **kwargs)

    def terminate(self, no_wait=False):
        r"""Set the terminate event and wait for the thread/process to stop.

        Args:
            no_wait (bool, optional): If True, terminate will not block until
                the thread/process stops. Defaults to False and blocks.

        Raises:
            AssertionError: If no_wait is False and the thread/process has not
                stopped after the timeout.

        """
        self.debug('')
        with self.lock:
            if self.was_terminated:  # pragma: debug
                self.debug('Driver already terminated.')
                return
            self.set_terminated_flag()
        if not no_wait:
            # if self.is_alive():
            #     self.join(self.timeout)
            self.wait(timeout=self.timeout)
            assert(not self.is_alive())
        # if self.as_process:
        #     self.process_instance.terminate()

    def poll(self):
        r"""Check if the process is finished and return the return
        code if it is."""
        out = None
        if not self.is_alive():
            out = self.returncode
        return out

    def get_current_task(self):
        r"""Get the current process/thread."""
        return self.context.current_task()

    def get_main_proc(self):
        r"""Get the main process/thread."""
        return self.context.main_task()

    def set_started_flag(self):
        r"""Set the started flag for the thread/process to True."""
        self.set_flag_attr('start_flag')

    def set_terminated_flag(self):
        r"""Set the terminated flag for the thread/process to True."""
        self.set_flag_attr('terminate_flag')

    def unset_started_flag(self):  # pragma: debug
        r"""Set the started flag for the thread/process to False."""
        self.unset_flag_attr('start_flag')

    def unset_terminated_flag(self):  # pragma: debug
        r"""Set the terminated flag for the thread/process to False."""
        self.unset_flag_attr('terminated_flag')

    @property
    def was_started(self):
        r"""bool: True if the thread/process was started. False otherwise."""
        return self.check_flag_attr('start_flag')

    @property
    def was_terminated(self):
        r"""bool: True if the thread/process was terminated. False otherwise."""
        return self.check_flag_attr('terminate_flag')

    @property
    def main_terminated(self):
        r"""bool: True if the main thread/process has terminated."""
        return (not self.get_main_proc().is_alive())

    def wait(self, timeout=None, key=None):
        r"""Wait until thread/process finish to return using sleeps rather than
        blocking.

        Args:
            timeout (float, optional): Maximum time that should be waited for
                the driver to finish. Defaults to None and is infinite.
            key (str, optional): Key that should be used to register the timeout.
                Defaults to None and is set based on the stack trace.

        """
        T = self.start_timeout(timeout, key_level=1, key=key)
        while self.is_alive() and not T.is_out:
            self.verbose_debug('Waiting for %s to finish...',
                               self.context.task_method)
            self.sleep()
        self.stop_timeout(key_level=1, key=key)

    def atexit(self):  # pragma: debug
        r"""Actions performed when python exits."""
        if self.is_alive():
            self.info('%s alive at exit', self.context.task_method.title())
        super(YggTask, self).atexit()
        

class YggTaskLoop(YggTask):
    r"""Class to run a loop inside a thread/process."""

    _cleanup_attr = (YggTask._cleanup_attr
                     + ['break_flag', 'loop_flag'])

    def __init__(self, *args, **kwargs):
        super(YggTaskLoop, self).__init__(*args, **kwargs)
        self._1st_main_terminated = False
        self.create_flag_attr('break_flag')
        self.create_flag_attr('loop_flag')

    def on_main_terminated(self, dont_break=False):  # pragma: debug
        r"""Actions performed when 1st main terminated.

        Args:
            dont_break (bool, optional): If True, the break flag won't be set.
                Defaults to False.

        """
        self._1st_main_terminated = True
        if not dont_break:
            self.set_break_flag()

    def set_break_flag(self):
        r"""Set the break flag for the thread/process to True."""
        self.set_flag_attr('break_flag')

    def unset_break_flag(self):  # pragma: debug
        r"""Set the break flag for the thread/process to False."""
        self.unset_flag_attr('break_flag')

    @property
    def was_break(self):
        r"""bool: True if the break flag was set."""
        return self.check_flag_attr('break_flag')

    def set_loop_flag(self):
        r"""Set the loop flag for the thread/process to True."""
        self.set_flag_attr('loop_flag')

    def unset_loop_flag(self):  # pragma: debug
        r"""Set the loop flag for the thread/process to False."""
        self.unset_flag_attr('loop_flag')

    @property
    def was_loop(self):
        r"""bool: True if the thread/process was loop. False otherwise."""
        return self.check_flag_attr('loop_flag')

    def wait_for_loop(self, timeout=None, key=None):
        r"""Wait until thread/process enters loop to return using sleeps rather than
        blocking.

        Args:
            timeout (float, optional): Maximum time that should be waited for
                the thread/process to enter loop. Defaults to None and is infinite.
            key (str, optional): Key that should be used to register the timeout.
                Defaults to None and is set based on the stack trace.

        """
        T = self.start_timeout(timeout, key_level=1, key=key)
        while (self.is_alive() and (not self.was_loop)
               and (not T.is_out)):  # pragma: debug
            self.verbose_debug('Waiting for thread/process to enter loop...')
            self.sleep()
        self.stop_timeout(key_level=1, key=key)

    def before_loop(self):
        r"""Actions performed before the loop."""
        self.debug('')

    def after_loop(self):
        r"""Actions performed after the loop."""
        self.debug('')

    def call_target(self):
        r"""Call target."""
        self.debug("Starting loop")
        self.before_loop()
        if (not self.was_break):
            self.set_loop_flag()
        while (not self.was_break):
            if ((self.main_terminated
                 and (not self._1st_main_terminated))):  # pragma: debug
                self.on_main_terminated()
            else:
                self.run_loop()
        self.set_break_flag()
        
    def run_loop(self, *args, **kwargs):
        r"""Actions performed on each loop iteration."""
        if self._ygg_target:
            self._ygg_target(*self._ygg_args, **self._ygg_kwargs)
        else:
            self.set_break_flag()

    def run_error(self):
        r"""Actions to perform on error in try/except wrapping run."""
        super(YggTaskLoop, self).run_error()
        self.set_break_flag()
        
    def run(self, *args, **kwargs):
        r"""Continue running until terminate event set."""
        super(YggTaskLoop, self).run(*args, **kwargs)
        try:
            self.after_loop()
        except BaseException:  # pragma: debug
            self.exception("AFTER LOOP ERROR")
            self.set_flag_attr('error_flag')

    def terminate(self, *args, **kwargs):
        r"""Also set break flag."""
        self.set_break_flag()
        super(YggTaskLoop, self).terminate(*args, **kwargs)