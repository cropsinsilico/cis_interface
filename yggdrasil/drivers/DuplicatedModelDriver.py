import copy
from yggdrasil.drivers import create_driver
from yggdrasil.drivers.Driver import Driver
        

class DuplicatedModelDriver(Driver):
    r"""Base class for Model drivers and for running executable based models.

    Args:
        name (str): Unique name used to identify the model. This will
            be used to report errors associated with the model.
        *args: Additional arguments are passed to the models in the set.
        **kwargs: Additional keyword arguments are passed to the models in
            the set.

    Attributes:

    Raises:
        RuntimeError: If both with_strace and with_valgrind are True.

    """

    name_format = "%s_copy%d"

    def __init__(self, yml, **kwargs):
        kwargs.update(yml)
        self.copies = []
        for iyml in self.get_yaml_copies(yml):
            ikws = copy.deepcopy(kwargs)
            ikws.update(iyml)
            self.copies.append(create_driver(yml=iyml, **ikws))
        super(DuplicatedModelDriver, self).__init__(**kwargs)

    @classmethod
    def get_yaml_copies(cls, yml):
        env_copy_specific = {}
        for i in range(yml['copies']):
            iname = cls.name_format % (yml['name'], i)
            env_copy_specific[iname] = yml.pop('env_%s' % iname, {})
        copies = []
        for i in range(yml['copies']):
            iyml = copy.deepcopy(yml)
            iyml['name'] = cls.name_format % (yml['name'], i)
            iyml['copy_index'] = i
            # Update environment to reflect addition of suffix
            iyml['env'] = yml['env'].copy()
            iyml['env'].update(env_copy_specific.get(iyml['name'], {}))
            copies.append(iyml)
        return copies

    def cleanup(self, *args, **kwargs):
        r"""Actions to perform to clean up the thread after it has stopped."""
        for x in self.copies:
            x.cleanup(*args, **kwargs)
        super(DuplicatedModelDriver, self).cleanup(*args, **kwargs)

    def start(self, *args, **kwargs):
        r"""Start thread/process and print info."""
        for x in self.copies:
            x.start(*args, **kwargs)
        super(DuplicatedModelDriver, self).start(*args, **kwargs)

    def stop(self, *args, **kwargs):
        r"""Stop the driver."""
        for x in self.copies:
            x.stop(*args, **kwargs)
        super(DuplicatedModelDriver, self).stop(*args, **kwargs)
        
    def graceful_stop(self, *args, **kwargs):
        r"""Gracefully stop the driver."""
        for x in self.copies:
            x.graceful_stop(*args, **kwargs)
        super(DuplicatedModelDriver, self).graceful_stop(*args, **kwargs)
        
    def terminate(self, *args, **kwargs):
        r"""Set the terminate event and wait for the thread/process to stop."""
        for x in self.copies:
            x.terminate(*args, **kwargs)
        super(DuplicatedModelDriver, self).terminate(*args, **kwargs)
        
    def run_loop(self):
        r"""Loop to check if model is still running and forward output."""
        # TODO: Stop if there is an error on one?
        if any([x.is_alive() for x in self.copies]):
            self.sleep()
            return
        else:
            self.set_break_flag()

    def after_loop(self, *args, **kwargs):
        r"""Actions to perform after run_loop has finished."""
        for x in self.copies:
            x.terminate()
        super(DuplicatedModelDriver, self).after_loop(*args, **kwargs)

    def printStatus(self, *args, **kwargs):
        r"""Print the class status."""
        for x in self.copies:
            x.printStatus(*args, **kwargs)
        super(DuplicatedModelDriver, self).printStatus(*args, **kwargs)

    @property
    def io_errors(self):
        r"""list: Errors produced by input/output drivers to this model."""
        errors = []
        for x in self.copies:
            errors += x.io_errors
        return errors
        
    @property
    def errors(self):
        r"""list: Errors returned by model copies."""
        out = []
        for x in self.copies:
            out += x.errors
        return out

    @errors.setter
    def errors(self, val):
        pass
