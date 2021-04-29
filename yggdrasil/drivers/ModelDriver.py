import os
import re
import sys
import copy
import logging
import warnings
import subprocess
import shutil
import uuid
import tempfile
from collections import OrderedDict
from pprint import pformat
from yggdrasil import platform, tools, languages, multitasking
from yggdrasil.components import import_component, import_all_components
from yggdrasil.drivers.Driver import Driver
from yggdrasil.metaschema.datatypes import is_default_typedef
from yggdrasil.metaschema.properties.ScalarMetaschemaProperties import (
    _valid_types)
from queue import Empty
logger = logging.getLogger(__name__)


_map_language_ext = OrderedDict()


def remove_product(product, check_for_source=False, **kwargs):
    r"""Delete a single product after checking that the product is not (or
    does not contain, in the case of directories), source files.

    Args:
        product (str): Full path to a file or directory that should be
            removed.
        check_for_source (bool, optional): If True, the specified product
            will be checked to ensure that no source files are present. If
            a source file is present, a RuntimeError will be raised.
            Defaults to False.
        **kwargs: Additional keyword arguments are passed to tools.remove_path.

    Raises:
        RuntimeError: If the specified product is a source file and
            check_for_source is False.
        RuntimeError: If the specified product is a directory that contains
            a source file and check_for_source is False.
        RuntimeError: If the product cannot be removed.

    """
    import_all_components('model')
    source_keys = list(_map_language_ext.keys())
    if '.exe' in source_keys:  # pragma: windows
        source_keys.remove('.exe')
    if check_for_source:
        if os.path.isdir(product):
            ext_tuple = tuple(source_keys)
            for root, dirs, files in os.walk(product):
                for f in files:
                    if f.endswith(ext_tuple):
                        raise RuntimeError(("%s contains a source file "
                                            "(%s)") % (product, f))
        elif os.path.isfile(product):
            ext = os.path.splitext(product)[-1]
            if ext in source_keys:
                raise RuntimeError("%s is a source file." % product)
    tools.remove_path(product, **kwargs)
        

def remove_products(products, source_products, timer_class=None):
    r"""Delete products produced during the process of running the model.

    Args:
        products (list): List of products that should be removed after
            checking that they are not source files.
        source_products (list): List of products that should be removed
            without checking that they are not source files.

    """
    for p in source_products:
        remove_product(p, timer_class=timer_class)
    for p in products:
        remove_product(p, timer_class=timer_class, check_for_source=True)


class ModelDriver(Driver):
    r"""Base class for Model drivers and for running executable based models.

    Args:
        name (str): Unique name used to identify the model. This will
            be used to report errors associated with the model.
        args (str or list): The full path to the file containing the
            model program that will be run by the driver or a list
            starting with the program file and including any arguments
            that should be passed as input to the program.
        products (list, optional): Paths to files created by the model that
            should be cleaned up when the model exits. Entries can be absolute
            paths or paths relative to the working directory. Defaults to [].
        function (str, optional): If provided, an integrated model is
            created by wrapping the function named here. The function must be
            located within the file specified by the source file listed in the
            first argument. If not provided, the model must contain it's own
            calls to the |yggdrasil| interface.
        source_products (list, optional): Files created by running the model
            that are source files. These files will be removed without checking
            their extension so users should avoid adding files to this list
            unless they are sure they should be deleted. Defaults to [].
        is_server (bool, dict, optional): If `True`, the model is assumed to be a
            server for one or more client models and an instance of
            :class:`yggdrasil.drivers.ServerDriver` is started. The
            corresponding channel that should be passed to the yggdrasil API
            will be the name of the model. If is_server is a dictionary, it
            should contain an 'input' key and an 'output' key. These are
            required to be the names of existing input and output channels in
            the model that will be co-opted by the server. (Note: This requires
            that the co-opted output channel's send method is called once for
            each time the co-opted input channel's recv method is called. If
            used with the `function` parameter, `is_server` must be a dictionary.
            Defaults to False.
        client_of (str, list, optional): The names of one or more models that
            this model will call as a server. If there are more than one, this
            should be specified as a sequence collection (list). The
            corresponding channel(s) that should be passed to the yggdrasil API
            will be the name of the server model joined with the name of the
            client model with an underscore `<server_model>_<client_model>`.
            There will be one channel created for each server the model is a
            client of. Defaults to empty list. Use of `client_of` with `function`
            is not currently supported.
        timesync (bool, str, optional): If set, the model is assumed to
            call a send then receive of the state at each timestep
            for syncronization with other models that are also
            integrating in time. If a string is provided, it is assumed
            to be the name of the server that will handle timestep
            synchronization. If a boolean is provided, the name of the
            server will be assumed to be 'timestep'. Defaults to False.
        overwrite (bool, optional): If True, any existing model products
            (compilation products, wrapper scripts, etc.) are removed prior to
            the run. If False, the products are not removed. Defaults to True.
            Setting this to False can improve the performance, particularly for
            models that take a long time to compile, but this should only be
            done once the model has been fully debugged to ensure that each run
            is tested on a clean copy of the model. The value of this keyword
            also determines whether or not products are removed after a run.
        preserve_cache (bool, optional): If True model products will be kept
            following the run, otherwise all products will be cleaned up.
            Defaults to False. This keyword is superceeded by overwrite.
        with_strace (bool, optional): If True, the command is run with strace (on
            Linux) or dtrace (on MacOS). Defaults to False.
        strace_flags (list, optional): Flags to pass to strace (or dtrace).
            Defaults to [].
        with_valgrind (bool, optional): If True, the command is run with valgrind.
            Defaults to False.
        valgrind_flags (list, optional): Flags to pass to valgrind. Defaults to [].
        model_index (int, optional): Index of model in list of models being run.
            Defaults to 0.
        copy_index (int, optional): Index of model in set of copies. Defaults
            to -1 indicating there is only one copy of the model.
        outputs_in_inputs (bool, optional): If True, outputs from wrapped model
            functions are passed by pointer as inputs for modification and the
            return value will be a flag. If False, outputs are limited to
            return values. Defaults to the value of the class attribute
            outputs_in_inputs.
        logging_level (str, optional): The level of logging messages that should
            be displayed by the model. Defaults to the logging level as
            determined by the configuration file and environment variables.
        allow_threading (bool, optional): If True, comm connections will be set up
            so that the model-side comms can be used by more than one thread.
            Defaults to False.
        copies (int, optional): The number of copies of the model that should be
            created. Defaults to 1.
        **kwargs: Additional keyword arguments are passed to parent class.

    Class Attributes:
        language (str): Primary name for the programming language that this
            compiler should be used for. [REQUIRED]
        language_aliases (list): Additional/alternative names that the language
            may be known by.
        language_ext (list): Extensions for programs written in the target
            language. [REQUIRED]
        base_languages (list): Other programming languages that this driver
            and the interpreter for the target language are dependent on (e.g.
            Matlab models require Python).
        executable_type (str): 'compiler' or 'interpreter' to indicate the type
            of the executable for the language. [AUTOMATED]
        interface_library (list): Name of the library containing the yggdrasil
            interface for the target language. [REQUIRED]
        interface_directories (list): Directories containing code in the
            interface library for the target language.
        interface_dependencies (list): List of names of libraries that are
            required to use the interface on the current platform. This dosn't
            include libraries required by specific communication types which are
            described by supported_comm_options.
        supported_comms (list): Name of comms supported in the target language.
            [REQUIRED]
        supported_comm_options (dict): Options for the supported comms like the
            platforms they are available on and the external libraries required
            to use them. [REQUIRED]
        external_libraries (dict): Information on external libraries required
            for running models in the target language using yggdrasil.
        internal_libraries (dict): Information on internal libraries required
            for running models in the target language using yggdrasil.
        type_map (dict): Mapping of |yggdrasil| extended JSON types to
            datatypes in the target programming language. [REQUIRED]
        function_param (dict): Options specifying how different operations
            would be encoded in the target language (e.g. if statements, for
            loops, while loops). [REQUIRED]
        version_flags (list): Flags that should be called with the language
            executable to determine the version of the compiler/interpreter.
            Defaults to ['--version'].
        outputs_in_inputs (bool): If True, outputs are passed by pointer as
            inputs for modification and the return value should be a flag.
            Defaults to False.
        include_arg_count (bool): If True, the number of arguments passed
            to send/recv calls is prepended to the arguments to the function.
            Defaults to False.
        include_channel_obj (bool): If True, the channel object is passed as
            input to the send/recv calls (after the argument count if it is
            also present due to include_arg_count being True). Defaults to
            False.
        is_typed (bool): True if the language is typed, False otherwise.
        brackets (tuple): A pair of opening and clossing characters that
            are used by the language to mark blocks. Set to None and
            ignored by default.
        no_executable (bool): True if there is not an executable associated
            with the language driver. Defaults to False.
        comms_implicit (bool): True if the comms installed for this driver
            are not explicitly defined (depend on input parameters). Defaults
            to False.

    Attributes:
        args (list): Argument(s) for running the model on the command line.
        model_file (str): Full path to the model executable or interpretable
            script.
        model_args (list): Runtime arguments for running the model on the
            command line.
        model_src (str): Full path to the model source code. For interpreted
            languages, this will be the same as model_file.
        model_function_info (dict): Parameters recovered by parsing the
            provided model function definition.
        overwrite (bool): If True, any existing compilation products will be
            overwritten by compilation and cleaned up following the run.
            Otherwise, existing products will be used and will remain after
            the run.
        products (list): Files created by running the model. This includes
            compilation products such as executables and/or object files.
        source_products (list): Files created by running the model that
            are source files. These files will be removed without checking
            their extension so users should avoid adding files to this list
            unless they are sure they should be deleted.
        wrapper_products (list): Files created in order to wrap the model.
        process (:class:`yggdrasil.tools.YggPopen`): Process used to run
            the model.
        function (str): The name of the model function that should be wrapped.
        is_server (bool, dict): If True, the model is assumed to be a server
            and an instance of :class:`yggdrasil.drivers.ServerDriver` is
            started. If a dict, the input/output channels with the specified
            names in the dict will be replaced with a server.
        client_of (list): The names of server models that this model is a
            client of.
        timesync (str): If set, the name of the server performing
            timestep synchronization for the model.
        with_strace (bool): If True, the command is run with strace or dtrace.
        strace_flags (list): Flags to pass to strace/dtrace.
        with_valgrind (bool): If True, the command is run with valgrind.
        valgrind_flags (list): Flags to pass to valgrind.
        model_index (int): Index of model in list of models being run.
        copy_index (int): Index of model in set of copies.
        modified_files (list): List of pairs of originals and copies of files
            that should be restored during cleanup.
        allow_threading (bool): If True, comm connections will be set up so that
            the model-side comms can be used by more than one thread.
        copies (int): The number of copies of the model that should be created.

    Raises:
        RuntimeError: If both with_strace and with_valgrind are True.

    """

    _schema_type = 'model'
    _schema_subtype_key = 'language'
    _schema_required = ['name', 'language', 'args', 'working_dir']
    _schema_properties = {
        'name': {'type': 'string'},
        'language': {'type': 'string', 'default': 'executable',
                     'description': (
                         'The programming language that the model '
                         'is written in. A list of available '
                         'languages can be found :ref:`here <'
                         'schema_table_model_subtype_rst>`.')},
        'args': {'type': 'array',
                 'items': {'type': 'string'}},
        'inputs': {'type': 'array', 'default': [],
                   'items': {'$ref': '#/definitions/comm'},
                   'description': (
                       'A mapping object containing the entry for a '
                       'model input channel or a list of input '
                       'channel entries. If the model does not get '
                       'input from another model, this may be '
                       'ommitted. A full description of channel '
                       'entries and the options available for '
                       'channels can be found :ref:`here<'
                       'yaml_comm_options>`.')},
        'outputs': {'type': 'array', 'default': [],
                    'items': {'$ref': '#/definitions/comm'},
                    'description': (
                        'A mapping object containing the entry for a '
                        'model output channel or a list of output '
                        'channel entries. If the model does not '
                        'output to another model, this may be '
                        'ommitted. A full description of channel '
                        'entries and the options available for '
                        'channels can be found :ref:`here<'
                        'yaml_comm_options>`.')},
        'env': {'type': 'object', 'default': {},
                'additional_properties': {'type': 'string'}},
        'products': {'type': 'array', 'default': [],
                     'items': {'type': 'string'}},
        'source_products': {'type': 'array', 'default': [],
                            'items': {'type': 'string'}},
        'working_dir': {'type': 'string'},
        'overwrite': {'type': 'boolean'},
        'preserve_cache': {'type': 'boolean', 'default': False},
        'function': {'type': 'string'},
        'is_server': {'anyOf': [{'type': 'boolean'},
                                {'type': 'object',
                                 'properties': {'input': {'type': 'string'},
                                                'output': {'type': 'string'}},
                                 'additionalProperties': False}],
                      'default': False},
        'client_of': {'type': 'array', 'items': {'type': 'string'},
                      'default': []},
        'timesync': {
            'anyOf': [
                {'type': 'boolean'}, {'type': 'string'},
                {'type': 'object',
                 'required': ['name'],
                 'properties': {
                     'name': {'type': 'string', 'default': 'timesync'},
                     'inputs': {'anyOf': [
                         {'type': 'string'},
                         {'type': 'array',
                          'items': {'type': 'string'}}]},
                     'outputs': {'anyOf': [
                         {'type': 'string'},
                         {'type': 'array',
                          'items': {'type': 'string'}}]}}},
                {'type': 'array',
                 'items': {
                     'anyOf': [
                         {'type': 'string'},
                         {'type': 'object',
                          'required': ['name'],
                          'properties': {
                              'name': {'type': 'string',
                                       'default': 'timesync'},
                              'inputs': {'anyOf': [
                                  {'type': 'string'},
                                  {'type': 'array',
                                   'items': {'type': 'string'}}]},
                              'outputs': {'anyOf': [
                                  {'type': 'string'},
                                  {'type': 'array',
                                   'items': {'type': 'string'}}]}}}]}}],
            'default': False},
        'with_strace': {'type': 'boolean', 'default': False},
        'strace_flags': {'type': 'array',
                         'default': ['-e', 'trace=memory'],
                         'items': {'type': 'string'}},
        'with_valgrind': {'type': 'boolean', 'default': False},
        'valgrind_flags': {'type': 'array',
                           'default': ['--leak-check=full',
                                       '--show-leak-kinds=all'],  # '-v'
                           'items': {'type': 'string'}},
        'outputs_in_inputs': {'type': 'boolean'},
        'logging_level': {'type': 'string', 'default': ''},
        'allow_threading': {'type': 'boolean'},
        'copies': {'type': 'integer', 'default': 1, 'minimum': 1}}
    _schema_excluded_from_class = ['name', 'language', 'args', 'working_dir']
    _schema_excluded_from_class_validation = ['inputs', 'outputs']
    
    language = None
    language_ext = None
    language_aliases = []
    base_languages = []
    executable_type = None
    interface_library = None
    interface_directories = []
    interface_dependencies = []
    supported_comms = []
    supported_comm_options = {}
    external_libraries = {}
    internal_libraries = {}
    type_map = None
    inverse_type_map = None
    function_param = None
    version_flags = ['--version']
    full_language = True
    outputs_in_inputs = False
    include_arg_count = False
    include_channel_obj = False
    is_typed = False
    types_in_funcdef = True
    interface_inside_exec = False
    dont_declare_channel = False
    is_dsl = False
    brackets = None
    zero_based = True
    max_line_width = None
    no_executable = False
    comms_implicit = False
    python_interface = {'table_input': 'YggAsciiTableInput',
                        'table_output': 'YggAsciiTableOutput',
                        'array_input': 'YggArrayInput',
                        'array_output': 'YggArrayOutput',
                        'pandas_input': 'YggPandasInput',
                        'pandas_output': 'YggPandasOutput'}
    _library_cache = {}
    _config_keys = []
    _config_attr_map = []
    _executable_search_dirs = None
    _disconnect_attr = (Driver._disconnect_attr
                        + ['queue', 'queue_thread',
                           'event_process_kill_called',
                           'event_process_kill_complete'])
    _mpi_tags = {'START': 1,
                 'STOP_RANK0': 2,  # Stopped by partner
                 'STOP_RANKX': 3,  # Stopped by root
                 'CMAKE_FILE': 4,
                 'CMAKE_COMPILED': 5}

    def __init__(self, name, args, model_index=0, copy_index=-1, clients=[],
                 mpi_rank=0, **kwargs):
        self.model_outputs_in_inputs = kwargs.pop('outputs_in_inputs', None)
        super(ModelDriver, self).__init__(name, **kwargs)
        if self.overwrite is None:
            self.overwrite = (not self.preserve_cache)
        # Setup process things
        self.model_process = None
        self.queue = multitasking.Queue()
        self.queue_thread = None
        self.event_process_kill_called = multitasking.Event()
        self.event_process_kill_complete = multitasking.Event()
        # Strace/valgrind
        if self.with_strace and self.with_valgrind:
            raise RuntimeError("Trying to run with strace and valgrind.")
        if (((self.with_strace or self.with_valgrind)
             and platform._is_win)):  # pragma: windows
            raise RuntimeError("strace/valgrind options invalid on windows.")
        self.model_index = model_index
        self.copy_index = copy_index
        self.clients = clients
        self.env_copy = ['LANG', 'PATH', 'USER']
        self._exit_line = b'EXIT'
        for k in self.env_copy:
            if k in os.environ:
                self.env[k] = os.environ[k]
        if not self.is_installed():
            raise RuntimeError("%s is not installed" % self.language)
        self.raw_model_file = None
        self.model_function_file = None
        self.model_function_info = None
        self.model_file = None
        self.model_args = []
        self.model_dir = None
        self.model_src = None
        self.args = args
        self.modified_files = []
        self.wrapper_products = []
        self._mpi_comm = False
        self._mpi_rank = 0
        self._mpi_size = 1
        self._mpi_requests = {}
        self._mpi_tag = (len(self._mpi_tags) * self.model_index)
        if multitasking._on_mpi:
            self._mpi_comm = multitasking.MPI.COMM_WORLD
            self._mpi_rank = self._mpi_comm.Get_rank()
            self._mpi_size = self._mpi_comm.Get_size()
            self._mpi_partner_rank = mpi_rank
        # Update for function
        if self.function:
            if self.is_server:
                assert(isinstance(self.is_server, dict))
            if self.function_param is None:
                raise ValueError(("Language %s is not parameterized "
                                  "and so functions cannot be automatically "
                                  "wrapped as a model.") % self.language)
            self.model_function_file = self.get_source_file(args)
            if not os.path.isfile(self.model_function_file):
                raise ValueError("Source file does not exist: '%s'"
                                 % self.model_function_file)
            model_dir, model_base = os.path.split(self.model_function_file)
            model_base = os.path.splitext(model_base)[0]
            args[0] = os.path.join(model_dir,
                                   'ygg_%s_%s%s' % (model_base, self.name,
                                                    self.language_ext[0]))
            # Write file
            if (not os.path.isfile(args[0])) or self.overwrite:
                self.model_function_info = self.parse_function_definition(
                    self.model_function_file, self.function)
                client_comms = ['%s:%s_%s' % (self.name, x, self.name)
                                for x in self.client_of]
                lines = self.write_model_wrapper(
                    self.model_function_file, self.function,
                    inputs=copy.deepcopy(self.inputs),
                    outputs=copy.deepcopy(self.outputs),
                    outputs_in_inputs=self.model_outputs_in_inputs,
                    client_comms=client_comms, copies=self.copies,
                    model_name=self.name)
                with open(args[0], 'w') as fd:
                    fd.write('\n'.join(lines))
        # Parse arguments
        self.debug(str(args))
        self.parse_arguments(args)
        assert(self.model_file is not None)
        # Remove products
        if self.overwrite:
            self.remove_products()
        # Write wrapper
        if self.function:
            self.wrapper_products.append(args[0])
        self.wrapper_products += self.write_wrappers()

    @staticmethod
    def before_registration(cls):
        r"""Operations that should be performed to modify class attributes prior
        to registration including things like platform dependent properties and
        checking environment variables for default settings.
        """
        Driver.before_registration(cls)
        cls.inverse_type_map = None
        cls._language = cls.language
        cls._language_aliases = cls.language_aliases
        if (((cls.language_ext is not None)
             and (not isinstance(cls.language_ext, (list, tuple))))):
            cls.language_ext = [cls.language_ext]
            
    @staticmethod
    def after_registration(cls, cfg=None, second_pass=False):
        r"""Operations that should be performed to modify class attributes after
        registration. For compiled languages this includes selecting the
        default compiler. The order of precedence is the config file 'compiler'
        option for the language, followed by the environment variable set by
        _compiler_env, followed by the existing class attribute.

        Args:
            cfg (YggConfigParser, optional): Config class that should
                be used to set options for the driver. Defaults to
                None and yggdrasil.config.ygg_cfg is used.
            second_pass (bool, optional): If True, the class as already
                been registered. Defaults to False.

        """
        if cfg is None:
            from yggdrasil.config import ygg_cfg
            cfg = ygg_cfg
            cfg.reload()
        Driver.after_registration(cls)
        cls.cfg = cfg
        for x in cls._config_attr_map:
            ka = x['attr']
            k0 = x.get('key', ka)
            setattr(cls, ka, cls.cfg.get(cls.language, k0,
                                         getattr(cls, ka)))
        
    @staticmethod
    def finalize_registration(cls):
        r"""Operations that should be performed after a class has been fully
        initialized and registered."""
        global _map_language_ext
        for x in cls.get_language_ext():
            if x not in _map_language_ext:
                _map_language_ext[x] = []
            _map_language_ext[x].append(cls.language)

    @classmethod
    def get_inverse_type_map(cls):
        r"""Get the inverse type map.

        Returns:
            dict: Mapping from native type to JSON type.

        """
        if cls.inverse_type_map is None:
            cls.inverse_type_map = {}
            for k, v in cls.type_map.items():
                if k != 'flag':
                    cls.inverse_type_map[v] = k
        return cls.inverse_type_map

    @classmethod
    def get_language_for_source(cls, fname, languages=None, early_exit=False,
                                **kwargs):
        r"""Determine the language that can be used with the provided source
        file(s). If more than one language applies to a set of multiple files,
        the language that applies to the most files is returned.

        Args:
            fname (str, list): The full path to one or more files. If more than
                one
            languages (list, optional): The list of languages that are acceptable.
                Defaults to None and any language will be acceptable.
            early_exit (bool, optional): If True, the first language identified
                will be returned if fname is a list of files. Defaults to False.
            **kwargs: Additional keyword arguments are passed to recursive calls.

        Returns:
            str: The language that can operate on the specified file.

        """
        if isinstance(fname, list):
            lang_dict = {}
            for f in fname:
                try:
                    ilang = cls.get_language_for_source(f, languages=languages,
                                                        **kwargs)
                    if early_exit:
                        return ilang
                except ValueError:
                    continue
                lang_dict.setdefault(ilang, 0)
                lang_dict[ilang] += 1
            if lang_dict:
                return max(lang_dict, key=lang_dict.get)
        else:
            ext = os.path.splitext(fname)[-1]
            for ilang in cls.get_map_language_ext().get(ext, []):
                if (languages is None) or (ilang in languages):
                    return ilang
        raise ValueError("Cannot determine language for file(s): '%s'" % fname)
                
    @classmethod
    def get_map_language_ext(cls):
        r"""Return the mapping of all language extensions."""
        return _map_language_ext

    @classmethod
    def get_all_language_ext(cls):
        r"""Return the list of all language extensions."""
        return list(_map_language_ext.keys())

    @classmethod
    def get_language_dir(cls):
        r"""Return the langauge directory."""
        return languages.get_language_dir(cls.language)

    @classmethod
    def get_language_ext(cls):
        r"""Return the language extension, including from the base classes."""
        out = cls.language_ext
        if out is None:
            out = []
            for x in cls.base_languages:
                out += import_component('model', x).get_language_ext()
        return out
        
    def parse_arguments(self, args, default_model_dir=None):
        r"""Sort model arguments to determine which one is the executable
        and which ones are arguments.

        Args:
            args (list): List of arguments provided.
            default_model_dir (str, optional): Path to directory that should be
                used to normalize the model file path if it is not absolute.
                Defaults to None and is set to the working_dir.

        """
        if isinstance(args, (str, bytes)):
            args = args.split()
        for i in range(len(args)):
            args[i] = str(args[i])
        assert(isinstance(args, list))
        if default_model_dir is None:
            default_model_dir = self.working_dir
        self.raw_model_file = args[0]
        self.model_file = self.raw_model_file
        self.model_args = args[1:]
        if (self.language != 'executable') and (not os.path.isabs(self.model_file)):
            model_file = os.path.normpath(os.path.join(default_model_dir,
                                                       self.model_file))
            self.model_file = model_file
        self.model_dir = os.path.dirname(self.model_file)
        self.debug("model_file = '%s', model_dir = '%s', model_args = '%s'",
                   self.model_file, self.model_dir, self.model_args)

    @property
    def numeric_logging_level(self):
        r"""int: Logging level for the model."""
        out = self.logger.getEffectiveLevel()
        if self.logging_level:
            out = logging.getLevelName(self.logging_level)
        return out

    @property
    def n_sent_messages(self):
        r"""dict: Number of messages sent by the model via each connection."""
        if (self._mpi_rank > 0) and self.check_mpi_request('stopped'):
            out = self.check_mpi_request('stopped')
            return out
        out = {}
        for x in self.yml.get('output_drivers', []):
            x_inst = x.get('instance', None)
            if x_inst:
                out[x_inst.name] = x_inst.models_recvd.get(self.name, 0)
        if self.is_server:
            for x in self.yml.get('input_drivers', []):
                x_inst = x.get('instance', None)
                if x_inst and (x_inst._connection_type == 'rpc_request'):
                    out[x_inst.name] = x_inst.servers_recvd.get(self.name, 0)
        return out

    @property
    def has_sent_messages(self):
        r"""bool: True if output has been received from the model."""
        n_msg = self.n_sent_messages
        if not n_msg:
            return True
        return bool(sum(n_msg.values()))

    def write_wrappers(self, **kwargs):
        r"""Write any wrappers needed to compile and/or run a model.

        Args:
            **kwargs: Keyword arguments are ignored (only included to
               allow cascade from child classes).

        Returns:
            list: Full paths to any created wrappers.

        """
        return []
        
    def model_command(self):
        r"""Return the command that should be used to run the model.

        Returns:
            list: Any commands/arguments needed to run the model from the
                command line.

        """
        return [self.model_file] + self.model_args

    @classmethod
    def language_executable(cls, **kwargs):
        r"""Command required to compile/run a model written in this language
        from the command line.

        Returns:
            str: Name of (or path to) compiler/interpreter executable required
                to run the compiler/interpreter from the command line.

        """
        if cls.no_executable:
            return ''
        raise NotImplementedError("language_executable not implemented for '%s'"
                                  % cls.language)
        
    @classmethod
    def executable_command(cls, args, unused_kwargs=None, **kwargs):
        r"""Compose a command for running a program using the exectuable for
        this language (compiler/interpreter) with the provided arguments.

        Args:
            args (list): The program that returned command should run and any
                arguments that should be provided to it.
            unused_kwargs (dict, optional): Existing dictionary that unused
                keyword arguments should be added to. Defaults to None and is
                ignored.
            **kwargs: Additional keyword arguments are ignored.

        Returns:
            list: Arguments composing the command required to run the program
                from the command line using the executable for this language.

        """
        raise NotImplementedError("executable_command not implemented for '%s'"
                                  % cls.language)

    @classmethod
    def run_executable(cls, args, return_process=False, debug_flags=None,
                       **kwargs):
        r"""Run a program using the executable for this language and the
        provided arguments.

        Args:
            args (list): The program that should be run and any arguments
                that should be provided to it.
            return_process (bool, optional): If True, the process class is
                returned without checking the process output. If False,
                communicate is called on the process and the output is parsed
                for errors. Defaults to False.
            debug_flags (list, optional): Debug executable and flags that should
                be prepended to the executable command. Defaults to None and
                is ignored.
            **kwargs: Additional keyword arguments are passed to
                cls.executable_command and tools.popen_nobuffer.

        Returns:
            str: Output to stdout from the run command if return_process is
                False, the process if return_process is True.
        
        Raises:
            RuntimeError: If the language is not installed.
            RuntimeError: If there is an error when running the command.

        """
        unused_kwargs = {}
        cmd = cls.executable_command(args, unused_kwargs=unused_kwargs, **kwargs)
        if isinstance(debug_flags, list):
            cmd = debug_flags + cmd
        try:
            # Add default keyword arguments
            if 'working_dir' in unused_kwargs:
                unused_kwargs.setdefault('cwd', unused_kwargs.pop('working_dir'))
            unused_kwargs.setdefault('shell', platform._is_win)
            # Call command
            logger.debug("Running '%s' from %s"
                         % (' '.join(cmd), unused_kwargs.get('cwd', os.getcwd())))
            logger.debug("Process keyword arguments:\n%s\n",
                         '    ' + pformat(unused_kwargs).replace('\n', '\n    '))
            print(' '.join(cmd))
            proc = tools.popen_nobuffer(cmd, **unused_kwargs)
            if return_process:
                return proc
            out, err = proc.communicate()
            if proc.returncode != 0:
                if out:
                    logger.info('\n%s' % out.decode('utf-8'))
                if err:  # pragma: debug
                    logger.info('\n%s' % err.decode('utf-8'))
                raise RuntimeError("Command '%s' failed with code %d."
                                   % (' '.join(cmd), proc.returncode))
            out = out.decode("utf-8")
            logger.debug('%s\n%s' % (' '.join(cmd), out))
            return out
        except (subprocess.CalledProcessError, OSError) as e:  # pragma: debug
            raise RuntimeError("Could not call command '%s': %s"
                               % (' '.join(cmd), e))
        
    def run_model(self, return_process=True, **kwargs):
        r"""Run the model. Unless overridden, the model will be run using
        run_executable.

        Args:
            return_process (bool, optional): If True, the process running
                the model is returned. If False, the process will block until
                the model finishes running. Defaults to True.
            **kwargs: Keyword arguments are passed to run_executable.

        """
        env = self.set_env()
        command = self.model_command()
        if self.with_strace or self.with_valgrind:
            kwargs.setdefault('debug_flags', self.debug_flags)
        self.debug('Working directory: %s', self.working_dir)
        self.debug('Command: %s', ' '.join(command))
        self.debug('Environment Variables:\n%s', self.pprint(env, block_indent=1))
        # Update keywords
        # NOTE: Setting forward_signals to False allows faster debugging
        # but should not be used in deployment for cases where models are not
        # running locally.
        default_kwargs = dict(env=env, working_dir=self.working_dir,
                              forward_signals=False,
                              shell=platform._is_win)
        for k, v in default_kwargs.items():
            kwargs.setdefault(k, v)
        return self.run_executable(command, return_process=return_process, **kwargs)

    @property
    def debug_flags(self):
        r"""list: Flags that should be prepended to an executable command to
        enable debugging."""
        pre_args = []
        if self.with_strace:
            if platform._is_linux:
                pre_args += ['strace'] + self.strace_flags
            else:  # pragma: debug
                raise RuntimeError("strace not supported on this OS.")
            # TODO: dtruss cannot be run without sudo, sudo cannot be
            # added to the model process command if it is not in the original
            # yggdrasil CLI call, and must be tested with an executable that
            # is not "signed with restricted entitlements" (which most built-in
            # utilities (e.g. sleep) are).
            # elif platform._is_mac:
            #     if 'sudo' in sys.argv:
            #         pre_args += ['sudo']
            #     pre_args += ['dtruss']
        elif self.with_valgrind:
            pre_args += ['valgrind'] + self.valgrind_flags
        return pre_args
        
    @classmethod
    def language_version(cls, version_flags=None, **kwargs):
        r"""Determine the version of this language.

        Args:
            **kwargs: Keyword arguments are passed to cls.run_executable.

        Returns:
            str: Version of compiler/interpreter for this language.

        """
        if version_flags is None:
            version_flags = cls.version_flags
        return cls.run_executable(version_flags, **kwargs).splitlines()[0].strip()

    @classmethod
    def is_installed(cls):
        r"""Determine if this model driver is installed on the current
        machine.

        Returns:
            bool: Truth of if this model driver can be run on the current
                machine.

        """
        return (cls.is_language_installed()
                and cls.are_base_languages_installed()
                and cls.are_dependencies_installed()
                and cls.is_interface_installed() and cls.is_comm_installed()
                and cls.is_configured() and (not cls.is_disabled()))

    @classmethod
    def are_base_languages_installed(cls, missing=None):
        r"""Determine if the base languages are installed.

        Args:
            missing (list, optional): A pre-existing list that
                missing base languages should be appended to.

        Returns:
            bool: True if the base langauges are installed. False otherwise.

        """
        out = True
        for x in cls.base_languages:
            if (not out) and (not isinstance(missing, list)):  # pragma: no cover
                break
            out = import_component('model', x).is_installed()
            if isinstance(missing, list) and (not out):
                missing.append(x)
        if missing:
            out = False
        return out

    @classmethod
    def are_dependencies_installed(cls):
        r"""Determine if the dependencies are installed for the interface (not
        including dependencies needed by a particular communication type).

        Returns:
            bool: True if the dependencies are installed. False otherwise.

        """
        out = (cls.language is not None)
        for x in cls.interface_dependencies:
            if not out:  # pragma: no cover
                break
            out = cls.is_library_installed(x)
        return out

    @classmethod
    def is_interface_installed(cls):
        r"""Determine if the interface library for the associated programming
        language is installed.

        Returns:
            bool: True if the interface library is installed.

        """
        out = (cls.language is not None)
        if out and (cls.interface_library is not None):
            out = cls.is_library_installed(cls.interface_library)
        return out
    
    @classmethod
    def is_language_installed(cls):
        r"""Determine if the interpreter/compiler for the associated programming
        language is installed.

        Returns:
            bool: True if the language interpreter/compiler is installed.

        """
        out = False
        if cls.language is not None:
            try:
                out = (shutil.which(cls.language_executable()) is not None)
            except NotImplementedError:  # pragma: debug
                out = False
        return out

    def get_source_file(self, args):
        r"""Determine the source file based on arguments.

        Args:
            args (list): Arguments provided.

        Returns:
            str: Full path to source file select.

        """
        out = args[0]
        if (((not self.is_source_file(out))
             and (self.language_ext is not None)
             and (os.path.splitext(out)[-1]
                  not in self.get_all_language_ext()))):
            out = os.path.splitext(out)[0] + self.language_ext[0]
        if not os.path.isabs(out):
            out = os.path.normpath(os.path.join(self.working_dir, out))
        return out

    @classmethod
    def is_source_file(cls, fname):
        r"""Determine if the provided file name points to a source files for
        the associated programming language by checking the extension.

        Args:
            fname (str): Path to file.

        Returns:
            bool: True if the provided file is a source file, False otherwise.

        """
        out = False
        model_ext = os.path.splitext(fname)[-1]
        if len(model_ext) > 0:
            out = (model_ext in cls.get_language_ext())
        return out

    @classmethod
    def is_library_installed(cls, lib, **kwargs):
        r"""Determine if a dependency is installed.

        Args:
            lib (str): Name of the library that should be checked.
            **kwargs: Additional keyword arguments are ignored.

        Returns:
            bool: True if the library is installed, False otherwise.

        """
        raise NotImplementedError("Method is_library_installed missing for '%s'"
                                  % cls.language)

    @classmethod
    def is_disabled(cls):
        return (cls.cfg.get(cls.language, 'disable', 'false').lower() == 'true')

    @classmethod
    def is_configured(cls):
        r"""Determine if the appropriate configuration has been performed (e.g.
        installation of supporting libraries etc.)

        Returns:
            bool: True if the language has been configured.

        """
        # Check for section & diable
        disable_flag = cls.is_disabled()
        out = (cls.cfg.has_section(cls.language) and (not disable_flag))
        # Check for commtypes
        if out and (len(cls.base_languages) == 0):
            out = (cls.cfg.get(cls.language, 'commtypes', None) is not None)
        # Check for config keys
        for k in cls._config_keys:
            if not out:  # pragma: no cover
                break
            out = (cls.cfg.get(cls.language, k, None) is not None)
        return out

    @classmethod
    def is_comm_installed(cls, commtype=None, skip_config=False, **kwargs):
        r"""Determine if a comm is installed for the associated programming
        language.

        Args:
            commtype (str, optional): If provided, this method will only test
                for installation of the specified communication type. Defaults
                to None and will check for any installed comm.
            skip_config (bool, optional): If True, the config list of comms
                installed for this language will not be used to determine if
                the comm is installed and the class attribute
                supported_comm_options will be processed. Defaults to False and
                config options are used in order to improve performance after
                initial configuration.
            platforms (list, optional): Platforms on which the comm can be
                installed. Defaults to None and is ignored unless there is a
                value for the commtype in supported_comm_options. This
                keyword argument is ignored if skip_config is False.
            libraries (list, optional): External libraries that are required
                by the specified commtype. Defaults to None and is ignored
                unless there is a value for the commtype in supported_comm_options.
                This keyword argument is ignored if skip_config is False.
            **kwargs: Additional keyword arguments are passed to either
                is_comm_installed for the base languages, supported languages,
                or is_library_installed as appropriate.

        Returns:
            bool: True if a comm is installed for this language.

        """
        # If there are base_languages for this language, use that language's
        # driver to check for comm installation.
        if len(cls.base_languages) > 0:
            out = True
            for x in cls.base_languages:
                if not out:  # pragma: no cover
                    break
                out = import_component('model', x).is_comm_installed(
                    commtype=commtype, skip_config=skip_config, **kwargs)
            return out
        if cls.comms_implicit:
            return True
        # Check for installation based on config option
        if not skip_config:
            installed_comms = cls.cfg.get(cls.language, 'commtypes', [])
            if commtype is None:
                return (len(installed_comms) > 0)
            else:
                return (commtype in installed_comms)
        # Check for any comm
        if commtype is None:
            for c in cls.supported_comms:
                if cls.is_comm_installed(commtype=c, skip_config=skip_config,
                                         **kwargs):
                    return True
        # Check that comm is explicitly supported
        if commtype not in cls.supported_comms:
            return False
        # Set & pop keywords
        for k, v in cls.supported_comm_options.get(commtype, {}).items():
            if kwargs.get(k, None) is None:
                kwargs[k] = v
        platforms = kwargs.pop('platforms', None)
        libraries = kwargs.pop('libraries', [])
        # Check platforms
        if (platforms is not None) and (platform._platform not in platforms):
            return False  # pragma: windows
        # Check libraries
        if (libraries is not None):
            for lib in libraries:
                if not cls.is_library_installed(lib, **kwargs):
                    return False
        # Check for server on RabbitMQ
        if commtype in ['rmq', 'rmq_async']:
            from yggdrasil.communication.RMQComm import check_rmq_server
            if not check_rmq_server():
                return False
        return True
    
    @classmethod
    def configure(cls, cfg):
        r"""Add configuration options for this language.

        Args:
            cfg (CisConfigParser): Config class that options should be set for.
        
        Returns:
            list: Section, option, description tuples for options that could not
                be set.

        """
        out = []
        # Section and executable
        if (cls.language is not None) and (not cfg.has_section(cls.language)):
            cfg.add_section(cls.language)
        # Executable type configuration
        out += cls.configure_executable_type(cfg)
        # Locate executable
        if (((not cls.is_language_installed())
             and (cls.executable_type is not None))):  # pragma: debug
            try:
                exec_file = cls.language_executable()
                if exec_file is not None:
                    fpath = tools.locate_file(
                        exec_file, directory_list=cls._executable_search_dirs)
                    if fpath:
                        cfg.set(cls.language, cls.executable_type, fpath)
            except NotImplementedError:
                pass
        # Configure libraries
        out += cls.configure_libraries(cfg)
        # Only do additional configuration if no base languages
        if not cls.base_languages:
            # Installed comms
            comms = []
            for c in cls.supported_comms:
                if cls.is_comm_installed(commtype=c, cfg=cfg, skip_config=True):
                    comms.append(c)
            cfg.set(cls.language, 'commtypes', comms)
        cls.after_registration(cls, cfg=cfg, second_pass=True)
        return out

    @classmethod
    def configure_executable_type(cls, cfg):
        r"""Add configuration options specific in the executable type
        before the libraries are configured.

        Args:
            cfg (YggConfigParser): Config class that options should be set for.
        
        Returns:
            list: Section, option, description tuples for options that could not
                be set.

        """
        return []

    @classmethod
    def configure_libraries(cls, cfg):
        r"""Add configuration options for external libraries in this language.

        Args:
            cfg (YggConfigParser): Config class that options should be set for.
        
        Returns:
            list: Section, option, description tuples for options that could not
                be set.

        """
        return []

    @classmethod
    def set_env_class(cls, existing=None, **kwargs):
        r"""Set environment variables that are instance independent.

        Args:
            existing (dict, optional): Existing dictionary of environment
                variables that new variables should be added to. Defaults
                to a copy of os.environ.
            **kwargs: Additional keyword arguments are ignored.

        Returns:
            dict: Environment variables for the model process.

        """
        if existing is None:  # pragma: no cover
            existing = {}
        existing.update(os.environ)
        return existing

    def set_env(self, existing=None, **kwargs):
        r"""Get environment variables that should be set for the model process.

        Args:
            existing (dict, optional): Existing dictionary of environment
                variables that new variables should be added to. Defaults
                to a copy of os.environ.
            **kwargs: Additional keyword arguments are passed to set_env_class.

        Returns:
            dict: Environment variables for the model process.

        """
        from yggdrasil.config import ygg_cfg
        if existing is None:
            existing = {}
        existing.update(copy.deepcopy(self.env))
        env = self.set_env_class(existing=existing, **kwargs)
        env['YGG_SUBPROCESS'] = "True"
        if multitasking._on_mpi:
            env['YGG_MPI_RANK'] = str(multitasking._mpi_rank)
        env['YGG_MODEL_INDEX'] = str(self.model_index)
        env['YGG_MODEL_LANGUAGE'] = self.language
        if self.copies > 1:
            env['YGG_MODEL_NAME'] = self.name.split('_copy')[0]
            env['YGG_MODEL_COPY'] = str(self.copy_index)
        else:
            env['YGG_MODEL_NAME'] = self.name
        env['YGG_MODEL_COPIES'] = str(self.copies)
        # env['YGG_PYTHON_EXEC'] = sys.executable
        env['YGG_DEFAULT_COMM'] = tools.get_default_comm()
        env['YGG_NCLIENTS'] = str(len(self.clients))
        if self.allow_threading or (self.copies > 1):
            env['YGG_THREADING'] = '1'
        if isinstance(self.is_server, dict):
            env['YGG_SERVER_INPUT'] = self.is_server['input']
            env['YGG_SERVER_OUTPUT'] = self.is_server['output']
        if self.logging_level:
            env['YGG_MODEL_DEBUG'] = self.logging_level
        replace = [k for k in env.keys() if ':' in k]
        for k in replace:
            env[k.replace(':', '__COLON__')] = env.pop(k)
        if ygg_cfg.get('general', 'allow_multiple_omp', False):
            env['KMP_DUPLICATE_LIB_OK'] = 'True'
        return env

    def before_start(self, no_queue_thread=False, **kwargs):
        r"""Actions to perform before the run starts.

        Args:
            no_queue_thread (bool, optional): If True, the queue_thread is not
                created/started. Defaults to False.
            **kwargs: Keyword arguments are pased to run_model.

        """
        self.model_process = self.run_model(**kwargs)
        # Start thread to queue output
        if not no_queue_thread:
            self.queue_thread = multitasking.YggTaskLoop(
                target=self.enqueue_output_loop,
                name=self.name + '.EnqueueLoop')
            self.queue_thread.start()
        if multitasking._on_mpi:
            self.init_mpi()

    def queue_close(self):
        r"""Close the queue for messages from the model process."""
        self.model_process.stdout.close()

    def queue_recv(self):
        r"""Receive a message from the model process."""
        return self.model_process.stdout.readline()

    def enqueue_output_loop(self):
        r"""Keep passing lines to queue."""
        try:
            line = self.queue_recv()
        except BaseException as e:  # pragma: debug
            print(e)
            line = ""
        if (len(line) == 0):
            self.queue_thread.set_break_flag()
            try:
                self.queue.put(self._exit_line)
            except multitasking.AliasDisconnectError:  # pragma: debug
                self.error("Queue disconnected")
            self.debug("End of model output")
            try:
                self.queue_close()
            except BaseException:  # pragma: debug
                pass
        else:
            try:
                self.queue.put(line.decode('utf-8'))
            except BaseException as e:  # pragma: debug
                warnings.warn("Error in printing output: %s" % e)

    def before_loop(self):
        r"""Actions before loop."""
        self.debug('Running %s from %s with cwd %s and env %s',
                   self.model_command(), os.getcwd(), self.working_dir,
                   pformat(self.env))

    def init_mpi(self):
        r"""Initialize MPI communicator."""
        if self._mpi_rank == 0:
            self._mpi_comm = None
        else:
            self.recv_mpi(tag=self._mpi_tags['START'])
            self._mpi_requests['stopped'] = {
                'request': self.recv_mpi(tag=self._mpi_tags['STOP_RANKX'],
                                         dont_block=True)}

    def send_mpi(self, msg, tag=0, dont_block=False):
        r"""Send an MPI message."""
        self.debug("%d: %s (blocking=%s)", self._mpi_tag + tag, msg, dont_block)
        kws = {'dest': self._mpi_partner_rank, 'tag': (self._mpi_tag + tag)}
        if dont_block:
            return self._mpi_comm.isend(msg, **kws)
        else:
            return self._mpi_comm.send(msg, **kws)

    def recv_mpi(self, tag=0, dont_block=False):
        r"""Receive an MPI message."""
        self.debug('%d (blocking=%s)', self._mpi_tag + tag, dont_block)
        kws = {'source': self._mpi_partner_rank, 'tag': (self._mpi_tag + tag)}
        if dont_block:
            return self._mpi_comm.irecv(**kws)
        else:
            return self._mpi_comm.recv(**kws)

    def stop_mpi_partner(self, msg=None, dest=0, tag=None):
        r"""Send a message to stop the MPI partner model on the main process."""
        if self._mpi_comm and (not self.check_mpi_request('stopping')):
            if tag is None:
                tag = self._mpi_tags['STOP_RANK0']
            if msg is None:
                if self.errors:
                    msg = 'ERROR'
                else:
                    msg = 'STOPPING'
            self._mpi_requests['stopping'] = {
                'result': True,  # Don't call test()
                'request': self.send_mpi(msg, tag=tag)}

    def wait_on_mpi_request(self, name, timeout=False):
        r"""Wait for a request to be completed.

        Args:
            name (str): Name that request was registered under.

        Returns:
            bool, str: Received message or False if the request does not
                exist or is not complete.

        """
        Tout = self.start_timeout(t=timeout, key_suffix=('.%s' % name))
        while (not self.check_mpi_request(name)) and (not Tout.is_out):
            self.sleep()
        self.stop_timeout(key_suffix=('.%s' % name))
        return self.check_mpi_request(name)

    def check_mpi_request(self, name):
        r"""Check if a request has been completed.

        Args:
            name (str): Name that request was registered under.

        Returns:
            bool, str: Received message or False if the request does not
                exist or is not complete.

        """
        if self._mpi_comm and (name in self._mpi_requests):
            if 'result' not in self._mpi_requests[name]:
                result = self._mpi_requests[name]['request'].test()
                if result[0]:
                    self._mpi_requests[name]['result'] = result[1]
                    if result[1] == 'ERROR':
                        self.errors.append(result[1])
            return self._mpi_requests[name].get('result', False)
        return False

    def set_break_flag(self, *args, **kwargs):
        r"""Stop the model loop."""
        self.stop_mpi_partner()
        super(ModelDriver, self).set_break_flag(*args, **kwargs)

    def run_loop(self):
        r"""Loop to check if model is still running and forward output."""
        # Continue reading until there is not any output
        if self.check_mpi_request('stopped'):
            self.debug("Stop requested by MPI partner.")
            self.set_break_flag()
        try:
            line = self.queue.get_nowait()
        except Empty:
            # This sleep is necessary to allow changes in queue without lock
            self.sleep()
            return
        except multitasking.AliasDisconnectError:  # pragma: debug
            self.error("Queue disconnected")
            self.set_break_flag()
        else:
            if (line == self._exit_line) or self.check_mpi_request('stopped'):
                self.debug("No more output")
                self.set_break_flag()
            else:
                self.print_encoded(line, end="")
                sys.stdout.flush()

    def run_finally(self):
        r"""Actions to perform in finally clause of try/except wrapping
        run."""
        # Ensure the MPI partner gets cleaned up following an error
        self.stop_mpi_partner()
        super(ModelDriver, self).run_finally()

    def after_loop(self):
        r"""Actions to perform after run_loop has finished. Mainly checking
        if there was an error and then handling it."""
        self.debug('')
        if self.queue_thread is not None:
            self.queue_thread.join(self.sleeptime)
            if self.queue_thread.is_alive():
                self.debug("Queue thread still alive")
                # Loop was broken from outside, kill the queueing thread
                self.kill_process()
                return
        self.wait_process(self.timeout, key_suffix='.after_loop')
        self.kill_process()
        self.debug(("Closing input/output drivers:\n"
                    "\tinput: %s\n\toutput: %s")
                   % ([drv['name'] for drv in
                       self.yml.get('input_drivers', [])],
                      [drv['name'] for drv in
                       self.yml.get('output_drivers', [])]))
        for drv in self.yml.get('input_drivers', []):
            if 'instance' in drv:
                drv['instance'].on_model_exit('output', self.name,
                                              errors=self.errors)
        for drv in self.yml.get('output_drivers', []):
            if 'instance' in drv:
                drv['instance'].on_model_exit('input', self.name,
                                              errors=self.errors)

    @property
    def io_errors(self):
        r"""list: Errors produced by input/output drivers to this model."""
        errors = []
        for drv in self.yml.get('input_drivers', []):
            if 'instance' in drv:
                errors += drv['instance'].errors
        for drv in self.yml.get('output_drivers', []):
            if 'instance' in drv:
                errors += drv['instance'].errors
        return errors

    @property
    def model_process_complete(self):
        r"""bool: Has the process finished or not. Returns True if the process
        has not started."""
        if self.model_process is None:  # pragma: debug
            return True
        return (self.model_process.poll() is not None)

    def wait_process(self, timeout=None, key=None, key_suffix=None):
        r"""Wait for some amount of time for the process to finish.

        Args:
            timeout (float, optional): Time (in seconds) that should be waited.
                Defaults to None and is infinite.
            key (str, optional): Key that should be used to register the timeout.
                Defaults to None and set based on the stack trace.

        Returns:
            bool: True if the process completed. False otherwise.

        """
        if not self.was_started:  # pragma: debug
            return True
        T = self.start_timeout(timeout, key_level=1, key=key, key_suffix=key_suffix)
        while ((not T.is_out) and (not self.model_process_complete)):  # pragma: debug
            self.sleep()
        self.stop_timeout(key_level=1, key=key, key_suffix=key_suffix)
        return self.model_process_complete

    def kill_process(self):
        r"""Kill the process running the model, checking return code."""
        if not self.was_started:  # pragma: debug
            self.debug('Process was never started.')
            self.set_break_flag()
            self.event_process_kill_called.set()
            self.event_process_kill_complete.set()
        if self.event_process_kill_called.is_set():  # pragma: debug
            self.debug('Process has already been killed.')
            return
        self.event_process_kill_called.set()
        with self.lock:
            self.debug('')
            if not self.model_process_complete:  # pragma: debug
                self.debug("Process is still running. Killing it.")
                try:
                    self.model_process.kill()
                    self.debug("Waiting %f s for process to be killed",
                               self.timeout)
                    self.wait_process(self.timeout, key_suffix='.kill_process')
                except BaseException:  # pragma: debug
                    self.exception("Error killing model process")
            assert(self.model_process_complete)
            if (((self.model_process is not None)
                 and (self.model_process.returncode != 0)
                 and self.has_sent_messages)):
                self.error("return code of %s indicates model error.",
                           str(self.model_process.returncode))
            self.event_process_kill_complete.set()
            if self.queue_thread is not None:
                if not self.was_break:  # pragma: debug
                    # Wait for messages to be printed
                    self.debug("Waiting for queue_thread to finish up.")
                    self.queue_thread.wait(self.timeout)
                if self.queue_thread.is_alive():  # pragma: debug
                    self.debug("Setting break flag for queue_thread to finish up.")
                    self.queue_thread.set_break_flag()
                    self.queue_thread.wait(self.timeout)
                    try:
                        self.queue_close()
                        self.queue_thread.wait(self.timeout)
                    except BaseException:  # pragma: debug
                        self.exception("Closed during concurrent action")
                    if self.queue_thread.is_alive():  # pragma: debug
                        self.error("Queue thread was not terminated.")

    def graceful_stop(self):
        r"""Gracefully stop the driver."""
        self.debug('')
        if self.has_sent_messages:
            self.wait_process(self.timeout, key_suffix='.graceful_stop')
        super(ModelDriver, self).graceful_stop()

    def cleanup_products(self):
        r"""Remove products created in order to run the model."""
        if self.overwrite and (not self.preserve_cache):
            self.remove_products()
        self.restore_files()

    def cleanup(self):
        r"""Remove compile executable."""
        self.cleanup_products()
        super(ModelDriver, self).cleanup()

    def restore_files(self):
        r"""Restore modified files to their original form."""
        for (original, modified) in self.modified_files:
            if os.path.isfile(original):
                os.remove(modified)
                shutil.move(original, modified)

    def remove_products(self):
        r"""Delete products produced during the process of running the model."""
        products = self.products
        source_products = self.source_products + self.wrapper_products
        remove_products(products, source_products, timer_class=self)
            
    @classmethod
    def cleanup_dependencies(cls, products=[], verbose=False):
        r"""Cleanup dependencies."""
        for x in products:
            if os.path.isfile(x):
                if verbose:  # pragma: debug
                    print("Removing %s" % x)
                os.remove(x)
                
    # Methods for automated model wrapping
    @classmethod
    def run_code(cls, lines, process_kwargs={}, **kwargs):
        r"""Run code by first writing it as an executable and then calling
        the driver.

        Args:
            lines (list): Lines of code to be wrapped as an executable.
            process_kwargs (dict, optional): Keyword arguments that should
                be passed to run_model. Defaults to {}.
            **kwargs: Additional keyword arguments are passed to the
                write_executable method.

        """
        name = 'test_code_%s' % str(uuid.uuid4())[:13].replace('-', '_')
        working_dir = os.getcwd()
        code_dir = tempfile.gettempdir()
        # code_dir = working_dir
        fname = os.path.join(code_dir, name + cls.get_language_ext()[0])
        lines = cls.write_executable(lines, **kwargs)
        with open(fname, 'w') as fd:
            fd.write('\n'.join(lines))
        inst = None
        try:
            assert(os.path.isfile(fname))
            inst = cls(name, [fname], working_dir=working_dir)
            inst.run_model(return_process=False, **process_kwargs)
        except BaseException:  # pragma: debug
            logger.error('Failed generated code:\n%s' % '\n'.join(lines))
            raise
        finally:
            if os.path.isfile(fname):
                os.remove(fname)
            if inst is not None:
                inst.cleanup()

    @classmethod
    def format_function_param(cls, key, default=None,
                              replacement=None, **kwargs):
        r"""Return the formatted version of the specified key.

        Args:
            key (str): Key in cls.function_param mapping that should be
                formatted.
            default (str, optional): Format that should be returned if key
                is not in cls.function_param. Defaults to None.
            replacement (str, optional): Format that should be used instead
                of the one in cls.function_param. Defaults to None.
            **kwargs: Additional keyword arguments are used in formatting the
                request function parameter.

        Returns:
            str: Formatted string.

        Raises:
            NotImplementedError: If key is not in cls.function_param and default
                is not set.

        """
        if replacement is not None:
            fmt = replacement
        else:
            if (key not in cls.function_param) and (default is None):
                raise NotImplementedError(("Language %s dosn't have an entry in "
                                           "function_param for key '%s'")
                                          % (cls.language, key))
            fmt = cls.function_param.get(key, default)
        return fmt.format(**kwargs)

    @classmethod
    def parse_var_definition(cls, io, value, outputs_in_inputs=None):
        r"""Extract information about input/output variables from a
        string definition.

        Args:
            io (str): Description of variables contained in the provided
                string. Must be 'inputs' or 'outputs'.
            value (str): String containing one or more variable definitions.
            outputs_in_inputs (bool, optional): If True, the outputs are
                presented in the function definition as inputs. Defaults
                to False.

        Returns:
            list: List of information about the variables contained in
                the provided string.

        Raises:
            AssertionError: If io is not 'inputs' or 'outputs'.
            NotImplementedError: If the def_regex for the specified
                io is not defined.

        """
        if outputs_in_inputs is None:
            outputs_in_inputs = cls.outputs_in_inputs
        assert(io in ['inputs', 'outputs'])
        if ('%s_def_regex' % io) not in cls.function_param:  # pragma: debug
            raise NotImplementedError(
                ("'%s_def_regex' not defined for "
                 "language %s.") % (io, cls.language))
        if 'multiple_outputs' in cls.function_param:
            multi_re = cls.function_param['multiple_outputs']
            for x in '[]()':
                multi_re = multi_re.replace(x, '\\' + x)
            multi_re = multi_re.format(outputs='(.*?)')
            match = re.search(multi_re, value)
            if match is not None:
                value = match.group(1)
        new_val = []
        io_re = cls.format_function_param('%s_def_regex' % io)
        for i, ivar in enumerate(cls.split_variables(value)):
            igrp = {'name': ivar}
            x = re.search(io_re, ivar)
            if x is not None:
                igrp = x.groupdict()
                for k in list(igrp.keys()):
                    if igrp[k] is None:
                        del igrp[k]
            if 'native_type' in igrp:
                igrp['native_type'] = igrp['native_type'].replace(' ', '')
                igrp['datatype'] = cls.get_json_type(igrp['native_type'])
            igrp['position'] = i
            if (io == 'outputs') and outputs_in_inputs:
                igrp = cls.input2output(igrp)
            new_val.append(igrp)
        return new_val

    @classmethod
    def parse_function_definition(cls, model_file, model_function,
                                  contents=None, match=None,
                                  expected_outputs=[], outputs_in_inputs=None):
        r"""Get information about the inputs & outputs to a model from its
        defintition if possible.

        Args:
            model_file (str): Full path to the file containing the model
                function's declaration.
            model_function (str): Name of the model function.
            contents (str, optional): String containing the function definition.
                If not provided, the function definition is read from model_file.
            match (re.Match, optional): Match object for the function regex. If
                not provided, a search is performed using function_def_regex.
            expected_outputs (list, optional): List of names or variable
                information dictionaries for outputs that are expected
                to be extracted from the function's definition. This
                variable is only used if outputs_in_inputs is True and
                outputs are not extracted from the function's defintion
                using the regex for this language. Defaults to [].
            outputs_in_inputs (bool, optional): If True, the outputs are
                presented in the function definition as inputs. Defaults
                to False.

        Returns:
            dict: Parameters extracted from the function definitions.

        """
        if outputs_in_inputs is None:
            outputs_in_inputs = cls.outputs_in_inputs
        out = {}
        if match or ('function_def_regex' in cls.function_param):
            if not match:
                function_regex = cls.format_function_param(
                    'function_def_regex', function_name=model_function)
                if contents is None:
                    with open(model_file, 'r') as fd:
                        contents = fd.read()
                match = re.search(function_regex, contents)
                if not match:  # pragma: debug
                    raise RuntimeError(("Could not find function match in file:\n"
                                        "%s\nfor regex:\nr'%s'")
                                       % (pformat(contents), function_regex))
                # Match brackets to determine where the function definition is
                if isinstance(cls.brackets, tuple):
                    assert(len(cls.brackets) == 2)
                    contents = match.group(0)
                    counts = {k: 0 for k in cls.brackets}
                    first_zero = 0
                    re_brackets = r'[\%s\%s]' % cls.brackets
                    for x in re.finditer(re_brackets, contents):
                        counts[x.group(0)] += 1
                        if (((counts[cls.brackets[0]] > 0)
                             and (counts[cls.brackets[0]]
                                  == counts[cls.brackets[1]]))):
                            first_zero = x.span(0)[1]
                            break
                    assert((first_zero == 0) or (first_zero == len(contents)))
                    # This is currently commented as regex's are
                    # sufficient so far, but this may be needed in the
                    # future to isolate single definitions.
                    # if (first_zero != 0) and first_zero != len(contents):
                    #     contents = contents[:first_zero]
                    #     match = re.search(function_regex, contents)
                    #     assert(match)
            out = match.groupdict()
            for k in list(out.keys()):
                if out[k] is None:
                    del out[k]
            for io in ['inputs', 'outputs']:
                if io in out:
                    out[io] = cls.parse_var_definition(
                        io, out[io], outputs_in_inputs=outputs_in_inputs)
        if outputs_in_inputs and expected_outputs and (not out.get('outputs', False)):
            missing_expected_outputs = []
            for o in expected_outputs:
                if isinstance(o, dict):
                    o = o['name']
                missing_expected_outputs.append(o)
            out['outputs'] = []
            for x in out['inputs']:
                if x['name'] not in missing_expected_outputs:
                    continue
                missing_expected_outputs.remove(x['name'])
                out['outputs'].append(cls.input2output(x))
            if missing_expected_outputs:  # pragma: debug
                raise ValueError(("Could not locate %d output "
                                  "variable(s) in input:  %s")
                                 % (len(missing_expected_outputs),
                                    missing_expected_outputs))
            for x in out['outputs']:
                out['inputs'].remove(x)
        if out.get('flag_var', None):
            flag_var = {'name': out.pop('flag_var'),
                        'datatype': {'type': 'flag'}}
            if out.get('flag_type', None):
                flag_var['native_type'] = out.pop('flag_type').replace(' ', '')
                flag_var['datatype'] = cls.get_json_type(flag_var['native_type'])
            if outputs_in_inputs:
                out['flag_var'] = flag_var
            else:
                assert(not out.get('outputs', []))
                out['outputs'] = [flag_var]
        return out

    @classmethod
    def channels2vars(cls, channels):
        r"""Convert a list of channels to a list of variables.

        Args:
            channels (list): List of channel dictionaries.

        Returns:
            list: List of variables.

        """
        if not isinstance(channels, list):
            channels = [channels]
        variables = []
        for x in channels:
            variables += x['vars']
        
        def get_pos(x):
            return x.get('position', 0)
        variables = sorted(variables, key=get_pos)
        return variables

    @classmethod
    def update_io_from_function(cls, model_file, model_function,
                                inputs=[], outputs=[], contents=None,
                                outputs_in_inputs=None):
        r"""Update inputs/outputs from the function definition.

        Args:
            model_file (str): Full path to the file containing the model
                function's declaration.
            model_function (str): Name of the model function.
            inputs (list, optional): List of model inputs including types.
                Defaults to [].
            outputs (list, optional): List of model outputs including types.
                Defaults to [].
            contents (str, optional): Contents of file to parse rather than
                re-reading the file. Defaults to None and is ignored.
            outputs_in_inputs (bool, optional): If True, the outputs are
                presented in the function definition as inputs. Defaults
                to False.

        Returns:
            dict, None: Flag variable used by the model. If None, the
                model does not use a flag variable.

        """
        if outputs_in_inputs is None:  # pragma: debug
            outputs_in_inputs = cls.outputs_in_inputs
        if (((isinstance(model_file, str) and os.path.isfile(model_file))
             or (contents is not None))):
            expected_outputs = []
            for x in outputs:
                expected_outputs += x.get('vars', [])
            info = cls.parse_function_definition(model_file, model_function,
                                                 contents=contents,
                                                 expected_outputs=expected_outputs)
        else:
            info = {"inputs": [], "outputs": []}
        info_map = {io: OrderedDict([(x['name'], x) for x in info.get(io, [])])
                    for io in ['inputs', 'outputs']}
        # Determine flag variable
        flag_var = None
        if info.get('flag_var', None):
            flag_var = dict(info['flag_var'], name='model_flag')
        # Check for vars matching names of input/output channels
        for io, io_var in zip(['inputs', 'outputs'], [inputs, outputs]):
            if (io == 'outputs') and outputs_in_inputs:
                io_map = info_map['inputs']
            else:
                io_map = info_map[io]
            for x in io_var:
                if x.get('vars', []):
                    continue
                var_name = x['name'].split(':')[-1]
                if var_name in io_map:
                    x['vars'] = [var_name]
                    for k in ['length', 'shape', 'ndim']:
                        kvar = '%s_var' % k
                        if kvar in io_map[var_name]:
                            x['vars'].append(io_map[var_name][kvar])
        # Move variables if outputs in inputs
        if outputs_in_inputs:
            if ((((len(inputs) + len(outputs)) == len(info.get('inputs', [])))
                 and (len(info.get('outputs', [])) == 0))):
                for i, vdict in enumerate(info['inputs'][:len(inputs)]):
                    inputs[i].setdefault('vars', [vdict['name']])
                    assert(inputs[i]['vars'] == [vdict['name']])
                for i, vdict in enumerate(info['inputs'][len(inputs):]):
                    outputs[i].setdefault('vars', [vdict['name']])
                    assert(outputs[i]['vars'] == [vdict['name']])
            for x in outputs:
                for i, v in enumerate(x.get('vars', [])):
                    if v in info_map['inputs']:
                        info_map['outputs'][v] = cls.input2output(
                            info_map['inputs'].pop(v))
        for io, io_var in zip(['inputs', 'outputs'], [inputs, outputs]):
            for x in io_var:
                x['channel_name'] = x['name']
                x['channel'] = (x['name'].split(':', 1)[-1]
                                + '_%s_channel' % io[:-1])
                for i, v in enumerate(x.get('vars', [])):
                    if v in info_map[io]:
                        x['vars'][i] = info_map[io][v]
            if (len(io_var) == 1) and info_map.get(io, False):
                io_var[0].setdefault('vars', list(info_map[io].values()))
            for x in io_var:
                if 'vars' not in x:
                    x['vars'] = [copy.deepcopy(x)]
                    x['vars'][0]['name'] = x['name'].split(':', 1)[-1]
                for v in x['vars']:
                    if isinstance(v.get('datatype', None), str):
                        v['datatype'] = {'type': v['datatype']}
                if isinstance(x.get('datatype', None), str):
                    x['datatype'] = {'type': x['datatype']}
            # Check for user defined length variables and add flag to
            # length variables
            for x in io_var:
                for k in ['length', 'shape', 'ndim']:
                    for v in x['vars']:
                        if k + '_var' in v:
                            v[k + '_var'] = info_map[io][v[k + '_var']]
                            # v[k + '_var']['is_' + k + '_var'] = True
                            v[k + '_var']['is_length_var'] = True
                        else:
                            v[k + '_var'] = False
            # Update datatypes
            if cls.is_typed:
                for x in io_var:
                    non_length = []
                    for v in x['vars']:
                        if not v.get('is_length_var', False):
                            non_length.append(v)
                    if ((x.get('datatype', None)
                         and (not is_default_typedef(x['datatype'])))):
                        if (len(non_length) == 1):
                            non_length[0]['datatype'] = x['datatype']
                        else:
                            # TODO: Remove types associated with length?
                            assert(x['datatype']['type'] == 'array')
                            assert(len(x['datatype']['items'])
                                   == len(non_length))
                            for v, t in zip(non_length, x['datatype']['items']):
                                v['datatype'] = t
                    else:
                        if (len(non_length) == 1):
                            x['datatype'] = non_length[0]['datatype']
                        else:
                            x['datatype'] = {
                                'type': 'array',
                                'items': [v['datatype'] for v in non_length]}
                    for v in x['vars']:
                        if 'native_type' not in v:
                            v['native_type'] = cls.get_native_type(**v)
        return flag_var

    @classmethod
    def write_model_wrapper(cls, model_file, model_function,
                            inputs=[], outputs=[],
                            outputs_in_inputs=None, verbose=False,
                            client_comms=[], copies=1, model_name=None):
        r"""Return the lines required to wrap a model function as an integrated
        model.

        Args:
            model_file (str): Full path to the file containing the model
                function's declaration.
            model_function (str): Name of the model function.
            inputs (list, optional): List of model inputs including types.
                Defaults to [].
            outputs (list, optional): List of model outputs including types.
                Defaults to [].
            outputs_in_inputs (bool, optional): If True, the outputs are
                presented in the function definition as inputs. Defaults
                to the class attribute outputs_in_inputs.
            verbose (bool, optional): If True, the contents of the created file
                are displayed. Defaults to False.
            client_comms (list, optional): List of the names of client comms
                that should be removed from the list of outputs. Defaults to [].
            copies (int, optional): Number of times the model driver is
                duplicated. If more than one, no error will be raised in the
                event there is never a call the the function. Defaults to 1.
            model_name (str, optional): Name given to the model. Defaults to
                None.

        Returns:
            list: Lines of code wrapping the provided model with the necessary
                code to run it as part of an integration.

        """
        # TODO: Determine how to encode dependencies on external variables in models
        if cls.function_param is None:
            raise NotImplementedError("function_param attribute not set for"
                                      "language '%s'" % cls.language)
        lines = []
        flag_var = {'name': 'flag', 'datatype': {'type': 'flag'}}
        iter_var = {'name': 'first_iter', 'datatype': {'type': 'flag'}}
        if outputs_in_inputs is None:
            outputs_in_inputs = cls.outputs_in_inputs
        # Replace server input w/ split input/output and remove client
        # connections from inputs
        for i, x in enumerate(inputs):
            if x.get('server_replaces', False):
                inputs[x['server_replaces']['input_index']] = (
                    x['server_replaces']['input'])
                outputs.insert(x['server_replaces']['output_index'],
                               x['server_replaces']['output'])
        outputs = [x for x in outputs if x['name'] not in client_comms]
        if client_comms:
            warnings.warn("When wrapping a model function, client comms "
                          "must either be initialized outside the function, "
                          "pass a 'global_scope' parameter to the "
                          "comm initialization (e.g. Python, R, Matlab), "
                          "or use a 'WITH_GLOBAL_SCOPE' macro "
                          "(e.g. C, C++, Fortran) around the initialization "
                          "so that they are persistent "
                          "across calls and the call or recv/send methods "
                          "must be called explicitly (as opposed to the "
                          "function inputs/outputs which will be handled "
                          "by the wrapper). This model's client comms are:\n"
                          "\t%s" % client_comms)
        # Update types based on the function definition for typed languages
        model_flag = cls.update_io_from_function(
            model_file, model_function,
            inputs=inputs, outputs=outputs,
            outputs_in_inputs=outputs_in_inputs)
        # Declare variables and flag, then define flag
        free_vars = []
        definitions = []
        if 'declare' in cls.function_param:
            for x in inputs + outputs:
                lines += cls.write_channel_decl(
                    x, definitions=definitions,
                    requires_freeing=free_vars)
            lines += cls.write_declaration(flag_var,
                                           definitions=definitions,
                                           requires_freeing=free_vars)
            lines += cls.write_declaration(iter_var,
                                           definitions=definitions,
                                           requires_freeing=free_vars)
            if model_flag:
                lines += cls.write_declaration(
                    model_flag, definitions=definitions,
                    requires_freeing=free_vars)
            for x in inputs + outputs:
                for v in x.get('vars', [x]):
                    lines += cls.write_declaration(
                        v, definitions=definitions,
                        requires_freeing=free_vars)
            lines += definitions
        lines.append(cls.format_function_param(
            'assign', name=flag_var['name'],
            value=cls.function_param.get(
                'true_flag', cls.function_param['true'])))
        lines.append(cls.format_function_param(
            'assign', name=iter_var['name'],
            value=cls.function_param.get(
                'true_flag', cls.function_param['true'])))
        # Declare/define input and output channels
        for x in inputs:
            lines += cls.write_channel_def('input',
                                           requires_freeing=free_vars, **x)
        for x in outputs:
            lines += cls.write_channel_def('output',
                                           requires_freeing=free_vars, **x)
        # Receive inputs before loop
        for x in inputs:
            if x.get('outside_loop', False):
                lines += cls.write_model_recv(x['channel'], x,
                                              flag_var=flag_var)
        # Loop
        loop_lines = []
        # Receive inputs
        any_loop_inputs = False
        loop_iter_var = iter_var
        if copies > 1:
            loop_iter_var = None
        for x in inputs:
            if not x.get('outside_loop', False):
                any_loop_inputs = True
                loop_lines += cls.write_model_recv(x['channel'], x,
                                                   flag_var=flag_var,
                                                   iter_var=loop_iter_var,
                                                   allow_failure=True)
        # Call model
        loop_lines += cls.write_model_function_call(
            model_function, model_flag, inputs, outputs,
            outputs_in_inputs=outputs_in_inputs)
        # Send outputs
        for x in outputs:
            if not x.get('outside_loop', False):
                loop_lines += cls.write_model_send(x['channel'], x,
                                                   flag_var=flag_var)
        loop_lines.append(cls.format_function_param(
            'assign', name=iter_var['name'],
            value=cls.function_param.get('false_flag',
                                         cls.function_param['false'])))
        # Add break if there are not any inputs inside the loop
        if not any_loop_inputs:
            loop_lines.append(cls.format_function_param(
                'assign', name=flag_var['name'],
                value=cls.function_param.get(
                    'false_flag', cls.function_param['false'])))
        # Add loop in while block
        flag_cond = cls.format_function_param('flag_cond',
                                              default='{flag_var}',
                                              flag_var=flag_var['name'])
        lines += cls.write_while_loop(flag_cond, loop_lines)
        # Send outputs after loop
        for x in outputs:
            if x.get('outside_loop', False):
                lines += cls.write_model_send(x['channel'], x,
                                              flag_var=flag_var)
        # Free variables
        for x in free_vars:
            lines += cls.write_free(x)
        # Wrap as executable with interface & model import
        prefix = None
        if 'interface' in cls.function_param:
            ygglib = cls.interface_library
            if ygglib in cls.internal_libraries:
                ygglib = cls.internal_libraries[ygglib]['source']
            if cls.interface_inside_exec:
                lines.insert(0, cls.format_function_param(
                    'interface', interface_library=ygglib))
            else:
                prefix = [cls.format_function_param(
                    'interface', interface_library=ygglib)]
        out = cls.write_executable(lines, prefix=prefix,
                                   model_name=model_name,
                                   imports={'filename': model_file,
                                            'function': model_function})
        if verbose:  # pragma: debug
            logger.info('\n' + '\n'.join(out))
        else:
            logger.debug('\n' + '\n'.join(out))
        return out

    @classmethod
    def write_channel_decl(cls, var, **kwargs):
        r"""Write a channel declaration.

        Args:
            var (dict): Information dictionary for the channel.
                being declared.
            **kwargs: Additional keyword arguments are passed to class's
                write_declaration.

        Returns:
            list: The lines declaring the variable.

        """
        out = []
        if not cls.dont_declare_channel:
            out = cls.write_declaration(
                {'name': var['channel'], 'type': 'comm'}, **kwargs)
        if (((var.get('datatype', None) is not None)
             and ('{channel_type}' in cls.function_param['input']))):
            var['channel_type'] = '%s_type' % var['channel']
            out += cls.write_type_decl(
                var['channel_type'], var['datatype'],
                definitions=kwargs.get('definitions', None),
                requires_freeing=kwargs.get('requires_freeing', None))
        return out

    @classmethod
    def write_type_decl(cls, name, datatype, name_base=None,
                        requires_freeing=None, definitions=None,
                        no_decl=False):
        r"""Get lines declaring the datatype within the language.

        Args:
            name (str): Name of variable that should be declared.
            datatype (dict): Type definition.
            requires_freeing (list, optional): List that variables requiring
                freeing should be appended to. Defaults to None.
            definitions (list, optional): Existing list that variable
                definitions should be added to. Defaults to None if not
                provided and definitions will be included in the returned
                lines.
            no_decl (bool, optional): If True, the variable is not
                declared, but supporting variables will be. Defaults
                to False.

        Returns:
            list: Lines required to define a type declaration.

        """
        out = []
        if name_base is None:
            name_base = name
        if datatype['type'] == 'array':
            if 'items' in datatype:
                assert(isinstance(datatype['items'], list))
                out += cls.write_declaration(
                    {'name': '%s_items' % name_base,
                     'datatype': {
                         'type': '1darray', 'subtype': 'dtype',
                         'length': len(datatype['items'])}},
                    definitions=definitions,
                    requires_freeing=requires_freeing)
                for i, x in enumerate(datatype['items']):
                    # Prevent recusion
                    x_copy = copy.deepcopy(x)
                    x_copy.pop('items', None)
                    x_copy.pop('properties', None)
                    out += cls.write_type_decl(
                        None, x_copy,
                        name_base=('%s_item%d' % (name_base, i)),
                        definitions=definitions,
                        requires_freeing=requires_freeing,
                        no_decl=True)
        elif datatype['type'] == 'object':
            if 'properties' in datatype:
                assert(isinstance(datatype['properties'], dict))
                precision = 0
                if datatype['properties']:
                    precision = max([len(k) for k in
                                     datatype['properties'].keys()])
                precision = max(80, precision)
                out += cls.write_declaration(
                    {'name': '%s_keys' % name_base,
                     'datatype': {
                         'type': '1darray', 'subtype': 'bytes',
                         'length': len(datatype['properties']),
                         'precision': precision}},
                    definitions=definitions,
                    requires_freeing=requires_freeing)
                out += cls.write_declaration(
                    {'name': '%s_vals' % name_base,
                     'datatype': {
                         'type': '1darray', 'subtype': 'dtype',
                         'length': len(datatype['properties'])}},
                    definitions=definitions,
                    requires_freeing=requires_freeing)
                for i, (k, v) in enumerate(datatype['properties'].items()):
                    # Prevent recusion
                    v_copy = copy.deepcopy(v)
                    v_copy.pop('items', None)
                    v_copy.pop('properties', None)
                    out += cls.write_type_decl(
                        None, v_copy,
                        name_base=('%s_prop%d' % (name_base, i)),
                        requires_freeing=requires_freeing,
                        definitions=definitions,
                        no_decl=True)
        elif datatype['type'] == 'ndarray':
            if 'shape' in datatype:
                out += cls.write_declaration(
                    {'name': '%s_shape' % name_base,
                     'datatype': {
                         'type': '1darray', 'subtype': 'int',
                         'precision': 64, 'length': len(datatype['shape'])}},
                    definitions=definitions,
                    requires_freeing=requires_freeing)
        elif datatype['type'] in ['ply', 'obj', '1darray',
                                  'scalar', 'boolean', 'null',
                                  'number', 'integer', 'string',
                                  'class', 'function', 'instance',
                                  'schema', 'any'] + list(_valid_types.keys()):
            pass
        else:  # pragma: debug
            raise ValueError(("Cannot create %s version of type "
                              "'%s'") % (cls.language, datatype['type']))
        if not no_decl:
            out += cls.write_declaration(
                {'name': name, 'type': 'dtype'})
        return out

    @classmethod
    def write_type_def(cls, name, datatype, name_base=None,
                       use_generic=False):
        r"""Get lines declaring the data type within the language.

        Args:
            name (str): Name of variable that definition should be stored in.
            datatype (dict): Type definition.
            use_generic (bool, optional): If True variables serialized
                and/or deserialized by the type will be assumed to be
                generic objects. Defaults to False.

        Returns:
            list: Lines required to define a type definition.

        """
        out = []
        fmt = None
        keys = {}
        if use_generic:
            keys['use_generic'] = cls.function_param['true']
        else:
            keys['use_generic'] = cls.function_param['false']
        typename = datatype['type']
        if name_base is None:
            name_base = name
        if datatype['type'] == 'array':
            if 'items' in datatype:
                assert(isinstance(datatype['items'], list))
                keys['nitems'] = len(datatype['items'])
                keys['items'] = '%s_items' % name_base
                if cls.zero_based:
                    idx_offset = 0
                else:
                    idx_offset = 1
                for i, x in enumerate(datatype['items']):
                    # Prevent recusion
                    x_copy = copy.deepcopy(x)
                    x_copy.pop('items', None)
                    x_copy.pop('properties', None)
                    out += cls.write_type_def(
                        cls.format_function_param(
                            'index', variable=keys['items'],
                            index=(i + idx_offset)), x_copy,
                        name_base=('%s_item%d' % (name_base, i)),
                        use_generic=use_generic)
            else:
                keys['nitems'] = 0
                keys['items'] = cls.function_param['null']
                keys['use_generic'] = cls.function_param['true']
        elif datatype['type'] == 'object':
            keys['use_generic'] = cls.function_param['true']
            if 'properties' in datatype:
                assert(isinstance(datatype['properties'], dict))
                keys['nitems'] = len(datatype['properties'])
                keys['keys'] = '%s_keys' % name_base
                keys['values'] = '%s_vals' % name_base
                if cls.zero_based:
                    idx_offset = 0
                else:
                    idx_offset = 1
                for i, (k, v) in enumerate(datatype['properties'].items()):
                    # Prevent recusion
                    v_copy = copy.deepcopy(v)
                    v_copy.pop('items', None)
                    v_copy.pop('properties', None)
                    out.append(cls.format_function_param(
                        'assign', value='\"%s\"' % k,
                        name=cls.format_function_param(
                            'index', variable=keys['keys'],
                            index=(i + idx_offset))))
                    out += cls.write_type_def(
                        cls.format_function_param(
                            'index', variable=keys['values'],
                            index=(i + idx_offset)), v_copy,
                        name_base=('%s_prop%d' % (name_base, i)),
                        use_generic=use_generic)
            else:
                keys['nitems'] = 0
                keys['keys'] = cls.function_param['null']
                keys['values'] = cls.function_param['null']
        elif datatype['type'] in ['ply', 'obj']:
            pass
        elif datatype['type'] == '1darray':
            for k in ['subtype', 'precision']:
                keys[k] = datatype[k]
            keys['precision'] = int(keys['precision'])
            keys['length'] = datatype.get('length', '0')
            keys['units'] = datatype.get('units', '')
        elif datatype['type'] == 'ndarray':
            for k in ['subtype', 'precision']:
                keys[k] = datatype[k]
            keys['precision'] = int(keys['precision'])
            if 'shape' in datatype:
                shape_var = '%s_shape' % name_base
                if cls.zero_based:
                    idx_offset = 0
                else:
                    idx_offset = 1
                for i, x in enumerate(datatype['shape']):
                    out.append(cls.format_function_param(
                        'assign', value=x,
                        name=cls.format_function_param(
                            'index', variable=shape_var,
                            index=(i + idx_offset))))
                keys['ndim'] = len(datatype['shape'])
                keys['shape'] = shape_var
                typename = 'ndarray_arr'
            else:
                keys['ndim'] = 0
                keys['shape'] = cls.function_param['null']
            keys['units'] = datatype.get('units', '')
        elif (typename == 'scalar') or (typename in _valid_types):
            keys['subtype'] = datatype.get('subtype', datatype['type'])
            keys['units'] = datatype.get('units', '')
            if keys['subtype'] in ['bytes', 'string', 'unicode']:
                keys['precision'] = int(datatype.get('precision', 0))
            else:
                keys['precision'] = int(datatype['precision'])
            typename = 'scalar'
        elif datatype['type'] in ['boolean', 'null', 'number',
                                  'integer', 'string']:
            keys['type'] = datatype['type']
            typename = 'default'
        elif (typename in ['class', 'function']):
            keys['type'] = typename
            typename = 'pyobj'
        elif typename in ['instance', 'any']:
            keys['use_generic'] = cls.function_param['true']
            typename = 'empty'
        elif typename in ['schema']:
            keys['use_generic'] = cls.function_param['true']
        else:  # pragma: debug
            raise ValueError("Cannot create %s version of type '%s'"
                             % (cls.language, typename))
        fmt = cls.format_function_param('init_type_%s' % typename, **keys)
        out.append(cls.format_function_param('assign', name=name,
                                             value=fmt))
        return out

    @classmethod
    def write_channel_def(cls, key, datatype=None, **kwargs):
        r"""Write an channel definition.

        Args:
            key (str): Entry in cls.function_param that should be used.
            datatype (dict, optional): Data type associated with the channel.
                Defaults to None and is ignored.
            **kwargs: Additional keyword arguments are passed as parameters
                to format_function_param.

        Returns:
            list: Lines required to declare and define an output channel.

        """
        out = []
        if (datatype is not None) and ('{channel_type}' in cls.function_param[key]):
            kwargs['channel_type'] = '%s_type' % kwargs['channel']
            out += cls.write_type_def(
                kwargs['channel_type'], datatype,
                use_generic=kwargs.get('use_generic', False))
        dir_map = {'input': 'recv', 'output': 'send'}
        try_keys = [dir_map[key] + '_converter', 'transform']
        try_vals = []
        if all([bool(kwargs.get(k, False)) for k in try_keys]):  # pragma: debug
            # TODO: Handling merger of the transforms in yaml or
            # remove the *_converter options entirely
            raise RuntimeError(("Transforms are specified in multiple "
                                "locations for this input: %s")
                               % str(try_keys))
        for k in try_keys:
            if k in kwargs:
                v = kwargs[k]
                if not isinstance(v, list):
                    v = [v]
                try_vals += v
        # This last transform is used because the others are assumed
        # to be applied by the connection driver
        if try_vals and isinstance(try_vals[-1], str):
            try_key = '%s_%s' % (try_vals[-1], key)
            if ((('python_interface' in cls.function_param)
                 and (try_key in cls.python_interface))):
                kwargs['python_interface'] = cls.python_interface[try_key]
                if ((('format_str' in kwargs)
                     and ('python_interface_format' in cls.function_param))):
                    key = 'python_interface_format'
                    kwargs['format_str'] = kwargs['format_str'].encode(
                        "unicode_escape").decode('utf-8')
                else:
                    key = 'python_interface'
        out += [cls.format_function_param(key, **kwargs)]
        return out

    @classmethod
    def write_model_function_call(cls, model_function, flag_var, inputs, outputs,
                                  outputs_in_inputs=None, on_failure=None,
                                  format_not_flag_cond=None, format_flag_cond=None):
        r"""Write lines necessary to call the model function.

        Args:
            model_function (str): Handle of the model function that should be
                called.
            flag_var (str): Name of variable that should be used as a flag.
            inputs (list): List of dictionaries describing inputs to the model.
            outputs (list): List of dictionaries describing outputs from the model.
            outputs_in_inputs (bool, optional): If True, the outputs are
                presented in the function definition as inputs. Defaults
                to the class attribute outputs_in_inputs.
            on_failure (list, optional): Lines to be executed if the model
                call fails. Defaults to an error message. This variable
                is only used if flag_var is not None and outputs_in_inputs
                is True.
            format_not_flag_cond (str, optional): Format string that produces
                a conditional expression that evaluates to False when the
                model flag indicates a failure. Defaults to None and the
                class's value for 'not_flag_cond' in function_param is used
                if it exists. If it does not exist, format_flag_cond is used.
            format_flag_cond (str, optional): Format string that produces
                a conditional expression that evaluates to True when the
                model flag indicates a success. Defaults to None and the
                defaults class's value for 'flag_cond' in function_param is
                used if it exists. If it does not exist, the flag is
                directly evaluated as if it were a boolean.

checking if the model flag indicates
                a failure

        Returns:
            list: Lines required to carry out a call to a model function in
                this language.

        """
        if outputs_in_inputs is None:  # pragma: debug
            outputs_in_inputs = cls.outputs_in_inputs
        func_inputs = cls.channels2vars(inputs)
        func_outputs = cls.channels2vars(outputs)
        if isinstance(flag_var, dict):
            flag_var = flag_var['name']
        out = cls.write_function_call(
            model_function, inputs=func_inputs, outputs=func_outputs,
            flag_var=flag_var, outputs_in_inputs=outputs_in_inputs)
        if flag_var and outputs_in_inputs:
            if (not format_flag_cond) and ('not_flag_cond' in cls.function_param):
                flag_cond = cls.format_function_param(
                    'not_flag_cond', flag_var=flag_var,
                    replacement=format_not_flag_cond)
            else:  # pragma: debug
                # flag_cond = '%s (%s)' % (
                #     cls.function_param['not'],
                #     cls.format_function_param(
                #         'flag_cond', default='{flag_var}', flag_var=flag_var,
                #         replacement=format_flag_cond))
                raise RuntimeError("Untested code below. Uncomment "
                                   "at your own risk if you find "
                                   "use case for it.")
            if on_failure is None:
                on_failure = [cls.format_function_param(
                    'error', error_msg="Model call failed.")]
            out += cls.write_if_block(flag_cond, on_failure)
        return out

    @classmethod
    def write_model_recv(cls, channel, recv_var, flag_var='flag',
                         iter_var=None, allow_failure=False,
                         alt_recv_function=None):
        r"""Write a model receive call include checking the return flag.

        Args:
            channel (str): Name of variable that the channel being received from
                was stored in.
            recv_var (dict, list): Information of one or more variables that
                receieved information should be stored in.
            flag_var (str, optional): Name of flag variable that the flag should
                be stored in. Defaults to 'flag',
            iter_var (str, optional): Name of flag signifying when the
                model is in it's first iteration. If allow_failure is
                True and iter_var is provided, an error will be raised
                if iter_var is True. Defaults to None.
            allow_failure (bool, optional): If True, the returned lines will
                call a break if the flag is False. Otherwise, the returned
                lines will issue an error. Defaults to False.
            alt_recv_function (str, optional): Alternate receive function
                format string. Defaults to None and is ignored.

        Returns:
            list: Lines required to carry out a receive call in this language.

        """
        if cls.function_param is None:
            raise NotImplementedError("function_param attribute not set for"
                                      "language '%s'" % cls.language)
        recv_var_str = recv_var
        if not isinstance(recv_var, str):
            recv_var_par = cls.channels2vars(recv_var)
            recv_var_str = cls.prepare_output_variables(
                recv_var_par, in_inputs=cls.outputs_in_inputs,
                for_yggdrasil=True)
        else:
            recv_var_par = cls.split_variables(recv_var_str)
        expanded_recv_var = None
        if (len(recv_var_par) > 1) and ('multiple_outputs' in cls.function_param):
            expanded_recv_var = recv_var_str
            recv_var_str = 'temp_%s' % recv_var_par[0]['name']
        if isinstance(flag_var, dict):
            flag_var = flag_var['name']
        if isinstance(iter_var, dict):
            iter_var = iter_var['name']
        if cls.outputs_in_inputs:
            inputs = [recv_var_str]
            outputs = [flag_var]
        else:
            inputs = []
            outputs = [flag_var, recv_var_str]
        if cls.include_channel_obj:
            inputs.insert(0, channel)
        lines = cls.write_function_call(
            cls.format_function_param('recv_function', channel=channel,
                                      replacement=alt_recv_function),
            inputs=inputs, outputs=outputs, include_arg_count=cls.include_arg_count)
        if 'not_flag_cond' in cls.function_param:
            flag_cond = cls.format_function_param('not_flag_cond',
                                                  flag_var=flag_var)
        else:
            flag_cond = '%s (%s)' % (
                cls.function_param['not'],
                cls.format_function_param('flag_cond', default='{flag_var}',
                                          flag_var=flag_var))
        fail_message = cls.escape_quotes(
            "Could not receive %s." % recv_var_str)
        if allow_failure:
            fail_message = cls.escape_quotes(
                'End of input from %s.' % recv_var_str)
            if_block = [cls.format_function_param('print', message=fail_message),
                        cls.function_param.get('break', 'break')]
            if iter_var is not None:
                if_block = cls.write_if_block(
                    iter_var,
                    [cls.format_function_param(
                        'error', error_msg=cls.escape_quotes(
                            'No input from %s.' % recv_var_str))],
                    if_block)
        else:
            if_block = [cls.format_function_param('error', error_msg=fail_message)]
        lines += cls.write_if_block(flag_cond, if_block)
        # Check if single element should be expanded
        if expanded_recv_var:
            # lines.append(cls.format_function_param(
            #     'print_generic', object=recv_var_str))
            if 'expand_mult' in cls.function_param:  # pragma: matlab
                lines.append(cls.format_function_param(
                    'expand_mult', name=expanded_recv_var, value=recv_var_str))
            elif 'assign_mult' in cls.function_param:
                lines.append(cls.format_function_param(
                    'assign_mult', name=expanded_recv_var, value=recv_var_str))
            else:
                lines.append(cls.format_function_param(
                    'assign', name=expanded_recv_var, value=recv_var_str))
        elif len(recv_var_par) == 1:
            lines += cls.write_expand_single_element(recv_var_str)
        return lines
    
    @classmethod
    def write_model_send(cls, channel, send_var, flag_var='flag',
                         allow_failure=False):
        r"""Write a model send call include checking the return flag.

        Args:
            channel (str): Name of variable that the channel being sent to
                was stored in.
            send_var (dict, list): Information on one or more variables
                containing information that will be sent.
            flag_var (str, optional): Name of flag variable that the flag should
                be stored in. Defaults to 'flag',
            allow_failure (bool, optional): If True, the returned lines will
                call a break if the flag is False. Otherwise, the returned
                lines will issue an error. Defaults to False.

        Returns:
            list: Lines required to carry out a send call in this language.

        """
        if cls.function_param is None:
            raise NotImplementedError("function_param attribute not set for"
                                      "language '%s'" % cls.language)
        send_var_str = send_var
        if not isinstance(send_var_str, str):
            send_var_par = cls.channels2vars(send_var)
            send_var_str = cls.prepare_input_variables(
                send_var_par, for_yggdrasil=True)
        if isinstance(flag_var, dict):
            flag_var = flag_var['name']
        if cls.include_channel_obj:
            send_var_str = [channel, send_var_str]
        lines = cls.write_function_call(
            cls.format_function_param('send_function', channel=channel),
            inputs=send_var_str,
            outputs=flag_var, include_arg_count=cls.include_arg_count)
        flag_cond = '%s (%s)' % (
            cls.function_param['not'],
            cls.format_function_param('flag_cond', default='{flag_var}',
                                      flag_var=flag_var))
        fail_message = cls.escape_quotes(
            "Could not send %s." % send_var_str)
        if allow_failure:  # pragma: no cover
            # This is not particularly useful, but is included for completion
            if_block = [cls.format_function_param('print', message=fail_message),
                        cls.function_param.get('break', 'break')]
        else:
            if_block = [cls.format_function_param('error', error_msg=fail_message)]
        lines += cls.write_if_block(flag_cond, if_block)
        return lines

    @classmethod
    def write_print_var(cls, var, prefix_msg=None):
        r"""Get the lines necessary to print a variable in this language.

        Args:
            var (dict): Variable information.
            prefix_msg (str, optional): Message that should be printed
                before the variable. Defaults to None and is ignored.

        Returns:
            list: Lines printing the specified variable.

        """
        out = []
        print_key = None
        varname = var
        if isinstance(var, dict):
            varname = var['name']
            typename = var.get(
                'datatype',
                {'type': var.get('type', None)}).get('type', None)
            if ('print_%s' % typename) in cls.function_param:
                print_key = ('print_%s' % typename)
            elif 'print_generic' in cls.function_param:
                print_key = 'print_generic'
        elif 'print_generic' in cls.function_param:
            print_key = 'print_generic'
        if print_key:
            if prefix_msg is not None:
                out.append(cls.format_function_param(
                    'print', message=prefix_msg))
            out += [cls.format_function_param(
                print_key, object=varname)]
        return out

    @classmethod
    def write_print_input_var(cls, var, **kwargs):
        r"""Get the lines necessary to print an input variable in this
        language.

        Args:
            var (dict): Variable information.
            **kwargs: Additional keyword arguments are passed to write_print_var.

        Returns:
            list: Lines printing the specified variable.

        """
        return cls.write_print_var(var, **kwargs)
        
    @classmethod
    def write_print_output_var(cls, var, in_inputs=False, **kwargs):
        r"""Get the lines necessary to print an output variable in this
        language.

        Args:
            var (dict): Variable information.
            in_inputs (bool, optional): If True, the output variable
                is passed in as an input variable to be populated.
                Defaults to False.
            **kwargs: Additional keyword arguments are passed to write_print_var.

        Returns:
            list: Lines printing the specified variable.

        """
        return cls.write_print_var(var, **kwargs)
        
    @classmethod
    def write_function_def(cls, function_name, inputs=[], outputs=[],
                           input_var=None, output_var=None,
                           function_contents=[],
                           outputs_in_inputs=False,
                           opening_msg=None, closing_msg=None,
                           print_inputs=False, print_outputs=False,
                           skip_interface=False, function_keys=None,
                           verbose=False, **kwargs):
        r"""Write a function definition.

        Args:
            function_name (str): Name fo the function being defined.
            inputs (list, optional): List of inputs to the function.
                Defaults to []. Ignored if input_var provided.
            outputs (list, optional): List of outputs from the function.
                Defaults to []. If not provided, no return call is
                added to the function body. Ignored if output_var
                provided.
            input_var (str, optional): Full string specifying input in
                the function definition. If not provided, this will be
                created based on the contents of the inputs variable.
            output_var (str, optional): Full string specifying output in
                the function definition. If not provided, this will be
                created based on the contents of the outputs variable.
            function_contents (list, optional): List of lines comprising
                the body of the function. Defaults to [].
            outputs_in_inputs (bool, optional): If True, the outputs are
                presented in the function definition as inputs. Defaults
                to False.
            opening_msg (str, optional): String that should be printed
                before the function contents (and inputs if print_inputs
                is True). Defaults to None and is ignored.
            closing_msg (str, optional): String that should be printed
                after the function contents (and outputs if print_outputs
                is True). Defaults to None and is ignored.
            print_inputs (bool, optional): If True, the input variables
                will be printed before the function contents. Defaults
                to False.
            print_outputs (bool, optional): If True, the output variables
                will be printed after the function contents. Defaults to
                False.
            skip_interface (bool, optional): If True, the line including
                the interface will be skipped. Defaults to False.
            function_keys (tuple, optional): 2 element tuple that
                specifies the keys for the function_param entries that
                should be used to begin & end a function definition.
                Defaults to ('function_def_begin', function_def_end').
            verbose (bool, optional): If True, the contents of the created file
                are displayed. Defaults to False.
            **kwargs: Additional keyword arguments are passed to
                cls.format_function_param.

        Returns:
            list: Lines completing the function call.

        Raises:
            NotImplementedError: If the function_param attribute for the
                class is not defined.

        """
        if cls.function_param is None:
            raise NotImplementedError("function_param attribute not set for"
                                      "language '%s'" % cls.language)
        if function_keys is None:
            function_keys = ('function_def_begin', 'function_def_end')
        out = []
        interface_lines = []
        if ('interface' in cls.function_param) and (not skip_interface):
            ygglib = cls.interface_library
            if ygglib in cls.internal_libraries:
                ygglib = cls.internal_libraries[ygglib]['source']
            interface_lines.append(cls.format_function_param(
                'interface', interface_library=ygglib))
        if not cls.interface_inside_exec:
            out += interface_lines
        flag_var = {}
        if input_var is None:
            input_var = cls.prepare_input_variables(
                inputs, in_definition=True)
        if output_var is None:
            output_var = cls.prepare_output_variables(
                outputs, in_inputs=outputs_in_inputs, in_definition=True)
        print_input_lines = []
        if print_inputs and inputs:
            for x in inputs:
                print_input_lines += cls.write_print_input_var(
                    x, prefix_msg=('INPUT[%s]:' % x['name']))
        print_output_lines = []
        if print_outputs and outputs:
            for x in outputs:
                print_output_lines += cls.write_print_output_var(
                    x, prefix_msg=('OUTPUT[%s]:' % x['name']),
                    in_inputs=outputs_in_inputs)
        old_outputs = []
        if outputs_in_inputs:
            if output_var:
                input_var = cls.prepare_input_variables(
                    [input_var, output_var])
            flag_var = kwargs.get('flag_var', 'flag')
            if isinstance(flag_var, str):
                flag_var = {'name': flag_var}
            flag_var.setdefault('datatype', 'flag')
            flag_var.setdefault('value', cls.function_param.get(
                'true_flag', cls.function_param['true']))
            old_outputs = outputs
            outputs = [flag_var]
            output_var = cls.prepare_output_variables(outputs)
        out.append(cls.format_function_param(
            function_keys[0], function_name=function_name,
            input_var=input_var, output_var=output_var, **kwargs))
        if cls.interface_inside_exec:
            out += [cls.function_param['indent'] + x
                    for x in interface_lines]
        free_vars = []
        if 'declare' in cls.function_param:
            definitions = []
            if not cls.types_in_funcdef:
                for o in (inputs + old_outputs):
                    out += [cls.function_param['indent'] + x for
                            x in cls.write_declaration(
                                o, definitions=definitions,
                                requires_freeing=free_vars,
                                dont_define=True)]
            for o in outputs:
                out += [cls.function_param['indent'] + x for
                        x in cls.write_declaration(
                            o, definitions=definitions,
                            requires_freeing=free_vars)]
            out += [cls.function_param['indent'] + x
                    for x in definitions]
        if outputs_in_inputs:
            out.append(cls.function_param['indent']
                       + cls.format_function_param(
                           'assign', **flag_var))
        if opening_msg:
            out.append(cls.function_param['indent']
                       + cls.format_function_param(
                           'print', message=opening_msg))
        if print_inputs:
            for x in print_input_lines:
                out.append(cls.function_param['indent'] + x)
        for x in function_contents:
            out.append(cls.function_param['indent'] + x)
        if print_outputs:
            for x in print_output_lines:
                out.append(cls.function_param['indent'] + x)
        if closing_msg:
            out.append(cls.function_param['indent']
                       + cls.format_function_param(
                           'print', message=closing_msg))
        # This is not currently used by the tests, but may be
        # needed in the future
        assert(not free_vars)
        # for x in free_vars:
        #     out += [cls.function_param['indent'] + line
        #             for line in cls.write_free(x)]
        if output_var and ('return' in cls.function_param):
            out.append(cls.function_param['indent']
                       + cls.format_function_param(
                           'return', output_var=output_var))
        if function_keys[1] in cls.function_param:
            out.append(cls.format_function_param(
                function_keys[1], function_name=function_name))
        else:
            out.append(cls.function_param.get('block_end', ''))
        if verbose:  # pragma: debug
            logger.info('\n' + '\n'.join(out))
        else:
            logger.debug('\n' + '\n'.join(out))
        return out

    @classmethod
    def write_function_call(cls, function_name, inputs=[], outputs=[],
                            include_arg_count=False,
                            outputs_in_inputs=False, **kwargs):
        r"""Write a function call.

        Args:
            function_name (str): Name of the function being called.
            inputs (list, optional): List of inputs to the function.
                Defaults to [].
            outputs (list, optional): List of outputs from the function.
                Defaults to [].
            include_arg_count (bool, optional): If True, the count of input
                arguments is included as the first argument. Defaults to
                False.
            outputs_in_inputs (bool, optional): If True, the outputs are
                presented in the function definition as inputs. Defaults
                to False.
            **kwargs: Additional keyword arguments are passed to
                cls.format_function_param.

        Returns:
            list: Lines completing the function call.

        """
        if outputs_in_inputs:
            inputs = inputs + [cls.prepare_output_variables(
                outputs, in_inputs=outputs_in_inputs)]
            flag_var = kwargs.get('flag_var', None)
            if (flag_var is None) and ('function_call_noout' not in cls.function_param):
                flag_var = 'flag'
            outputs = []
            if flag_var:
                outputs.append(flag_var)
        kwargs.setdefault('input_var', cls.prepare_input_variables(inputs))
        kwargs.setdefault('output_var', cls.prepare_output_variables(outputs))
        nout = len(cls.split_variables(kwargs['output_var']))
        if include_arg_count:
            narg = len(cls.split_variables(kwargs['input_var']))
            kwargs['input_var'] = cls.prepare_input_variables(
                [str(narg), kwargs['input_var']])
        if (nout == 0) and ('function_call_noout' in cls.function_param):
            call_str = cls.format_function_param(
                'function_call_noout', function_name=function_name, **kwargs)
        else:
            call_str = cls.format_function_param(
                'function_call', default='{function_name}({input_var})',
                function_name=function_name, **kwargs)
        if nout == 0:
            out = [call_str + cls.function_param.get('line_end', '')]
        elif (nout > 1) and ('assign_mult' in cls.function_param):
            out = [cls.format_function_param(
                'assign_mult', name=kwargs['output_var'], value=call_str)]
        else:
            out = [cls.format_function_param(
                'assign', name=kwargs['output_var'], value=call_str)]
        return out
        
    @classmethod
    def write_executable_import(cls, model_name=None, **kwargs):
        r"""Add import statements to executable lines.
       
        Args:
            **kwargs: Keyword arguments for import statement.

        Returns:
            list: Lines required to complete the import.
 
        """
        # This code is currently unused, but may be needed in the
        # future to import a dependency directly
        # if ('filename' not in kwargs) and ('import_nofile' in cls.function_param):
        #     key = 'import_nofile'
        # else:
        #     key = 'import'
        # return [cls.format_function_param(key, **kwargs)]
        out = []
        if 'import' in cls.function_param:
            out = [cls.format_function_param('import', **kwargs)]
        return out

    @classmethod
    def write_executable(cls, lines, prefix=None, suffix=None,
                         function_definitions=None, imports=None,
                         model_name=None):
        r"""Return the lines required to complete a program that will run
        the provided lines.

        Args:
            lines (list): Lines of code to be wrapped as an executable.
            prefix (list, optional): Lines of code that should proceed the
                wrapped code. Defaults to None and is ignored. (e.g. C/C++
                include statements).
            suffix (list, optional): Lines of code that should follow the
                wrapped code. Defaults to None and is ignored.
            function_definitions (list, optional): Lines of code defining
                functions that will beused by the code contained in lines.
                Defaults to None and is ignored.
            imports (list, optional): Kwargs for packages that should
                be imported for use by the executable. Defaults to
                None and is ignored.
            model_name (str, optional): Name given to the model. Defaults to
                None.

        Returns:
            lines: Lines of code wrapping the provided lines with the
                necessary code to run it as an executable (e.g. C/C++'s main).

        """
        if cls.function_param is None:
            raise NotImplementedError("function_param attribute not set for"
                                      "language '%s'" % cls.language)
        out = []
        # Add imports
        if imports is not None:
            if not isinstance(imports, list):
                imports = [imports]
            import_lines = []
            for kws in imports:
                import_lines += cls.write_executable_import(**kws)
            if prefix is None:
                prefix = []
            prefix += import_lines
        # Add standard & user defined prefixes
        if ((('exec_prefix' in cls.function_param)
             and (cls.function_param['exec_prefix'] not in lines))):
            out.append(cls.function_param['exec_prefix'])
            out.append('')
        if prefix is not None:
            if not isinstance(prefix, (list, tuple)):
                prefix = [prefix]
            out += prefix
            out.append('')
        if (((not cls.function_param.get('functions_defined_last', False))
             and (function_definitions is not None))):
            out += function_definitions
            out.append('')
        # Add code with begin/end book ends
        if ((('exec_begin' in cls.function_param)
             and (cls.function_param['exec_begin'] not in '\n'.join(lines)))):
            out.append(cls.function_param['exec_begin'])
            if not isinstance(lines, (list, tuple)):
                lines = [lines]
            for x in lines:
                out.append(cls.function_param['indent'] + x)
            out.append(cls.function_param.get('exec_end',
                                              cls.function_param.get(
                                                  'block_end', '')))
        else:
            out += lines
        if out[-1]:
            out.append('')
        # Add standard & user defined suffixes
        if suffix is not None:
            if not isinstance(suffix, (list, tuple)):
                suffix = [suffix]
            out += suffix
            out.append('')
        if ((('exec_suffix' in cls.function_param)
             and (cls.function_param['exec_suffix'] not in lines))):
            out.append(cls.function_param['exec_suffix'])
            out.append('')
        if (((cls.function_param.get('functions_defined_last', False))
             and (function_definitions is not None))):  # pragma: matlab
            out += function_definitions
            out.append('')
        if cls.max_line_width:
            new_out = []
            for iout in out:
                new_out += cls.split_line(iout)
            out = new_out
        return out

    @classmethod
    def escape_quotes(cls, x):
        r"""Escape quotes in a string.

        Args:
           x (str): String to escape quotes in.

        Returns:
           str: x with escaped quotes.

        """
        out = x.replace('"', '\\\"')
        out = out.replace("'", "\\\'")
        return out

    @classmethod
    def split_line(cls, line, length=None, force_split=False):
        r"""Split a line as close to (or before) a given character as
        possible.

        Args:
            line (str): Line to split.
            length (int, optional): Maximum length of split lines. Defaults
                to cls.max_line_width if not provided.
            force_split (bool, optional): If True, force a split to
                occur at the specified length. Defauts to False.

        Returns:
            list: Set of lines resulting from spliting the provided line.

        """
        out = []
        if not line.lstrip():
            return [line]
        nindent = line.index(line.lstrip()[0])
        block_end = cls.function_param['block_end'].lower()
        if '\n' in line:
            out = line.split('\n')
            for i in range(1, len(out)):
                if out[i].lstrip().lower().startswith(block_end):
                    nindent -= len(cls.function_param['indent'])
                out[i] = (nindent * ' ') + out[i]
            new_out = []
            for x in out:
                new_out += cls.split_line(x, length=length,
                                          force_split=force_split)
            return new_out
        if length is None:
            length = cls.max_line_width
        if (length is None) or (len(line) < length):
            return [line]
        length_allow = (length - len(cls.function_param.get(
            'continuation_before', '')))
        if force_split:
            isplit = length_allow
        else:
            isplit = line[:length_allow].rindex(' ') + 1
        if (isplit < nindent + 1) or (isplit >= len(line)):
            out = [line]
        else:
            out.append(line[:isplit] + cls.function_param.get(
                'continuation_before', ''))
            out += cls.split_line(
                ((nindent * ' ') + cls.function_param.get(
                    'continuation_after', '') + line[isplit:]),
                length=length, force_split=force_split)
        return out

    @classmethod
    def input2output(cls, var):
        r"""Perform conversion necessary to turn a variable extracted from a
        function definition from an input to an output.

        Args:
            var (dict): Variable definition.

        Returns:
            dict: Updated variable definition.

        """
        return var

    @classmethod
    def output2input(cls, var, in_definition=True):
        r"""Perform conversion necessary to turn an output variable
        into an corresponding input that can be used to format a
        function definition.

        Args:
            var (dict): Variable definition.
            in_definition (bool, optional): If True, the returned
                dictionary corresponds to an input variable in a
                function definition. If False, the returned value
                will correspond to an input to a function. Defaults to
                True.

        Returns:
            dict: Updated variable definition.

        """
        return var

    @classmethod
    def get_native_type(cls, **kwargs):
        r"""Get the native type.

        Args:
            type (str, optional): Name of |yggdrasil| extended JSON
                type or JSONSchema dictionary defining a datatype.
            **kwargs: Additional keyword arguments may be used in determining
                the precise declaration that should be used.

        Returns:
            str: The native type.

        """
        if 'native_type' in kwargs:
            return kwargs['native_type']
        assert('json_type' not in kwargs)
        json_type = kwargs.get('datatype', kwargs.get('type', 'bytes'))
        if isinstance(json_type, dict):
            type_name = json_type['type']
            if type_name == 'scalar':
                type_name = json_type['subtype']
        else:
            type_name = json_type
        if (type_name == 'flag') and (type_name not in cls.type_map):
            type_name = 'boolean'
        return cls.type_map[type_name]

    @classmethod
    def get_json_type(cls, native_type):
        r"""Get the JSON type from the native language type.

        Args:
            native_type (str): The native language type.

        Returns:
            str, dict: The JSON type.

        """
        return cls.get_inverse_type_map()[native_type]
    
    @classmethod
    def write_declaration(cls, var, value=None, requires_freeing=None,
                          definitions=None, dont_define=False):
        r"""Return the lines required to declare a variable with a certain
        type.

        Args:
            var (dict, str): Name or information dictionary for the variable
                being declared.
            value (str, optional): Value that should be assigned to the
                variable after it is declared.
            requires_freeing (list, optional): Existing list that variables
                requiring freeing should be appended to. Defaults to None
                and is ignored.
            definitions (list, optional): Existing list that variable
                definitions should be added to. Defaults to None if not
                provided and definitions will be included in the returned
                lines.
            dont_define (bool, optional): If True, the variable will not
                be defined. Defaults to False.

        Returns:
            list: The lines declaring the variable.

        """
        if isinstance(var, str):  # pragma: no cover
            var = {'name': var}
        type_name = cls.get_native_type(**var)
        out = [cls.format_function_param('declare',
                                         type_name=type_name,
                                         variable=cls.get_name_declare(var))]
        if dont_define:
            return out
        if definitions is None:
            definitions = out
        if (value is None) and isinstance(var.get('datatype', False), dict):
            init_type = 'init_%s' % var['datatype']['type']
            free_type = 'free_%s' % var['datatype']['type']
            if init_type in cls.function_param:
                assert(free_type in cls.function_param)
                value = cls.function_param[init_type]
                if requires_freeing is not None:
                    requires_freeing.append(var)
        if value is not None:
            definitions.append(cls.format_function_param(
                'assign', name=var['name'], value=value))
        return out

    @classmethod
    def get_name_declare(cls, var):
        r"""Determine the name that should be used for declaration.

        Args:
            var (str, dict): Name of variable or dictionary of information.

        Returns:
            str: Modified name for declaration.

        """
        if isinstance(var, str):  # pragma: no cover
            return var
        assert(isinstance(var, dict))
        out = var['name']
        return out
    
    @classmethod
    def write_free(cls, var, **kwargs):
        r"""Return the lines required to free a variable with a certain type.

        Args:
            var (dict, str): Name or information dictionary for the variable
                being declared.
            **kwargs: Additional keyword arguments are passed to format_function_param.

        Returns:
            list: The lines freeing the variable.

        """
        if isinstance(var, str):  # pragma: no cover
            var = {'name': var}
        out = []
        if not var.get('dont_free', False):
            if ((isinstance(var.get('datatype', False), dict)
                 and (('free_%s' % var['datatype']['type'])
                      in cls.function_param))):
                out = [cls.format_function_param(
                    'free_%s' % var['datatype']['type'],
                    variable=var['name'], **kwargs)]
            else:
                out = [cls.format_function_param(
                    'free', variable=var['name'], **kwargs)]
        return out

    @classmethod
    def write_assign_to_output(cls, dst_var, src_var, copy=False,
                               outputs_in_inputs=False, **kwargs):
        r"""Write lines assigning a value to an output variable.

        Args:
            dst_var (str, dict): Name or information dictionary for
                variable being assigned to.
            src_var (str, dict): Name or information dictionary for
                value being assigned to dst_var.
            copy (bool, optional): If True, the assigned value is copied
                during assignment. Defaults to False.
            outputs_in_inputs (bool, optional): If True, outputs are passed
                as input parameters. In some languages, this means that a
                pointer or reference is passed (e.g. C) and so the assignment
                should be to the memory indicated rather than the variable.
                Defaults to False.

        Returns:
            list: Lines achieving assignment.

        """
        datatype = None
        if isinstance(dst_var, dict):
            kwargs['name'] = dst_var['name']
            datatype = dst_var['datatype']
        else:
            kwargs['name'] = dst_var
        if isinstance(src_var, dict):
            kwargs['value'] = src_var['name']
            datatype = src_var['datatype']
        else:
            kwargs['value'] = src_var
        if ((outputs_in_inputs and isinstance(dst_var, dict)
             and isinstance(dst_var['datatype'], dict)
             and ('copy_' + dst_var['datatype']['type']
                  in cls.function_param))):
            copy = True
        if copy:
            if ((isinstance(datatype, dict)
                 and ('copy_' + datatype['type'] in cls.function_param))):
                return [cls.format_function_param(
                    'copy_' + datatype['type'], **kwargs)]
            else:
                return [cls.format_function_param('assign_copy', **kwargs)]
        else:
            return [cls.format_function_param('assign', **kwargs)]

    @classmethod
    def write_expand_single_element(cls, output_var):
        r"""Write lines allowing extraction of the only element from a single
        element array as a stand-alone variable if the variable is an array
        and only has one element.

        Args:
            output_var (str): Name of the variable that should be conditionally
                expanded.

        Returns:
            list: Lines added the conditional expansion of single element
                arrays.

        """
        if 'istype' not in cls.function_param:
            return []
        out = cls.write_if_block(
            ('(%s) %s (%s %s 1)' % (
                cls.format_function_param('istype',
                                          variable=output_var,
                                          type=cls.type_map['array']),
                cls.function_param.get('and', '&&'),
                cls.format_function_param('len',
                                          variable=output_var),
                cls.function_param.get('equ', '=='))),
            cls.format_function_param(
                'assign', name=output_var,
                value=cls.format_function_param(
                    'index', variable=output_var,
                    index=int(cls.function_param.get('first_index', 0)))))
        return out
        
    @classmethod
    def split_variables(cls, var_str):
        r"""Split variable string include individual variables.

        Args:
            var_str (str): String containing multiple variables.

        Returns:
            list: Split variables.

        """
        out = []
        if var_str:
            pairs = [(r'\[', r'\]'),
                     (r'\(', r'\)'),
                     (r'\{', r'\}'),
                     (r"'", r"'"),
                     (r'"', r'"')]
            regex_ele = r''
            present = False
            for p in pairs:
                if not any([(str(ip)[-1] in var_str) for ip in p]):
                    continue
                present = True
                regex_ele += (r'(?:%s[.\n]*?%s)|' % p)
            if present:
                regex_ele += '(?:.+?)'
                regex_ele = r'\s*(%s)\s*(?:,|$)' % regex_ele
                out = [x.group(1) for x in re.finditer(regex_ele, var_str)]
            else:
                out = [x.strip() for x in var_str.split(',')]
        return out

    @classmethod
    def prepare_variables(cls, vars_list, in_definition=False,
                          for_yggdrasil=False):
        r"""Concatenate a set of input variables such that it can be passed as a
        single string to the function_call parameter.

        Args:
            vars_list (list): List of variable dictionaries containing info
                (e.g. names) that should be used to prepare a string representing
                input/output to/from a function call.
            in_definition (bool, optional): If True, the returned sequence
                will be of the format required for specifying variables
                in a function definition. Defaults to False.
            for_yggdrasil (bool, optional): If True, the variables will be
                prepared in the formated expected by calls to yggdarsil
                send/recv methods. Defaults to False.

        Returns:
            str: Concatentated variables list.

        """
        name_list = []
        if not isinstance(vars_list, list):
            vars_list = [vars_list]
        for x in vars_list:
            if isinstance(x, str):
                name_list.append(x)
            else:
                assert(isinstance(x, dict))
                name_list.append(x['name'])
        return ', '.join(name_list)

    @classmethod
    def prepare_input_variables(cls, vars_list, in_definition=False,
                                for_yggdrasil=False):
        r"""Concatenate a set of input variables such that it can be passed as a
        single string to the function_call parameter.

        Args:
            vars_list (list): List of variable dictionaries containing info
                (e.g. names) that should be used to prepare a string representing
                input to a function call.
            in_definition (bool, optional): If True, the returned sequence
                will be of the format required for specifying input
                variables in a function definition. Defaults to False.
            for_yggdrasil (bool, optional): If True, the variables will be
                prepared in the formated expected by calls to yggdarsil
                send/recv methods. Defaults to False.

        Returns:
            str: Concatentated variables list.

        """
        return cls.prepare_variables(vars_list, in_definition=in_definition,
                                     for_yggdrasil=for_yggdrasil)

    @classmethod
    def prepare_output_variables(cls, vars_list, in_definition=False,
                                 in_inputs=False, for_yggdrasil=False):
        r"""Concatenate a set of output variables such that it can be passed as
        a single string to the function_call parameter.

        Args:
            vars_list (list): List of variable dictionaries containing info
                (e.g. names) that should be used to prepare a string representing
                output from a function call.
            in_definition (bool, optional): If True, the returned sequence
                will be of the format required for specifying output
                variables in a function definition. Defaults to False.
            in_inputs (bool, optional): If True, the output variables should
                be formated to be included as input variables. Defaults to
                False.
            for_yggdrasil (bool, optional): If True, the variables will be
                prepared in the formated expected by calls to yggdarsil
                send/recv methods. Defaults to False.

        Returns:
            str: Concatentated variables list.

        """
        if in_inputs:
            vars_list = [cls.output2input(x, in_definition=in_definition)
                         for x in vars_list]
        out = cls.prepare_variables(vars_list, in_definition=in_definition,
                                    for_yggdrasil=for_yggdrasil)
        if isinstance(vars_list, list) and (len(vars_list) > 1):
            if in_definition and ('multiple_outputs_def' in cls.function_param):
                out = cls.format_function_param('multiple_outputs_def', outputs=out)
            elif 'multiple_outputs' in cls.function_param:
                out = cls.format_function_param('multiple_outputs', outputs=out)
        return out

    @classmethod
    def write_if_block(cls, cond, block_contents, else_block_contents=False):
        r"""Return the lines required to complete a conditional block.

        Args:
            cond (str): Conditional that should determine block execution.
            block_contents (list): Lines of code that should be executed inside
                the block.
            else_block_contents (list, optional): Lines of code that should be
                executed inside the else clause of the block. Defaults to False
                if not provided and an else clause is omitted.

        Returns:
            list: Lines of code performing conditional execution of a block.

        """
        if cls.function_param is None:
            raise NotImplementedError("function_param attribute not set for"
                                      "language '%s'" % cls.language)
        out = []
        if not isinstance(cond, list):
            cond = [cond]
            block_contents = [block_contents]
        assert(len(cond) == len(block_contents))
        for i, (icond, iblock_contents) in enumerate(zip(cond, block_contents)):
            if i == 0:
                out.append(cls.format_function_param('if_begin', cond=icond))
            else:
                out.append(cls.format_function_param('if_elif', cond=icond))
            if not isinstance(iblock_contents, (list, tuple)):
                iblock_contents = [iblock_contents]
            for x in iblock_contents:
                out.append(cls.function_param['indent'] + x)
        if else_block_contents:
            out.append(cls.format_function_param('if_else'))
            if not isinstance(else_block_contents, (list, tuple)):
                else_block_contents = [else_block_contents]
            for x in else_block_contents:
                out.append(cls.function_param['indent'] + x)
        # Close block
        out.append(cls.function_param.get('if_end',
                                          cls.function_param.get(
                                              'block_end', '')))
        return out
                   
    @classmethod
    def write_for_loop(cls, iter_var, iter_begin, iter_end, loop_contents):
        r"""Return the lines required to complete a for loop.

        Args:
            iter_var (str): Name of variable that iterator should use.
            iter_begin (int): Beginning of iteration.
            iter_end (int): End of iteration.
            loop_contents (list): Lines of code that should be executed inside
                the loop.

        Returns:
            list: Lines of code performing a loop.

        """
        if cls.function_param is None:
            raise NotImplementedError("function_param attribute not set for"
                                      "language '%s'" % cls.language)
        out = []
        # Opening for statement line
        out.append(cls.format_function_param('for_begin', iter_var=iter_var,
                                             iter_begin=iter_begin,
                                             iter_end=iter_end))
        # Indent loop contents
        if not isinstance(loop_contents, (list, tuple)):
            loop_contents = [loop_contents]
        for x in loop_contents:
            out.append(cls.function_param['indent'] + x)
        # Close block
        out.append(cls.function_param.get('for_end',
                                          cls.function_param.get(
                                              'block_end', '')))
        return out

    @classmethod
    def write_while_loop(cls, cond, loop_contents):
        r"""Return the lines required to complete a for loop.

        Args:
            cond (str): Conditional that should determine loop execution.
            loop_contents (list): Lines of code that should be executed inside
                the loop.

        Returns:
            list: Lines of code performing a loop.

        """
        if cls.function_param is None:
            raise NotImplementedError("function_param attribute not set for"
                                      "language '%s'" % cls.language)
        out = []
        # Opening for statement line
        out.append(cls.format_function_param('while_begin', cond=cond))
        # Indent loop contents
        if not isinstance(loop_contents, (list, tuple)):
            loop_contents = [loop_contents]
        for x in loop_contents:
            out.append(cls.function_param['indent'] + x)
        # Close block
        out.append(cls.function_param.get('while_end',
                                          cls.function_param.get(
                                              'block_end', '')))
        return out

    @classmethod
    def write_try_except(cls, try_contents, except_contents, error_var='e',
                         error_type=None):
        r"""Return the lines required to complete a try/except block.

        Args:
            try_contents (list): Lines of code that should be executed inside
                the try block.
            except_contents (list): Lines of code that should be executed inside
                the except block.
            error_var (str, optional): Name of variable where the caught error
                should be stored. Defaults to 'e'.
            error_type (str, optional): Name of error type that should be caught.
                If not provided, defaults to None and will be set based on the
                class function_param entry for 'try_error_type'.

        Returns:
            Lines of code perfoming a try/except block.

        """
        if (cls.function_param is None) or ('try_begin' not in cls.function_param):
            raise NotImplementedError("function_param attribute not set for"
                                      "language '%s'" % cls.language)
        if error_type is None:
            error_type = cls.function_param.get('try_error_type', None)
        out = []
        # Try block contents
        if not isinstance(try_contents, (list, tuple)):
            try_contents = [try_contents]
        out.append(cls.function_param['try_begin'])
        for x in try_contents:
            out.append(cls.function_param['indent'] + x)
        # Except block contents
        if not isinstance(except_contents, (list, tuple)):
            except_contents = [except_contents]
        out.append(cls.format_function_param('try_except', error_var=error_var,
                                             error_type=error_type))
        for x in except_contents:
            out.append(cls.function_param['indent'] + x)
        # Close block
        out.append(cls.function_param.get('try_end',
                                          cls.function_param.get(
                                              'block_end', '')))
        return out
