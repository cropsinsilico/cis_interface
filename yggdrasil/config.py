"""
This module imports the configuration for yggdrasil.

.. todo::
   Remove reference to environment variables for accessing config options.

"""
import os
import sys
import json
import shutil
import logging
import warnings
import configparser
import copy
import argparse
from contextlib import contextmanager
from collections import OrderedDict
from yggdrasil import tools
env_prefixes = tools.get_env_prefixes()
config_file = '.yggdrasil.cfg'
def_config_file = os.path.join(os.path.dirname(__file__), 'defaults.cfg')
usr_dir = os.path.expanduser('~')
if env_prefixes:
    usr_dir = env_prefixes[-1]
usr_config_file = os.path.join(usr_dir, config_file)
loc_config_file = os.path.join(os.getcwd(), config_file)
logger = logging.getLogger(__name__)


# Set associated environment variables
_cfg_map = {
    ('debug', 'ygg'): {
        'env': 'YGG_DEBUG', 'arg': 'loglevel',
        'help': 'Logging level for yggdrasil operations.'},
    ('debug', 'rmq', 'RMQ_DEBUG'): {
        'env': 'YGG_RMQ_DEBUG', 'arg': 'rmq-loglevel',
        'help': 'Logging level for RabbitMQ operations.'},
    ('debug', 'client'): {
        'env': 'YGG_CLIENT_DEBUG', 'arg': 'client-loglevel',
        'help': 'Logging level for yggdrasil operations on model processes.'},
    ('jsonschema', 'validate_components'): {
        'env': 'YGG_VALIDATE_COMPONENTS', 'arg': 'validate-components',
        'action': 'store_true',
        'help': ('Validate components on creation using their JSON schema '
                 '(Decreases performance).')},
    ('jsonschema', 'validate_messages'): {
        'env': 'YGG_VALIDATE_MESSAGES', 'arg': 'validate-messages',
        'type': str, 'choices': ['False', 'True', 'First'],
        'help': ('Which messages should be validated during communication. '
                 '\'True\': all messages (decreases performance), '
                 '\'False\': no messages, or '
                 '\'First\': only the first message a comm sends/receives.')},
    ('rmq', 'namespace'): {
        'env': 'YGG_NAMESPACE', 'help': 'RabbitMQ namespace.'},
    ('rmq', 'host'): {
        'env': 'YGG_MSG_HOST', 'help': 'RabbitMQ host address.'},
    ('rmq', 'vhost'): {
        'env': 'YGG_MSG_VHOST', 'help': 'RabbitMQ virtual host address.'},
    ('rmq', 'user'): {
        'env': 'YGG_MSG_USER', 'help': 'RabbitMQ username.'},
    ('rmq', 'password'): {
        'env': 'YGG_MSG_PW', 'help': 'RabbitMQ password.'},
    ('parallel', 'cluster'): {
        'env': 'YGG_CLUSTER', 'help': 'Cluster that should be used.'},
    ('testing', 'enable_examples'): {
        'env': 'YGG_ENABLE_EXAMPLE_TESTS', 'arg': 'with-examples',
        'action': 'store_true',
        'help': 'Run example tests when encountered.'},
    ('testing', 'enable_demos'): {
        'env': 'YGG_ENABLE_DEMO_TESTS', 'arg': 'with-demos',
        'action': 'store_true',
        'help': 'Run demo tests when encountered.'},
    ('testing', 'languages'): {
        'env': 'YGG_TEST_LANGUAGE', 'arg': 'language',
        'default': [], 'nargs': '+', 'type': str,
        'help': 'Language(s) that sould not be tested.'},
    ('testing', 'skip_languages'): {
        'env': 'YGG_TEST_SKIP_LANGUAGE', 'arg': 'skip-language',
        'default': [], 'nargs': '+', 'type': str,
        'help': 'Language(s) that sould not be tested.'},
    ('testing', 'enable_long'): {
        'env': 'YGG_ENABLE_LONG_TESTS', 'arg': 'long-running',
        'action': 'store_true',
        'help': 'Run long tests when encounterd.'},
    ('testing', 'enable_production_runs'): {
        'env': 'YGG_TEST_PRODUCTION_RUNS',
        'action': 'store_true',
        'help': 'Run production level tests when encountered.'},
    ('general', 'default_comm'): {
        'env': 'YGG_DEFAULT_COMM', 'type': str,
        'help': 'Comm type that should be used by default.'}
}
_key2env = {}
for k, v in _cfg_map.items():
    arg = []
    if 'arg' in v:
        arg = [v['arg']]
    if k[0] not in ['debug']:
        new_arg = k[1].replace('_', '-')
        if new_arg not in arg:
            arg.append(new_arg)
    for x in copy.deepcopy(arg):
        _key2env[x.replace('-', '_')] = v['env']
        new_arg = x.replace('-', '')
        if new_arg not in arg:
            arg.append(new_arg)
    v['args'] = arg
    v['kwargs'] = {
        kk: v[kk] for kk in ['default', 'type', 'nargs', 'help', 'choices',
                             'action']
        if kk in v}

    
class YggConfigParser(configparser.ConfigParser, object):
    r"""Config parser that returns None if option not provided on get."""

    def __init__(self, files=None):
        self.files = files
        super(YggConfigParser, self).__init__()

    def reload(self):
        r"""Reload parameters from the original files."""
        for s in self.sections():
            self.remove_section(s)
        self._sections = self._dict()
        if self.files is not None:
            self.read(self.files)

    @property
    def file_to_update(self):
        r"""str: Full path to file that should be updated if update_file is
        called without an explicit file path."""
        out = None
        if self.files is not None:
            out = self.files[-1]
        return out

    def update_file(self, fname=None):
        r"""Write out updated contents to a file.

        Args:
            fname (str, optional): Full path to file where contents should be
               saved. If None, file_to_update is used. Defaults to None.

        Raises:
            RuntimeError: If fname is None and file_to_update is None.

        """
        if fname is None:
            fname = self.file_to_update
        if fname is None:
            raise RuntimeError("No file provided or set at creation.")
        with open(fname, 'w') as fd:
            self.write(fd)

    def read(self, *args, **kwargs):
        out = super(YggConfigParser, self).read(*args, **kwargs)
        alias_map = [(('debug', 'psi'), ('debug', 'ygg')),
                     (('debug', 'cis'), ('debug', 'ygg'))]
        for old, new in alias_map:
            v = self.get(*old)
            if v:  # pragma: debug
                self.set(new[0], new[1], v)
        return out

    @classmethod
    def from_files(cls, files, **kwargs):
        r"""Construct a config parser from a set of files.

        Args:
            files (list): One or more files that options should be read from in
                the order they should be loaded.
            **kwargs: Additional keyword arguments are passed to the class
                constructor.

        Returns:
           YggConfigParser: Config parser with information loaded from the
               provided files.

        """
        out = cls(files=files, **kwargs)
        out.reload()
        return out

    def set(self, section, option, value=None):
        """Set an option."""
        if not isinstance(value, str):
            value = json.dumps(value)
        super(YggConfigParser, self).set(section, option, value=value)

    def backwards_str2val(self, val):  # pragma: no cover
        try:
            out = json.loads(val)
        except ValueError:
            if val.startswith('[') and val.endswith(']'):
                if val[1:-1]:
                    out = [self.backwards_str2val(x.strip())
                           for x in val[1:-1].split(',')]
                else:
                    out = []
            elif val.startswith("'") and val.endswith("'"):
                out = val.strip("'")
            else:
                out = val
        return out

    def get(self, section, option, default=None, **kwargs):
        r"""Return None if the section/option does not exist.

        Args:
            section (str): Name of section.
            option (str): Name of option in section.
            default (obj, optional): Value that should be returned if the
                section and/or option are not found or are an empty string.
                Defaults to None.
            **kwargs: Additional keyword arguments are passed to the parent
                class's get.

        Returns:
            obj: String entry if the section & option exist, otherwise default.

        """
        section = section.lower()
        option = option.lower()
        out = None
        if (out is None) and ((section, option) in _cfg_map):
            out = os.environ.get(_cfg_map[(section, option)]['env'], None)
        if (((out is None) and self.has_section(section)
             and self.has_option(section, option))):
            # Super does not work for ConfigParser as not inherited from object
            out = configparser.ConfigParser.get(self, section, option, **kwargs)
        # Count empty strings as not provided
        if out:
            return self.backwards_str2val(out)
        return default


def get_language_order(drivers):
    r"""Get the correct language order, including any base languages.

    Args:
        drivers (dict): Drivers in order.

    Returns:
        dict: Drivers in sorted order.

    """
    from yggdrasil.components import import_component
    out = OrderedDict()
    for d, drv in drivers.items():
        if d == 'cpp':
            d = 'c++'
        new_deps = OrderedDict()
        sub_deps = OrderedDict()
        for sub_d in drv.base_languages:
            if sub_d in drivers:
                sub_deps[sub_d] = drivers[sub_d]
            else:
                sub_deps[sub_d] = import_component('model', sub_d)
        sub_deps = get_language_order(sub_deps)
        min_dep = -1
        for sub_d, sub_drv in sub_deps.items():
            if sub_d in out:
                min_dep = max(min_dep, list(out.keys()).index(sub_d))
            else:
                new_deps[sub_d] = sub_drv
        if d in out.keys():
            dpos = list(out.keys()).index(d)
            assert(dpos > min_dep)
            min_dep = dpos
        else:
            new_deps[d] = drv
        new_out = OrderedDict()
        for k in list(out.keys())[:(min_dep + 1)]:
            new_out[k] = out[k]
        new_out.update(new_deps)
        for k in list(out.keys())[(min_dep + 1):]:
            new_out[k] = out[k]
        out = new_out
    return out


def update_language_config(languages=None, skip_warnings=False,
                           disable_languages=None, enable_languages=None,
                           allow_multiple_omp=None, lang_kwargs=None,
                           overwrite=False, verbose=False):
    r"""Update configuration options for a language driver.

    Args:
        languages (list, optional): List of languages to configure.
            Defaults to None and all supported languages will be
            configured.
        skip_warnings (bool, optional): If True, warnings about missing options
            will not be raised. Defaults to False.
        disable_languages (list, optional): List of languages that should be
            disabled. Defaults to an empty list.
        enable_languages (list, optional): List of languages that should be
            enabled. Defaults to an empty list.
        allow_multiple_omp (bool, optional): Set the allow_multiple_omp config
            option controlling whether or not the KMP_DUPLICATE_LIB_OK environment
            variable is set for model environments. Defaults to None and is
            ignored.
        overwrite (bool, optional): If True, the existing file will be overwritten.
            Defaults to False.
        verbose (bool, optional): If True, information about the config file
            will be displayed. Defaults to False.
        lang_kwargs (dict, optional): Dictionary containing language
            specific keyword arguments. Defaults to {}.

    """
    from yggdrasil.components import import_component
    if verbose:
        logger.info("Updating user configuration file for yggdrasil at:\n\t%s"
                    % usr_config_file)
    miss = []
    if (languages is None) or overwrite:
        all_languages = tools.get_supported_lang()
        languages = ['c', 'c++', 'make', 'cmake', 'python', 'lpy', 'r', 'matlab']
        for lang in all_languages:
            if lang.lower() not in languages:
                languages.append(lang)
    elif not isinstance(languages, list):
        languages = [languages]
    if disable_languages is None:
        disable_languages = []
    if enable_languages is None:
        enable_languages = []
    if lang_kwargs is None:
        lang_kwargs = {}
    if overwrite:
        shutil.copy(def_config_file, usr_config_file)
        ygg_cfg_usr.reload()
    if allow_multiple_omp is not None:
        if not ygg_cfg_usr.has_section('general'):
            ygg_cfg_usr.add_section('general')
        ygg_cfg_usr.set('general', 'allow_multiple_omp', allow_multiple_omp)
    drivers = OrderedDict([(lang, import_component('model', lang))
                           for lang in languages])
    drv = list(get_language_order(drivers).values())
    for idrv in drv:
        if (((idrv.language in disable_languages)
             and (idrv.language in enable_languages))):
            logger.info(("%s language both enabled and disabled. "
                         "No action will be taken.") % idrv.language)
        elif idrv.language in disable_languages:
            if not ygg_cfg_usr.has_section(idrv.language):
                ygg_cfg_usr.add_section(idrv.language)
            ygg_cfg_usr.set(idrv.language, 'disable', 'True')
        elif idrv.language in enable_languages:
            if not ygg_cfg_usr.has_section(idrv.language):
                ygg_cfg_usr.add_section(idrv.language)
            ygg_cfg_usr.set(idrv.language, 'disable', 'False')
        if ygg_cfg_usr.get(idrv.language, 'disable', 'False').lower() == 'true':
            continue  # pragma: no cover
        miss += idrv.configure(ygg_cfg_usr,
                               **lang_kwargs.get(idrv.language, {}))
    ygg_cfg_usr.update_file()
    ygg_cfg.reload()
    if not skip_warnings:
        for sect, opt, desc in miss:  # pragma: windows
            warnings.warn(("Could not set option %s in section %s. "
                           + "Please set this in %s to: %s")
                          % (opt, sect, ygg_cfg_usr.file_to_update, desc),
                          RuntimeWarning)
    if verbose:
        with open(usr_config_file, 'r') as fd:
            print(fd.read())
    

def get_ygg_loglevel(cfg=None, default='DEBUG'):
    r"""Get the current log level.

    Args:
        cfg (:class:`yggdrasil.config.YggConfigParser`, optional):
            Config parser with options that should be used to determine the
            log level. Defaults to :data:`yggdrasil.config.ygg_cfg`.
        default (str, optional): Log level that should be returned if the log
            level option is not set in cfg. Defaults to 'DEBUG'.

    Returns:
        str: Log level string.

    """
    is_model = tools.is_subprocess()
    if cfg is None:
        cfg = ygg_cfg
    if is_model:
        opt = 'client'
    else:
        opt = 'ygg'
    return cfg.get('debug', opt, default)


def set_ygg_loglevel(level, cfg=None):
    r"""Set the current log level.

    Args:
        level (str): Level that the log should be set to.
        cfg (:class:`yggdrasil.config.YggConfigParser`, optional):
            Config parser with options that should be used to update the
            environment. Defaults to :data:`yggdrasil.config.ygg_cfg`.
    
    """
    is_model = tools.is_subprocess()
    if cfg is None:
        cfg = ygg_cfg
    if is_model:
        opt = 'client'
    else:
        opt = 'ygg'
    cfg.set('debug', opt, level)
    logLevelYGG = eval('logging.%s' % level)
    ygg_logger = logging.getLogger("yggdrasil")
    ygg_logger.setLevel(level=logLevelYGG)
        
    
def cfg_logging(cfg=None):
    r"""Set logging levels from config options.

    Args:
        cfg (:class:`yggdrasil.config.YggConfigParser`, optional):
            Config parser with options that should be used to update the
            environment. Defaults to :data:`yggdrasil.config.ygg_cfg`.

    """
    is_model = tools.is_subprocess()
    to_stdout = is_model
    try:  # pragma: no cover
        # Direct log messages to stdout in interpreter so that messages
        # are not red in notebooks
        get_ipython  # noqa: F821
        in_notebook = True
    except BaseException:
        in_notebook = False
    to_stdout = (is_model or in_notebook)
    if cfg is None:
        cfg = ygg_cfg
    log_format = cfg.get(
        'debug', 'format',
        "%(levelname)s:%(module)s.%(funcName)s[%(lineno)d]:%(message)s")
    logLevelYGG = eval(
        'logging.%s' % os.environ.get(
            'YGG_DEBUG', cfg.get('debug', 'ygg', 'NOTSET')))
    logLevelRMQ = eval(
        'logging.%s' % os.environ.get(
            'YGG_RMQ_DEBUG', cfg.get('debug', 'rmq', 'INFO')))
    logLevelCLI = eval(
        'logging.%s' % os.environ.get(
            'YGG_CLIENT_DEBUG', cfg.get('debug', 'client', 'INFO')))
    if is_model:
        logLevelYGG = os.environ.get('YGG_MODEL_DEBUG', logLevelCLI)
    if not to_stdout:
        logging.basicConfig(format=log_format)
    ygg_logger = logging.getLogger("yggdrasil")
    rmq_logger = logging.getLogger("pika")
    ygg_logger.setLevel(level=logLevelYGG)
    rmq_logger.setLevel(level=logLevelRMQ)
    # For models, route the logs to stdout so that they are
    # displayed by the model driver.
    if to_stdout:
        formatter = logging.Formatter(fmt=log_format)
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(formatter)
        handler.setLevel(logLevelYGG)
        ygg_logger.handlers = [handler]
        rmq_logger.handlers = [handler]
        if in_notebook:  # pragma: no cover
            ygg_logger.propagate = False
            rmq_logger.propagate = False
        # ygg_logger.addHandler(handler)
        # rmq_logger.addHandler(handler)


def cfg_environment(env=None, cfg=None):
    r"""Set environment variables based on config options.

    Args:
        env (dict, optional): Dictionary of environment variables that should
            be updated. Defaults to `os.environ`.
        cfg (:class:`yggdrasil.config.YggConfigParser`, optional):
            Config parser with options that should be used to update the
            environment. Defaults to :data:`yggdrasil.config.ygg_cfg`.

    """
    if env is None:
        env = os.environ
    if cfg is None:
        cfg = ygg_cfg
    for k, v in _cfg_map.items():
        val = cfg.get(*k)
        if val:
            env.setdefault(v['env'], val)

            
# Initialize config
ygg_cfg_usr = YggConfigParser.from_files([usr_config_file])
ygg_cfg = YggConfigParser.from_files([def_config_file, usr_config_file,
                                      loc_config_file])


# Do initial update of logging & environment (legacy)
cfg_logging()
cfg_environment()


def get_config_parser(parser=None, description=None, skip_sections=None):
    r"""Create a parser or add to an existing parser arguments based on
    configuration options.

    Args:
        parser (argparse.ArgumentParser, optional): Existing argument parser
            that arguments should be added to. Defaults to None and a new
            parser is created.
        description (str, optional): The description that should be used if
            a new parser is created. Defaults to None.
        skip_sections (list, optional): Configuration sections that should be
            skipped when adding arguments to the parser. Defaults to None and
            arguments for all configuration sections will be added.

    Returns:
        argparse.ArgumentParser: Argument parser with arguments added that
            are associated with configuration options.

    """
    if skip_sections is None:
        skip_sections = []
    if parser is None:
        parser = argparse.ArgumentParser(description=description)
    for k, v in _cfg_map.items():
        if k[0] in skip_sections:
            continue
        parser.add_argument(*['--' + x for x in v['args']], **v['kwargs'])
    parser.add_argument('--production-run', action='store_true',
                        help=('Turn off safe guards in order to improve '
                              'performance. This is equivalent to '
                              '\'--validate-components '
                              '--validate-messages=True\''))
    parser.add_argument('--debug', action='store_true',
                        help=('Turn on debugging utilties including '
                              'increased logging and validation. This is '
                              'equivalent to \'--loglevel=DEBUG '
                              '--client-loglevel=DEBUG '
                              '--validate-components=False '
                              '--validate-messages=False\''))
    return parser


def resolve_config_parser(args):
    r"""Process argument results by setting flags that are set by combination
    arguments.

    Args:
        args (argparse.ArgumentParser): Argument parser to set combination
            child flags for.

    Returns:
        argparse.ArgumentParser: Argument parser with child flags for
            combination flags set.

    """
    if args.debug and args.production_run:  # pragma: debug
        raise ValueError("\'--debug\' and \'--production-run\' flags are "
                         "incompatible.")
    if args.production_run:
        args.validate_components = False
        args.validate_messages = False
    elif args.debug:
        args.loglevel = 'DEBUG'
        args.client_loglevel = 'DEBUG'
        args.validate_components = True
        args.validate_messages = True
    else:
        args.loglevel = 'INFO'
        args.client_loglevel = 'INFO'
    if args.validate_messages in ['True', 'False']:
        args.validate_messages = (args.validate_messages == 'True')
    return args


def acquire_env(new_env):
    r"""Get the existing environment variable values and set the environment
    based on the provided dictionary.

    Args:
        new_env (dict): Mapping from configuration key to values that
            environment variables should be set to.

    Returns:
        dict: Mapping of environment variables and values that were overridden
            by new_env.

    """
    old_env = {}
    if new_env.get('debug', '') and new_env.get('production_run', ''):  # pragma: debug
        raise ValueError("'debug' and 'production_run' variables are "
                         "incompatible.")
    if 'production_run' in new_env:
        if new_env['production_run']:
            new_env['validate_components'] = False
            new_env['validate_messages'] = False
        new_env.pop('production_run')
    if 'debug' in new_env:
        if new_env['debug']:
            new_env['loglevel'] = 'DEBUG'
            new_env['client_loglevel'] = 'DEBUG'
            new_env['validate_components'] = True
            new_env['validate_messages'] = True
    if new_env.get('validate_messages', '') in ['True', 'False']:
        new_env['validate_messages'] = (new_env['validate_messages'] == 'True')
    # old_env = {k: os.environ.get(k, None) for k in _key2env.values()}
    for k, v in new_env.items():
        k_env = _key2env.get(k, k)
        old_env.setdefault(k_env, os.environ.get(k_env, None))
        if (((k_env in ['YGG_TEST_LANGUAGE', 'YGG_TEST_SKIP_LANGUAGE'])
             and isinstance(v, list))):
            if len(v) == 0:
                continue
            from yggdrasil.components import import_component
            v = [import_component('model', x).language for x in v]
        if not isinstance(v, str):
            v = json.dumps(v)
        os.environ[k_env] = v
    if new_env.get('loglevel', False):
        set_ygg_loglevel(new_env['loglevel'])
    return old_env


def restore_env(old_env):
    r"""Restore environment variables to a previous state.

    Args:
        old_env (dict): Mapping from environment variable to value for state
            that should be restored.

    """
    for k, v in old_env.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


@contextmanager
def parser_config(args, **kwargs):
    r"""Context manager for a run that modifies configuration options using
    values from an argument parser.

    Args:
        args (argparse.Namespace): Argument parsing results.
        **kwargs: Additional environment variable key/value pairs and/or
            argument name key/value pairs that should be added to the
            environment.

    """
    args = resolve_config_parser(args)
    for k0 in _key2env.keys():
        k = k0.replace('-', '_')
        if getattr(args, k, None) is not None:
            kwargs[k0] = getattr(args, k)
    old_env = acquire_env(kwargs)
    try:
        yield
    finally:
        restore_env(old_env)


@contextmanager
def temp_config(**kwargs):
    r"""Context manager for a run that modifies configuration options using
    a dictionary of key/value pairs.

    Args:
        **kwargs: Environment variable key/value pairs and/or argument name
            key/value pairs that should be added to the environment.

    """
    old_env = acquire_env(kwargs)
    try:
        yield
    finally:
        restore_env(old_env)
