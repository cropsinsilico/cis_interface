"""This module provides tools for running models using yggdrasil."""
import sys
import os
import time
import copy
import signal
import traceback
import atexit
from pprint import pformat
from itertools import chain
import socket
from yggdrasil.tools import YggClass
from yggdrasil.config import ygg_cfg, cfg_environment, temp_config
from yggdrasil import platform, yamlfile
from yggdrasil.drivers import create_driver, DuplicatedModelDriver
from yggdrasil.multitasking import MPI


COLOR_TRACE = '\033[30;43;22m'
COLOR_NORMAL = '\033[0m'


class YggFunction(YggClass):
    r"""This class wraps function-like behavior around a model.

    Args:
        model_yaml (str, list): Full path to one or more yaml files containing
            model information including the location of the source code and any
            input(s)/output(s).
        **kwargs: Additional keyword arguments are passed to the YggRunner
            constructor.

    Attributes:
        outputs (dict): Input channels providing access to model output.
        inputs (dict): Output channels providing access to model input.
        runner (YggRunner): Runner for model.

    """
    
    def __init__(self, model_yaml, **kwargs):
        from yggdrasil.languages.Python.YggInterface import (
            YggInput, YggOutput)
        # Create and start runner in another process
        self.runner = YggRunner(model_yaml, as_function=True, **kwargs)
        # Start the drivers
        self.runner.run()
        self.model_driver = self.runner.modeldrivers['function_model']
        for k in self.runner.modeldrivers.keys():
            if k != 'function_model':
                self.__name__ = k
                break
        # Create input/output channels
        self.inputs = {}
        self.outputs = {}
        # import zmq; ctx = zmq.Context()
        for drv in self.model_driver['input_drivers']:
            for env in drv['instance'].model_env.values():
                os.environ.update(env)
            channel_name = drv['instance'].ocomm.name
            var_name = drv['name'].split('function_')[-1]
            self.outputs[var_name] = drv.copy()
            self.outputs[var_name]['vars'] = [
                iv.split(':')[-1] for iv in drv.get('vars', [var_name])]
            self.outputs[var_name]['comm'] = YggInput(
                channel_name, no_suffix=True)
            # context=ctx)
        for drv in self.model_driver['output_drivers']:
            for env in drv['instance'].model_env.values():
                os.environ.update(env)
            channel_name = drv['instance'].icomm.name
            var_name = drv['name'].split('function_')[-1]
            self.inputs[var_name] = drv.copy()
            self.inputs[var_name]['vars'] = [
                iv.split(':')[-1] for iv in drv.get('vars', [var_name])]
            self.inputs[var_name]['comm'] = YggOutput(
                channel_name, no_suffix=True)
            # context=ctx)
        self._stop_called = False
        atexit.register(self.stop)
        # Get arguments
        self.arguments = []
        for k, v in self.inputs.items():
            self.arguments += v['vars']
        self.returns = []
        for k, v in self.outputs.items():
            self.returns += v['vars']

    # def widget_function(self, *args, **kwargs):
    #     # import matplotlib.pyplot as plt
    #     # ncols = min(3, len(arguments))
    #     # nrows = int(ceil(float(len(arguments))/float(ncols)))
    #     # plt.show()
    #     out = self(*args, **kwargs)
    #     return out

    # def widget(self, *args, **kwargs):
    #     from ipywidgets import interact_manual
    #     return interact_manual(self.widget_function, *args, **kwargs)
        
    def __call__(self, **kwargs):
        r"""Call the model as a function by sending variables.

        Args:
           **kwargs: Any keyword arguments are expected to be named input
               variables for the model.

        Raises:
            RuntimeError: If an input argument is missing.
            RuntimeError: If sending an input argument to a model fails.
            RuntimeError: If receiving an output value from a model fails.

        Returns:
            dict: Returned values for each return variable.

        """
        # Check for arguments
        for a in self.arguments:
            if a not in kwargs:  # pragma: debug
                raise RuntimeError("Required argument %s not provided." % a)
        # Send
        for k, v in self.inputs.items():
            flag = v['comm'].send([kwargs[a] for a in v['vars']])
            if not flag:  # pragma: debug
                raise RuntimeError("Failed to send %s" % k)
        # Receive
        out = {}
        for k, v in self.outputs.items():
            flag, data = v['comm'].recv(timeout=60.0)
            if not flag:  # pragma: debug
                raise RuntimeError("Failed to receive variable %s" % v)
            ivars = v['vars']
            if isinstance(data, (list, tuple)):
                assert(len(data) == len(ivars))
                for a, d in zip(ivars, data):
                    out[a] = d
            else:
                assert(len(ivars) == 1)
                out[ivars[0]] = data
        return out

    def stop(self):
        r"""Stop the model(s) from running."""
        if self._stop_called:
            return
        self._stop_called = True
        for x in self.inputs.values():
            x['comm'].send_eof()
            x['comm'].linger_close()
        for x in self.outputs.values():
            x['comm'].close()
        self.model_driver['instance'].terminate()
        self.runner.waitModels(timeout=10)
        for x in self.inputs.values():
            x['comm'].close()
        self.runner.terminate()
        self.runner.atexit()


class YggRunner(YggClass):
    r"""This class handles the orchestration of starting the model and
    IO drivers, monitoring their progress, and cleaning up on exit.

    Arguments:
        modelYmls (list): List of paths to yaml files specifying the models
            that should be run.
        namespace (str, optional): Name that should be used to uniquely
            identify any RMQ exchange. Defaults to the value in the config
            file.
        host (str, optional): Name of the host that the models will be launched
            from. Defaults to None.
        rank (int, optional): Rank of this set of models if run in parallel.
            Defaults to 0.
        ygg_debug_level (str, optional): Level for Ygg debug messages. Defaults
            to environment variable 'YGG_DEBUG'.
        rmq_debug_level (str, optional): Level for RabbitMQ debug messages.
            Defaults to environment variable 'RMQ_DEBUG'.
        ygg_debug_prefix (str, optional): Prefix for Ygg debug messages.
            Defaults to namespace.
        as_function (bool, optional): If True, the missing input/output channels
            will be created for using model(s) as a function. Defaults to False.

    Attributes:
        namespace (str): Name that should be used to uniquely identify any RMQ
            exchange.
        host (str): Name of the host that the models will be launched from.
        rank (int): Rank of this set of models if run in parallel.
        modeldrivers (dict): Model drivers associated with this run.
        connectiondrivers (dict): Connection drivers for this run.
        interrupt_time (float): Time of last interrupt signal.
        error_flag (bool): True if one or more models raises an error.

    ..todo:: namespace, host, and rank do not seem strictly necessary.

    """
    def __init__(self, modelYmls, namespace=None, host=None, rank=0,
                 ygg_debug_level=None, rmq_debug_level=None,
                 ygg_debug_prefix=None, connection_task_method='thread',
                 as_function=False, production_run=False):
        self.mpi_comm = None
        name = 'runner'
        if MPI is not None:
            comm = MPI.COMM_WORLD
            if comm.Get_size() > 1:
                self.mpi_comm = comm
                rank = comm.Get_rank()
                name += str(rank)
        super(YggRunner, self).__init__(name)
        if namespace is None:
            namespace = ygg_cfg.get('rmq', 'namespace', False)
        if not namespace:  # pragma: debug
            raise Exception('rmq:namespace not set in config file')
        self.namespace = namespace
        self.host = host
        self.rank = rank
        self.connection_task_method = connection_task_method
        self.modeldrivers = {}
        self.connectiondrivers = {}
        self.interrupt_time = 0
        self._old_handlers = {}
        self.production_run = production_run
        self.error_flag = False
        self.as_function = as_function
        self.debug("Running in %s with path %s namespace %s rank %d",
                   os.getcwd(), sys.path, namespace, rank)
        # Update environment based on config
        cfg_environment()
        # Parse yamls
        if self.mpi_comm and (self.rank > 0):
            pass
        else:
            self.drivers = yamlfile.parse_yaml(modelYmls, as_function=as_function)
            self.connectiondrivers = self.drivers['connection']
            self.modeldrivers = self.drivers['model']

    def pprint(self, *args):
        r"""Print with color."""
        s = ''.join(str(i) for i in args)
        print((COLOR_TRACE + '{}' + COLOR_NORMAL).format(s))

    def atexit(self, *args, **kwargs):
        r"""At exit ensure that the runner has stopped and cleaned up."""
        self.debug('')
        self.reset_signal_handler()
        self.closeChannels()
        self.cleanup()

    def signal_handler(self, sig, frame):
        r"""Terminate all drivers on interrrupt."""
        self.debug("Interrupt with signal %d", sig)
        now = time.perf_counter()
        elapsed = now - self.interrupt_time
        self.debug('Elapsed time since last interrupt: %d s', elapsed)
        self.interrupt_time = now
        self.pprint(' ')
        self.pprint(80 * '*')
        if elapsed < 5:
            self.pprint('* %76s *' % 'Interrupted twice within 5 seconds: shutting down')
            self.pprint(80 * '*')
            self.debug("Terminating models and closing all channels")
            self.terminate()
            self.pprint(80 * '*')
            return 1
        else:
            self.pprint('* %76s *' % 'Interrupted: Displaying channel summary')
            self.pprint('* %76s *' % 'interrupt again (within 5 seconds) to exit')
            self.pprint(80 * '*')
            self.printStatus()
            self.pprint(80 * '*')
        self.debug('%d returns', sig)

    def _swap_handler(self, signum, signal_handler):
        self._old_handlers[signum] = signal.getsignal(signum)
        signal.signal(signum, signal_handler)
        if not platform._is_win:
            signal.siginterrupt(signum, False)
        
    def set_signal_handler(self, signal_handler=None):
        r"""Set the signal handler.

        Args:
            signal_handler (function, optional): Function that should handle
                received SIGINT and SIGTERM signals. Defaults to
                self.signal_handler.

        """
        if signal_handler is None:
            signal_handler = self.signal_handler
        self._swap_handler(signal.SIGINT, signal_handler)
        if not platform._is_win:
            self._swap_handler(signal.SIGTERM, signal_handler)
        else:  # pragma: windows
            self._swap_handler(signal.SIGBREAK, signal_handler)

    def reset_signal_handler(self):
        r"""Reset signal handlers to old ones."""
        for k, v in self._old_handlers.items():
            signal.signal(k, v)

    def run(self, signal_handler=None, timer=None, t0=None):
        r"""Run all of the models and wait for them to exit.

        Args:
            signal_handler (function, optional): Function that should be used as
                a signal handler. Defaults to None and is set by
                set_signal_handler.
            timer (function, optional): Function that should be called to get
                intermediate timing statistics. Defaults to time.time if not
                provided.
            t0 (float, optional): Zero point for timing statistics. Is set
                using the provided timer if not provided.

        Returns:
            dict: Intermediate times from the run.

        """
        with temp_config(production_run=self.production_run):
            if timer is None:
                timer = time.time
            if t0 is None:
                t0 = timer()
            times = {}
            times['init'] = timer()
            self.loadDrivers()
            times['load drivers'] = timer()
            self.startDrivers()
            times['start drivers'] = timer()
            self.set_signal_handler(signal_handler)
            if not self.as_function:
                self.waitModels()
                times['run models'] = timer()
                self.atexit()
                times['at exit'] = timer()
            tprev = t0
            key_order = ['init', 'load drivers', 'start drivers', 'run models',
                         'at exit']
            for k in key_order:
                if k in times:
                    self.info('%20s\t%f', k, times[k] - tprev)
                    tprev = times[k]
            self.info(40 * '=')
            self.info('%20s\t%f', "Total", tprev - t0)
        return times

    @property
    def all_drivers(self):
        r"""iterator: For all drivers."""
        return chain(self.connectiondrivers.values(),
                     self.modeldrivers.values())

    def io_drivers(self):
        r"""Return the input and output drivers for all models.

        Returns:
            iterator: Access to list of I/O drivers.

        """
        return self.connectiondrivers.values()

    def create_driver(self, yml):
        r"""Create a driver instance from the yaml information.

        Args:
            yml (yaml): Yaml object containing driver information.

        Returns:
            object: An instance of the specified driver.

        """
        self.debug('Creating %s, a %s', yml['name'], yml['driver'])
        curpath = os.getcwd()
        if 'working_dir' in yml:
            os.chdir(yml['working_dir'])
        try:
            if yml.get('copies', 1) > 1:
                instance = DuplicatedModelDriver.DuplicatedModelDriver(
                    yml, namespace=self.namespace, rank=self.rank)
            else:
                instance = create_driver(yml=yml, namespace=self.namespace,
                                         rank=self.rank, **yml)
            yml['instance'] = instance
        finally:
            os.chdir(curpath)
        return instance

    def createModelDriver(self, yml):
        r"""Create a model driver instance from the yaml information.

        Args:
            yml (yaml): Yaml object containing driver information.

        Returns:
            object: An instance of the specified driver.

        """
        drv = self.create_driver(yml)
        self.debug("Model %s:, env: %s",
                   yml['name'], pformat(yml['instance'].env))
        return drv

    def create_connection_driver(self, yml):
        r"""Create a connection driver instance from the yaml information.

        Args:
            yml (yaml): Yaml object containing driver information.

        Returns:
            object: An instance of the specified driver.

        """
        yml['task_method'] = self.connection_task_method
        drv = self.create_driver(yml)
        # Transfer connection addresses to model via env
        # TODO: Change to server that tracks connections
        for model, env in drv.model_env.items():
            try:
                self.modeldrivers[model].setdefault('env', {})
                self.modeldrivers[model]['env'].update(env)
            except KeyError:
                model0 = model.split('_copy')[0]
                if (((model0 in self.modeldrivers)
                     and (self.modeldrivers[model0].get('copies', 0) > 1))):
                    self.modeldrivers[model0].setdefault('env_%s' % model, {})
                    self.modeldrivers[model0]['env_%s' % model].update(env)
                else:  # pragma: debug
                    raise
        return drv
        
    def loadDrivers(self):
        r"""Load all of the necessary drivers, doing the IO drivers first
        and adding IO driver environmental variables back tot he models."""
        self.debug('')
        driver = dict(name='name')
        try:
            # Create connection drivers
            self.debug("Loading connection drivers")
            for driver in self.connectiondrivers.values():
                self.create_connection_driver(driver)
            # Distribute tasks
            if self.mpi_comm:
                if self.rank == 0:
                    self.all_modeldrivers = self.modeldrivers
                    size = self.mpi_comm.Get_size()
                    models = [[] for _ in range(size)]
                    for i, (k, v) in enumerate(self.modeldrivers.items()):
                        x_cp = copy.deepcopy(v)
                        for k2 in ['input_drivers', 'output_drivers']:
                            x_cp.pop(k2, None)
                        # Skew models away from root process so that
                        # connection threading might not share process
                        models[(i) % size].append((k, x_cp))
                    max_len = len(max(models, key=len))
                    for x in models:
                        while len(x) < max_len:
                            x.append(None)
                else:
                    models = None
                self.modeldrivers = dict(
                    [x for x in self.mpi_comm.scatter(models, root=0)
                     if (x is not None)])
                if self.rank == 0:
                    for i, (k, v) in enumerate(self.all_modeldrivers.items()):
                        if k not in self.modeldrivers:
                            v['language'] = 'mpi'
                            v['driver'] = 'MPIPartnerModel'
                            v['mpi_rank'] = i
                        self.modeldrivers[k] = v
            # Create model drivers
            self.debug("Loading model drivers")
            for driver in self.modeldrivers.values():
                self.createModelDriver(driver)
        except BaseException:  # pragma: debug
            self.error("%s could not be created.", driver['name'])
            self.terminate()
            raise

    def startDrivers(self):
        r"""Start drivers, starting with the IO drivers."""
        self.info('Starting I/O drivers and models on system '
                  + '{} in namespace {} with rank {}'.format(
                      self.host, self.namespace, self.rank))
        driver = dict(name='name')
        try:
            # Start connections
            for driver in self.io_drivers():
                self.debug("Starting driver %s", driver['name'])
                d = driver['instance']
                if not d.was_started:
                    d.start()
            # Ensure connections in loop
            for driver in self.io_drivers():
                self.debug("Checking driver %s", driver['name'])
                d = driver['instance']
                d.wait_for_loop()
                assert(d.was_loop)
                assert(not d.errors)
            # Start models
            for driver in self.modeldrivers.values():
                self.debug("Starting driver %s", driver['name'])
                d = driver['instance']
                # TODO: Need way to start client remotely
                for n2 in driver.get('client_of', []):
                    if self.mpi_comm:
                        raise NotImplementedError("Start client remotely")
                    d2 = self.modeldrivers[n2]['instance']
                    if not d2.was_started:
                        self.debug("Starting server '%s' before client", d2.name)
                        d2.start()
                if not d.was_started:
                    d.start()
        except BaseException:  # pragma: debug
            self.error("%s did not start", driver['name'])
            self.terminate()
            raise
        self.debug('ALL DRIVERS STARTED')

    def waitModels(self, timeout=False):
        r"""Wait for all model drivers to finish. When a model finishes,
        join the thread and perform exits for associated IO drivers."""
        self.debug('')
        running = [d for d in self.modeldrivers.values()]
        dead = []
        Tout = self.start_timeout(t=timeout,
                                  key_suffix='.waitModels')
        while ((len(running) > 0) and (not self.error_flag)
               and (not Tout.is_out)):
            for drv in running:
                d = drv['instance']
                if d.errors:  # pragma: debug
                    self.error('Error in model %s', drv['name'])
                    self.error_flag = True
                    break
                elif d.io_errors:  # pragma: debug
                    self.error('Error in input/output driver for model %s'
                               % drv['name'])
                    self.error_flag = True
                    break
                d.join(1)
                if not d.is_alive():
                    if not d.errors:
                        self.info("%s finished running.", drv['name'])
                        # self.do_model_exits(drv)
                        # self.debug("%s completed model exits.", drv['name'])
                        self.do_client_exits(drv)
                        self.debug("%s completed client exits.", drv['name'])
                        running.remove(drv)
                        self.info("%s finished exiting.", drv['name'])
                else:
                    self.debug('%s still running', drv['name'])
            dead = []
            for drv in self.all_drivers:
                d = drv['instance']
                d.join(0.1)
                if not d.is_alive():
                    dead.append(drv['name'])
        self.stop_timeout(key_suffix='.waitModels')
        for d in self.modeldrivers.values():
            if d['instance'].errors:
                self.error_flag = True
        if not self.error_flag:
            self.info('All models completed')
        else:
            self.error('One or more models generated errors.')
            self.printStatus()
            self.terminate()
        self.debug('Returning')

    # def do_model_exits(self, model):
    #     r"""Perform exits for IO drivers associated with a model.

    #     Args:
    #         model (dict): Dictionary of model parameters including any
    #             associated IO drivers.

    #     """
    #     for drv in model['input_drivers']:
    #         #  if model['name'] in drv['models']:
    #         #     drv['models'].remove(model['name'])
    #         if not drv['instance'].is_alive():
    #             continue
    #         # if (len(drv['models']) == 0):
    #         self.debug('on_model_exit %s', drv['name'])
    #         drv['instance'].on_model_exit('output', model['name'])
    #     for drv in model['output_drivers']:
    #         # if model['name'] in drv['models']:
    #         #     drv['models'].remove(model['name'])
    #         if not drv['instance'].is_alive():
    #             continue
    #         # if (len(drv['models']) == 0):
    #         self.debug('on_model_exit %s', drv['name'])
    #         drv['instance'].on_model_exit('input', model['name'])
    
    def do_client_exits(self, model):
        r"""Perform exits for IO drivers associated with a client model.

        Args:
            model (dict): Dictionary of model parameters including any
                associated IO drivers.

        """
        # TODO: Exit upstream models that no longer have any open
        # output, connections when a connection is closed.
        for srv_name in model.get('client_of', []):
            iod = self.connectiondrivers[srv_name]
            iod['instance'].remove_model('input', model['name'])
            if iod['instance'].nclients == 0:
                srv = self.modeldrivers[srv_name]
                srv['instance'].stop()

    def terminate(self):
        r"""Immediately stop all drivers, beginning with IO drivers."""
        self.debug('')
        for driver in self.all_drivers:
            if 'instance' in driver:
                self.debug('Stop %s', driver['name'])
                driver['instance'].terminate()
                # Terminate should ensure instance not alive
                assert(not driver['instance'].is_alive())
        self.debug('Returning')

    def cleanup(self):
        r"""Perform cleanup operations for all drivers."""
        self.debug('')
        for driver in self.all_drivers:
            if 'instance' in driver:
                driver['instance'].cleanup()
        # self.inputdrivers = {}
        # self.outputdrivers = {}
        # self.modeldrivers = {}

    def printStatus(self):
        r"""Print the status of all drivers, starting with the IO drivers."""
        self.debug('')
        for driver in self.all_drivers:
            if 'instance' in driver:
                driver['instance'].printStatus()

    def closeChannels(self, force_stop=False):
        r"""Stop IO drivers and join the threads.

        Args:
            force_stop (bool, optional): If True, the terminate method is
                used to stop the drivers. Otherwise, the stop method is used.
                The stop method will try to exit gracefully while terminate
                will exit as quickly as possible. Defaults to False.

        """
        self.debug('')
        drivers = [i for i in self.io_drivers()]
        for drv in drivers:
            if 'instance' in drv:
                driver = drv['instance']
                if driver.is_alive():  # pragma: debug
                    self.debug("Stopping %s", drv['name'])
                    if force_stop or self.error_flag:
                        driver.terminate()
                    else:
                        driver.stop()
                    self.debug("Stop(%s) returns", drv['name'])
        self.debug('Channel Stops DONE')
        for drv in drivers:
            if 'instance' in drv:
                driver = drv['instance']
                assert(not driver.is_alive())
        self.debug('Returning')

        
def get_runner(models, **kwargs):
    r"""Get runner for a set of models, getting run information from the
    environment.

    Args:
        models (list): List of yaml files containing information on the models
            that should be run.
        **kwargs: Additonal keyword arguments are passed to YggRunner.

    Returns:
        YggRunner: Runner for the provided models.

    Raises:
        Exception: If config option 'namespace' in 'rmq' section not set.

    """
    # Get environment variables
    rank = os.environ.get('PARALLEL_SEQ', '0')
    host = socket.gethostname()
    os.environ['YGG_RANK'] = rank
    os.environ['YGG_HOST'] = host
    rank = int(rank)
    kwargs.update(rank=rank, host=host)
    # Run
    yggRunner = YggRunner(models, **kwargs)
    return yggRunner


def run(*args, **kwargs):
    yggRunner = get_runner(*args, **kwargs)
    try:
        yggRunner.run()
        yggRunner.debug("runner returns, exiting")
    except Exception as ex:  # pragma: debug
        yggRunner.pprint("yggrun exception: %s" % type(ex))
        print(traceback.format_exc())
    print('')
