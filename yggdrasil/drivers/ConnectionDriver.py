"""Module for funneling messages from one comm to another."""
import os
import copy
import numpy as np
import functools
import queue
from yggdrasil import multitasking
from yggdrasil.communication import new_comm, CommBase
from yggdrasil.drivers.Driver import Driver
from yggdrasil.components import create_component, isinstance_component


def _translate_list2element(arr):
    if isinstance(arr, (list, tuple)):
        arr = arr[0]
    return arr


class TaskThreadError(RuntimeError):
    pass


def run_remotely(method):
    r"""Decorator for methods that should be run remotely."""
    @functools.wraps(method)
    def modified_method(self, *args, **kwargs):
        method_name = method.__name__
        if self.can_run_remotely:
            try:
                return self.task_thread.run_task_remote(method_name, args, kwargs)
            except (TaskThreadError,
                    multitasking.AliasDisconnectError):  # pragma: debug
                pass
        return method(self, *args, **kwargs)
    return modified_method


class RemoteTaskLoop(multitasking.YggTaskLoop):
    r"""Class to handle running tasks on the connection loop process."""

    _disconnect_attr = (multitasking.YggTaskLoop._disconnect_attr
                        + ['q_tasks', 'q_results'])

    def __init__(self, connection, **kwargs):
        self.connection = connection
        self.q_tasks = multitasking.Queue(
            task_method='process',
            task_context=connection.process_instance.context)
        self.q_results = multitasking.Queue(
            task_method='process',
            task_context=connection.process_instance.context)
        super(RemoteTaskLoop, self).__init__(target=self.target, **kwargs)
        # Overwrite break flag with process safe Event
        self.break_flag = multitasking.Event(
            task_method='process',
            task_context=connection.process_instance.context)

    def __getstate__(self):
        out = super(RemoteTaskLoop, self).__getstate__()
        del out['connection']
        return out

    def is_open(self):
        return (not self.was_break)

    def close(self):
        r"""Close the queues."""
        self.terminate()
        self.q_tasks.disconnect()
        self.q_results.disconnect()

    def run_task_local(self, task, args, kwargs):
        r"""Run task on the current process."""
        f_task = getattr(self.connection, task)
        if hasattr(f_task, '__call__'):
            out = f_task(*args, **kwargs)
        else:
            out = f_task
        return out

    def run_task_remote(self, task, args, kwargs):
        r"""Run task on the connection loop process."""
        assert(self.connection.as_process
               and (not self.connection.in_process)
               and self.connection.is_alive())
        if self.break_flag.is_set():  # pragma: debug
            raise TaskThreadError("Task thread was stopped.")
        self.q_tasks.put_nowait((task, args, kwargs))
        try:
            out = self.q_results.get(timeout=180.0)
        except queue.Empty:  # pragma: debug
            raise TaskThreadError("Task thread was stopped.")
        if out == 'TERMINATED':  # pragma: debug
            raise TaskThreadError("Task thread was stopped.")
        return out

    def after_loop(self):
        r"""Actions performed after the loop."""
        super(RemoteTaskLoop, self).after_loop()
        try:
            while not self.q_tasks.empty():  # pragma: debug
                self.q_tasks.get_nowait()
                self.q_results.put('TERMINATED')
        except multitasking.AliasDisconnectError:  # pragma: debug
            pass

    def target(self):
        r"""Complete all pending tasks."""
        try:
            while not self.q_tasks.empty():
                self.debug("Task waiting")
                args = self.q_tasks.get_nowait()
                self.debug("Task received: %s", args)
                out = self.run_task_local(*args)
                self.debug("Task complete: %s = %s", args, out)
                self.q_results.put(out)
                self.debug("Task returned: %s", args)
            if self.was_break:
                return
            self.sleep()
        except multitasking.AliasDisconnectError:  # pragma: debug
            self.set_break_flag()


class ConnectionDriver(Driver):
    r"""Class that continuously passes messages from one comm to another.

    Args:
        name (str): Name that should be used to set names of input/output comms.
        inputs (list, optional): One or more dictionaries containing keyword
            arguments for constructing input communicators. Defaults to an
            empty dictionary if not provided.
        outputs (list, optional): One or more dictionaries containing keyword
            arguments for constructing output communicators. Defaults to an
            empty dictionary if not provided.
        translator (str, func, optional): Function or string specifying function
            that should be used to translate messages from the input communicator
            before passing them to the output communicator. If a string, the
            format should be "<package.module>:<function>" so that <function>
            can be imported from <package>. Defaults to None and messages are
            passed directly. This can also be a list of functions/strings that
            will be called on the messages in the order they are provided.
        timeout_send_1st (float, optional): Time in seconds that should be
            waited before giving up on the first send. Defaults to self.timeout.
        single_use (bool, optional): If True, the driver will be stopped after
            one loop. Defaults to False.
        onexit (str, optional): Class method that should be called when a
            model that the connection interacts with exits, but before the
            connection driver is shut down. Defaults to None.
        **kwargs: Additonal keyword arguments are passed to the parent class.

    Attributes:
        icomm_kws (dict): Keyword arguments for the input communicator.
        ocomm_kws (dict): Keyword arguments for the output communicator.
        icomm (CommBase): Input communicator.
        ocomm (CommBase): Output communicator.
        nrecv (int): Number of messages received.
        nproc (int): Number of messages processed.
        nsent (int): Number of messages sent.
        state (str): Descriptor of last action taken.
        translator (func): Function that will be used to translate messages from
            the input communicator before passing them to the output communicator.
        timeout_send_1st (float): Time in seconds that should be waited before
            giving up on the first send.
        single_use (bool): If True, the driver will be stopped after one
            loop.
        onexit (str): Class method that should be called when the corresponding
            model exits, but before the driver is shut down.

    """

    _connection_type = 'default'
    _icomm_type = 'default'
    _ocomm_type = 'default'
    _direction = 'any'
    _schema_type = 'connection'
    _schema_subtype_key = 'connection_type'
    _schema_subtype_description = ('Connection between one or more comms/files '
                                   'and one or more comms/files.')
    _schema_subtype_default = 'default'
    _connection_type = 'connection'
    _schema_required = ['inputs', 'outputs']
    _schema_properties = {
        'connection_type': {'type': 'string'},
        'inputs': {'type': 'array', 'minItems': 1,
                   'items': {'anyOf': [{'$ref': '#/definitions/comm'},
                                       {'$ref': '#/definitions/file'}]},
                   'default': [{}],
                   'description': (
                       'One or more name(s) of model output channel(s) '
                       'and/or new channel/file objects that the '
                       'connection should receive messages from. '
                       'A full description of file entries and the '
                       'available options can be found :ref:`here<'
                       'yaml_file_options>`.')},
        'outputs': {'type': 'array', 'minItems': 1,
                    'items': {'anyOf': [{'$ref': '#/definitions/comm'},
                                        {'$ref': '#/definitions/file'}]},
                    'default': [{}],
                    'description': (
                        'One or more name(s) of model input channel(s) '
                        'and/or new channel/file objects that the '
                        'connection should send messages to. '
                        'A full description of file entries and the '
                        'available options can be found :ref:`here<'
                        'yaml_file_options>`.')},
        'translator': {'type': 'array',
                       'items': {'oneOf': [
                           {'type': 'function'},
                           {'$ref': '#/definitions/transform'}]}},
        'onexit': {'type': 'string'}}
    _schema_excluded_from_class_validation = ['inputs', 'outputs']
    _disconnect_attr = Driver._disconnect_attr + [
        '_comm_closed', '_skip_after_loop', 'shared', 'task_thread']

    def __init__(self, name, translator=None, single_use=False, onexit=None, **kwargs):
        # kwargs['method'] = 'process'
        super(ConnectionDriver, self).__init__(name, **kwargs)
        # Shared attributes (set once or synced using events)
        self.single_use = single_use
        self.shared = self.context.Dict()
        self.shared.update(nrecv=0, nproc=0, nsent=0,
                           state='started', close_state='',
                           _comm_closed=multitasking.DummyEvent(),
                           _skip_after_loop=multitasking.DummyEvent())
        # Attributes used by process
        self._eof_sent = False
        self._first_send_done = False
        self._used = False
        self.onexit = None
        self.task_thread = None
        if self.as_process:
            self.task_thread = RemoteTaskLoop(
                self, name=('%s.TaskThread' % self.name))
        # Translator
        if translator is None:
            translator = []
        elif not isinstance(translator, list):
            translator = [translator]
        self.translator = []
        for t in translator:
            if isinstance(t, dict):
                t = create_component('transform', **t)
            if not hasattr(t, '__call__'):
                raise ValueError("Translator %s not callable." % t)
            self.translator.append(t)
        if (onexit is not None) and (not hasattr(self, onexit)):
            raise ValueError("onexit '%s' is not a class method." % onexit)
        self.onexit = onexit
        # Add comms and print debug info
        self._init_comms(name, **kwargs)
        self.models = {'input': list(self.icomm.model_env.keys()),
                       'output': list(self.ocomm.model_env.keys())}
        # self.debug('    env: %s', str(self.env))
        self.debug(('\n' + 80 * '=' + '\n'
                    + 'class = %s\n'
                    + '    input: name = %s, address = %s\n'
                    + '    output: name = %s, address = %s\n'
                    + (80 * '=')), self.__class__,
                   self.icomm.name, self.icomm.address,
                   self.ocomm.name, self.ocomm.address)

    def _init_single_comm(self, io, comm_list):
        r"""Parse keyword arguments for input/output comm."""
        self.debug("Creating %s comm", io)
        comm_kws = dict()
        assert(isinstance(comm_list, list))
        assert(comm_list)
        if io == 'input':
            direction = 'recv'
            attr_comm = 'icomm'
            comm_kws['close_on_eof_recv'] = False
            comm_type = self._icomm_type
        else:
            direction = 'send'
            attr_comm = 'ocomm'
            comm_type = self._ocomm_type
        comm_kws['direction'] = direction
        comm_kws['dont_open'] = True
        comm_kws['reverse_names'] = True
        comm_kws['use_async'] = True
        comm_kws['name'] = self.name
        for i, x in enumerate(comm_list):
            if x is None:
                comm_list[i] = dict()
            else:
                assert(isinstance(x, dict))
            if 'filetype' not in comm_list[i]:
                comm_list[i].setdefault('commtype', comm_type)
            if self.as_process:
                comm_list[i]['buffer_task_method'] = 'process'
            if (((comm_list[i].get('partner_copies', 0) > 1)
                 and (not comm_list[i].get('is_client', False))
                 and (direction == 'send')
                 and (not comm_list[i].get('dont_copy', False)))):
                from yggdrasil.communication import ForkComm
                # TODO: Handle recv?
                comm_list[i]['commtype'] = [
                    dict(comm_list[i],
                         partner_model=(
                             '%s_copy%d' % (comm_list[i]['partner_model'], idx)))
                    for idx in range(comm_list[i]['partner_copies'])]
                for k in ForkComm.ForkComm.child_keys:
                    comm_list[i].pop(k, None)
        comm_kws['commtype'] = copy.deepcopy(comm_list)
        self.debug('%s comm_kws:\n%s', attr_comm, self.pprint(comm_kws, 1))
        setattr(self, attr_comm, new_comm(**comm_kws))
        setattr(self, '%s_kws' % attr_comm, comm_kws)

    def _init_comms(self, name, **kwargs):
        r"""Parse keyword arguments for input/output comms."""
        self._init_single_comm('input', self.inputs)
        try:
            self._init_single_comm('output', self.outputs)
        except BaseException:
            self.icomm.close()
            raise
        # Apply keywords dependent on comms
        if self.icomm.any_files:
            kwargs.setdefault('timeout_send_1st', 60)
        self.timeout_send_1st = kwargs.pop('timeout_send_1st', self.timeout)
        self.debug('Final env:\n%s', self.pprint(self.env, 1))

    def __setstate__(self, state):
        super(ConnectionDriver, self).__setstate__(state)
        if self.as_process:
            self.task_thread.connection = self

    @property
    def model_env(self):
        r"""dict: Mapping between model name and opposite comm
        environment variables that need to be provided to the model."""
        out = {}
        for x in [self.icomm, self.ocomm]:
            iout = x.model_env
            for k, v in iout.items():
                if k in out:
                    out[k].update(v)
                else:
                    out[k] = v
        return out
        
    def get_flag_attr(self, attr):
        r"""Return the flag attribute."""
        if attr in self.shared:
            return self.shared[attr]
        return super(ConnectionDriver, self).get_flag_attr(attr)

    def set_flag_attr(self, attr, value=True):
        r"""Set a flag."""
        if attr in self.shared:
            exist = self.shared[attr]
            if value:
                exist.set()
            else:
                exist.clear()
            self.shared[attr] = exist
            return
        super(ConnectionDriver, self).set_flag_attr(attr, value=value)

    @property
    def nrecv(self):
        r"""int: Number of messages received."""
        return self.shared['nrecv']

    @nrecv.setter
    def nrecv(self, x):
        self.shared['nrecv'] = x

    @property
    def nsent(self):
        r"""int: Number of messages sent."""
        return self.shared['nsent']

    @nsent.setter
    def nsent(self, x):
        self.shared['nsent'] = x

    @property
    def nproc(self):
        r"""int: Number of messages processed."""
        return self.shared['nproc']

    @nproc.setter
    def nproc(self, x):
        self.shared['nproc'] = x

    @property
    def state(self):
        r"""str: Current state of the connection."""
        return self.shared['state']

    @state.setter
    def state(self, x):
        if hasattr(self, 'shared'):
            self.shared['state'] = x

    @property
    def close_state(self):
        r"""str: State of the connection at close."""
        return self.shared['close_state']

    @close_state.setter
    def close_state(self, x):
        self.shared['close_state'] = x

    @property
    def can_run_remotely(self):
        r"""bool: True if process should be run remotely."""
        return (self.as_process and (not self.in_process)
                and self.is_alive()
                and self.task_thread.is_open())

    @run_remotely
    def wait_for_route(self, timeout=None):
        r"""Wait until messages have been routed."""
        T = self.start_timeout(timeout, key_suffix='.route')
        while ((not T.is_out)
               and (self.nrecv != self.nsent)):  # pragma: debug
            self.sleep()
        self.stop_timeout(key_suffix='.route')
        return (self.nrecv == self.nsent)

    @property
    @run_remotely
    def is_valid(self):
        r"""bool: Returns True if the connection is open and the parent class
        is valid."""
        with self.lock:
            return (super(ConnectionDriver, self).is_valid
                    and self.is_comm_open and not (self.single_use and self._used))

    @property
    @run_remotely
    def is_comm_open(self):
        r"""bool: Returns True if both communicators are open."""
        with self.lock:
            return (self.icomm.is_open and self.ocomm.is_open
                    and not self.check_flag_attr('_comm_closed'))

    @property
    @run_remotely
    def is_comm_closed(self):
        r"""bool: Returns True if both communicators are closed."""
        with self.lock:
            return self.icomm.is_closed and self.ocomm.is_closed

    @property
    @run_remotely
    def n_msg(self):
        r"""int: Number of messages waiting in input communicator."""
        with self.lock:
            return self.icomm.n_msg_recv

    @run_remotely
    def open_comm(self):
        r"""Open the communicators."""
        self.debug('')
        with self.lock:
            if self.check_flag_attr('_comm_closed'):
                self.debug('Aborted as comm closed')
                return
            try:
                self.icomm.open()
                self.ocomm.open()
            except BaseException:
                self.close_comm()
                raise
        self.debug('Returning')

    @run_remotely
    def close_comm(self):
        r"""Close the communicators."""
        self.debug('')
        with self.lock:
            self.set_flag_attr('_comm_closed')
            self.set_flag_attr('_skip_after_loop')
            # Capture errors for both comms
            ie = None
            oe = None
            try:
                if getattr(self, 'icomm', None) is not None:
                    self.icomm.close()
            except BaseException as e:
                ie = e
            try:
                if getattr(self, 'ocomm', None) is not None:
                    self.ocomm.close()
            except BaseException as e:
                oe = e
            if ie:
                raise ie
            if oe:
                raise oe
        self.debug('Returning')

    def start(self):
        r"""Open connection before running."""
        if not self.as_process:
            self.open_comm()
            Tout = self.start_timeout()
            while (not self.is_comm_open) and (not Tout.is_out):
                self.sleep()
            self.stop_timeout()
            if not self.is_comm_open:
                raise Exception("Connection never finished opening.")
        super(ConnectionDriver, self).start()
        self.debug('Started connection process')
        if self.as_process:
            self.wait_flag_attr('loop_flag', timeout=120.0)
            self.icomm.disconnect()
            self.ocomm.disconnect()

    def graceful_stop(self, timeout=None, **kwargs):
        r"""Stop the driver, first waiting for the input comm to be empty.

        Args:
            timeout (float, optional): Max time that should be waited. Defaults
                to None and is set to attribute timeout.
            **kwargs: Additional keyword arguments are passed to the parent
                class's graceful_stop method.

        """
        self.debug('')
        with self.lock:
            self.set_close_state('stop')
            self.set_flag_attr('_skip_after_loop')
        self.drain_input(timeout=timeout)
        self.wait_for_route(timeout=timeout)
        self.drain_output(timeout=timeout)
        super(ConnectionDriver, self).graceful_stop()
        self.debug('Returning')

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
        self.debug('')
        with self.lock:
            if name in self.models[direction]:
                self.models[direction].remove(name)
            self.debug(("%s model '%s' signed off."
                        "\n\tInput  models: %d"
                        "\n\tOutput models: %d")
                       % (direction.title(), name,
                          len(self.models["input"]),
                          len(self.models["output"])))
            return (len(self.models[direction]) == 0)

    @run_remotely
    def on_model_exit_remote(self, direction, name,
                             errors=False):
        r"""Drain input and then close it (on the remote process).

        Args:
            direction (str): Direction of model.
            name (str): Name of model exiting.
            errors (list, optional): Errors generated by the
                model. Defaults to False.

        Returns:
            bool: True if all of the input/output models have signed
                off; False otherwise.

        """
        if not self.remove_model(direction, name):
            self.debug("%s models remain: %s",
                       direction, self.models[direction])
            return False
        if not self.is_alive():
            return False
        self.debug("All %s models have signed off.", direction)
        if (((self.onexit not in [None, 'on_model_exit',
                                  'pass'])
             and (not errors))):
            self.debug("Calling onexit = '%s'" % self.onexit)
            getattr(self, self.onexit)()
        if not errors:
            if direction == 'output':
                T = self.start_timeout(60, key_suffix='.model_exit')
                while (not T.is_out) and self.models['input']:
                    self.debug("remaining input models: %s",
                               self.models['input'])
                    self.sleep(10 * self.sleeptime)
                self.stop_timeout(key_suffix='.model_exit')
                self.drain_input(timeout=self.timeout)
        if direction == 'input':
            if not errors:
                self.wait_for_route(timeout=self.timeout)
            with self.lock:
                self.icomm.close()
        elif direction == 'output':
            with self.lock:
                # self.icomm.close()
                self.ocomm.close()
        self.set_close_state('%s model exit' % direction)
        self.debug('Exit of %s model triggered close', direction)
        self.set_break_flag()
        return True

    def on_model_exit(self, direction, name, errors=False):
        r"""Drain input and then close it."""
        self.debug('%s model %s exiting', direction.title(), name)
        if self.on_model_exit_remote(direction, name,
                                     errors=errors):
            self.wait()
            self.debug('Finished')

    def do_terminate(self):
        r"""Stop the driver by closing the communicators."""
        self.debug('')
        self.set_close_state('terminate')
        self.close_comm()
        if self.as_process:
            self.task_thread.terminate()
        super(ConnectionDriver, self).do_terminate()

    def cleanup(self):
        r"""Ensure that the communicators are closed."""
        self.close_comm()
        if self.as_process:
            self.task_thread.close()
        super(ConnectionDriver, self).cleanup()

    @run_remotely
    def printStatus(self, beg_msg='', end_msg='',
                    verbose=False):
        r"""Print information on the status of the ConnectionDriver.

        Arguments:
            beg_msg (str, optional): Additional message to print at beginning.
            end_msg (str, optional): Additional message to print at end.
            verbose (bool, optional): If True, the status of
                individual comms will be displayed. Defaults to
                False.

        """
        msg = beg_msg
        msg += '%-50s' % (self.__module__.split('.')[-1] + '(' + self.name + '): ')
        msg += '%-30s' % ('last action: ' + self.state)
        msg += '%-25s' % ('is_open(%s, %s), ' % (self.icomm.is_open,
                                                 self.ocomm.is_open))
        msg += '%-15s' % (str(self.nrecv) + ' received, ')
        msg += '%-15s' % (str(self.nproc) + ' processed, ')
        msg += '%-15s' % (str(self.nsent) + ' sent, ')
        msg += '%-20s' % (str(self.icomm.n_msg) + ' ready to recv')
        msg += '%-20s' % (str(self.ocomm.n_msg) + ' ready to send')
        with self.lock:
            if self.close_state:
                msg += '%-30s' % ('close state: ' + self.close_state)
        msg += end_msg
        print(msg)
        if verbose:
            self.icomm.printStatus()
            self.ocomm.printStatus()

    @run_remotely
    def confirm_input(self, timeout=None):
        r"""Confirm receipt of messages from input comm."""
        T = self.start_timeout(timeout, key_suffix='.confirm_input')
        while not T.is_out:  # pragma: debug
            with self.lock:
                if (not self.icomm.is_open):
                    break
                elif self.icomm.is_confirmed_recv:
                    break
            self.sleep(10 * self.sleeptime)
        self.stop_timeout(key_suffix='.confirm_input')

    @run_remotely
    def confirm_output(self, timeout=None):
        r"""Confirm receipt of messages from output comm."""
        T = self.start_timeout(timeout, key_suffix='.confirm_output')
        while not T.is_out:  # pragma: debug
            with self.lock:
                if (not self.ocomm.is_open):
                    break
                elif self.ocomm.is_confirmed_send:
                    break
            self.sleep(10 * self.sleeptime)
        self.stop_timeout(key_suffix='.confirm_output')

    @run_remotely
    def drain_input(self, timeout=None):
        r"""Drain messages from input comm."""
        T = self.start_timeout(timeout, key_suffix='.drain_input')
        while not T.is_out:
            with self.lock:
                if (not (self.icomm.is_open
                         or self.was_terminated)):
                    break
                elif ((self.icomm.n_msg_recv_drain == 0)
                      and self.icomm.is_confirmed_recv):
                    break
            self.sleep()
        self.stop_timeout(key_suffix='.drain_input')

    @run_remotely
    def drain_output(self, timeout=None, dont_confirm_eof=False):
        r"""Drain messages from output comm."""
        nwait = 0
        if dont_confirm_eof:
            nwait += 1
        T = self.start_timeout(timeout, key_suffix='.drain_output')
        while not T.is_out:
            with self.lock:
                if (not (self.ocomm.is_open
                         or self.was_terminated)):  # pragma: no cover
                    break
                elif ((self.ocomm.n_msg_send_drain <= nwait)
                      and self.ocomm.is_confirmed_send):
                    break
            self.sleep()  # pragma: no cover
        self.stop_timeout(key_suffix='.drain_output')

    def before_loop(self):
        r"""Actions to perform prior to sending messages."""
        self.state = 'before loop'
        try:
            if self.as_process:
                self.task_thread.start()
            self.open_comm()
            self.sleep()  # Help ensure senders/receivers connected before messages
            self.debug('Running in %s, is_valid = %s', os.getcwd(), str(self.is_valid))
            assert(self.is_valid)
        except BaseException:  # pragma: debug
            self.printStatus()
            self.exception('Could not prep for loop (is_open = (%s, %s)).' % (
                self.icomm.is_open, self.ocomm.is_open))
            self.close_comm()
            self.set_break_flag()
            if self.as_process:
                self.task_thread.terminate()

    def after_loop_process(self):
        r"""Actions to preform after loop for process."""
        self.debug("After loop process")
        self.task_thread.set_break_flag()
        self.task_thread.wait()

    def after_loop(self):
        r"""Actions to perform after sending messages."""
        self.state = 'after loop'
        self.debug('')
        # Close input comm in case loop did not
        self.confirm_input(timeout=False)
        self.debug('Confirmed input')
        if self.check_flag_attr('_skip_after_loop') and self.as_process:
            self.after_loop_process()
        with self.lock:
            self.debug('Acquired lock')
            if self.check_flag_attr('_skip_after_loop'):
                self.debug("After loop skipped.")
                return
            self.icomm.close()
        # Send EOF in case the model didn't
        if not self.single_use:
            self.send_eof()
        # Do not close output comm in case model/connection still receiving
        if self.as_process and self.ocomm.touches_model:
            self.drain_output(timeout=False, dont_confirm_eof=True)
        self.debug('Finished')
        if self.as_process:
            self.after_loop_process()

    def recv_message(self, **kwargs):
        r"""Get a new message to send.

        Args:
            **kwargs: Additional keyword arguments are passed to the appropriate
                recv method.

        Returns:
            CommMessage, bool: False if no more messages, message otherwise.

        """
        assert(self.in_process)
        kwargs.setdefault('timeout', 0)
        with self.lock:
            if self.icomm.is_closed:
                return False
            msg = self.icomm.recv(return_message_object=True, **kwargs)
            self.errors += self.icomm.errors
        if msg.flag == CommBase.FLAG_EOF:
            return self.on_eof(msg)
        if msg.flag == CommBase.FLAG_SUCCESS:
            return msg
        else:
            return bool(msg.flag)

    def on_eof(self, msg):
        r"""Actions to take when EOF received.

        Args:
            msg (CommMessage): Message object that provided the EOF.

        Returns:
            CommMessage, bool: Value that should be returned by recv_message on EOF.

        """
        with self.lock:
            self.debug('EOF received')
            self.state = 'eof'
            self.set_close_state('eof')
            self.set_break_flag()
        self.debug('After EOF')
        return False

    def on_message(self, msg):
        r"""Process a message.

        Args:
            msg (bytes, str): Message to be processed.

        Returns:
            bytes, str: Processed message.

        """
        if (self.ocomm._send_serializer) and self.icomm.serializer.initialized:
            self.update_serializer(msg)
        for t in self.translator:
            msg.args = t(msg.args)
        return msg

    def update_serializer(self, msg):
        r"""Update the serializer for the output comm based on input."""
        self.debug('Before update:\n'
                   + '  icomm:\n    sinfo:\n%s\n    typedef:\n%s\n'
                   + '  ocomm:\n    sinfo:\n%s\n    typedef:\n%s',
                   self.pprint(self.icomm.serializer.serializer_info, 2),
                   self.pprint(self.icomm.serializer.typedef, 2),
                   self.pprint(self.ocomm.serializer.serializer_info, 2),
                   self.pprint(self.ocomm.serializer.typedef, 2))
        for t in self.translator:
            if isinstance_component(t, 'transform'):
                t.set_original_datatype(msg.stype)
                msg.stype = t.transformed_datatype
        # This can be removed if send_message is set up to update and send the
        # received message rather than create a new one by sending msg.args
        self.ocomm.update_serializer_from_message(msg)
        if (((msg.stype['type'] == 'array')
             and (self.ocomm.serializer.typedef['type'] != 'array')
             and (len(msg.stype['items']) == 1))):
            # if (((self.icomm.serializer.typedef['type'] == 'array')
            #      and (self.ocomm.serializer.typedef['type'] != 'array')
            #      and (len(self.icomm.serializer.typedef['items']) == 1))):
            self.translator.insert(0, _translate_list2element)
        self.debug('After update:\n'
                   + '  icomm:\n    sinfo:\n%s\n    typedef:\n%s\n'
                   + '  ocomm:\n    sinfo:\n%s\n    typedef:\n%s',
                   self.pprint(self.icomm.serializer.serializer_info, 2),
                   self.pprint(self.icomm.serializer.typedef, 2),
                   self.pprint(self.ocomm.serializer.serializer_info, 2),
                   self.pprint(self.ocomm.serializer.typedef, 2))

    def _send_message(self, *args, **kwargs):
        r"""Send a single message.

        Args:
            *args: Arguments are passed to the output comm send method.
            *kwargs: Keyword arguments are passed to the output comm send method.

        Returns:
            bool: Success or failure of send.

        """
        with self.lock:
            if self.ocomm.is_closed:
                return False
            return self.ocomm.send_message(*args, **kwargs)
        
    def _send_1st_message(self, *args, **kwargs):
        r"""Send the first message, trying multiple times.

        Args:
            *args: Arguments are passed to the output comm send method.
            *kwargs: Keyword arguments are passed to the output comm send method.

        Returns:
            bool: Success or failure of send.

        """
        self.ocomm._multiple_first_send = False
        T = self.start_timeout(self.timeout_send_1st,
                               key_suffix='.1st_send')
        flag = self._send_message(*args, **kwargs)
        self.ocomm.suppress_special_debug = True
        if (not flag) and (not self.ocomm._type_errors):
            self.debug("1st send failed, will keep trying for %f s in silence.",
                       float(self.timeout_send_1st))
            while ((not T.is_out) and (not flag)
                   and self.ocomm.is_open):  # pragma: debug
                flag = self._send_message(*args, **kwargs)
                if not flag:
                    self.sleep()
        self.stop_timeout(key_suffix='.1st_send')
        self.ocomm.suppress_special_debug = False
        self._first_send_done = True
        if not flag:
            self.error("1st send failed.")
        else:
            self.debug("1st send succeded")
        return flag

    def send_eof(self):
        r"""Send EOF message.

        Returns:
            bool: Success or failure of send.

        """
        with self.lock:
            if self._eof_sent:  # pragma: debug
                self.debug('Already sent EOF')
                return False
            self._eof_sent = True
        self.debug('Sent EOF')
        msg = CommBase.CommMessage(flag=CommBase.FLAG_EOF,
                                   args=self.ocomm.eof_msg)
        return self.send_message(msg)

    def send_message(self, msg, **kwargs):
        r"""Send a single message.

        Args:
            msg (CommMessage): Message being sent.
            *kwargs: Keyword arguments are passed to the output comm send method.

        Returns:
            bool: Success or failure of send.

        """
        assert(self.in_process)
        self.debug('')
        with self.lock:
            self._used = True
        kws_prepare = {k: kwargs.pop(k) for k in self.ocomm._prepare_message_kws
                       if k in kwargs}
        msg_out = self.ocomm.prepare_message(msg.args, **kws_prepare)
        if self._first_send_done:
            flag = self._send_message(msg_out, **kwargs)
        else:
            flag = self._send_1st_message(msg_out, **kwargs)
        # if self.single_use:
        #     with self.lock:
        #         self.debug('Used')
        #         self.icomm.drain_messages()
        #         self.icomm.close()
        self.errors += self.ocomm.errors
        return flag

    def set_close_state(self, state):
        r"""Set the close state if its not already set."""
        out = False
        with self.lock:
            if not self.close_state:
                self.debug("Setting close state to %s", state)
                self.close_state = state
                out = True
        return out

    def run_loop(self):
        r"""Run the driver. Continue looping over messages until there are not
        any left or the communication channel is closed.
        """
        self.state = 'in loop'
        # if not self.is_valid:
        if (((self.single_use and self._used)
             or self.check_flag_attr('_comm_closed'))):
            self.debug("Breaking loop")
            self.set_close_state('invalid')
            self.set_break_flag()
            return
        # Receive a message
        self.state = 'receiving'
        msg = self.recv_message()
        if msg is False:
            self.debug('No more messages')
            self.set_break_flag()
            self.set_close_state('receiving')
            return
        if (msg is True) or (isinstance(msg, CommBase.CommMessage)
                             and (msg.flag != CommBase.FLAG_SUCCESS)):
            self.state = 'waiting'
            self.verbose_debug(':run: Waiting for next message.')
            self.sleep()
            return
        self.nrecv += 1
        self.state = 'received'
        if isinstance(msg.args, bytes):
            self.debug('Received message that is %d bytes from %s.',
                       len(msg.args), self.icomm.address)
        elif isinstance(msg.args, np.ndarray):
            self.debug('Received array with shape %s and data type %s from %s',
                       msg.args.shape, msg.args.dtype, self.icomm.address)
        else:
            self.debug('Received message of type %s from %s',
                       type(msg.args), self.icomm.address)
        # Process message
        self.state = 'processing'
        msg = self.on_message(msg)
        if msg is False:  # pragma: debug
            self.error('Could not process message.')
            self.set_break_flag()
            self.set_close_state('processing')
            return
        self.nproc += 1
        self.state = 'processed'
        self.debug('Processed message.')
        # Send a message
        self.state = 'sending'
        ret = self.send_message(msg)
        if ret is False:
            self.error('Could not send message.')
            self.set_break_flag()
            self.set_close_state('sending')
            return
        self.nsent += 1
        self.state = 'sent'
        self.debug('Sent message to %s.', self.ocomm.address)
