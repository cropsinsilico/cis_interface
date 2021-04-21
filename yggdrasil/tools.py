"""This modules offers various tools."""
from __future__ import print_function
import threading
import logging
import pprint
import os
import re
import sys
import sysconfig
try:
    from distutils import sysconfig as distutils_sysconfig
except ImportError:  # pragma: debug
    distutils_sysconfig = None
import warnings
import copy
import shutil
import inspect
import time
import signal
import uuid as uuid_gen
import subprocess
import importlib
import difflib
from yggdrasil import platform, constants
from yggdrasil.components import import_component, ComponentBase


logger = logging.getLogger(__name__)
YGG_MSG_EOF = b'EOF!!!'
YGG_MSG_BUF = 1024 * 2


_stack_in_log = False
_stack_in_timeout = False
if ((logging.getLogger("yggdrasil").getEffectiveLevel()
     <= logging.DEBUG)):  # pragma: debug
    _stack_in_log = False
    _stack_in_timeout = True


def apply_recurse(x, func, **kwargs):
    r"""Apply a function recursively to all elements of x if it is
    a list, tuple, or dictionary.

    Args:
        x (list, tuple, dict): Object to apply function to.
        func (function): Function to apply to elements of x.
        **kwargs: Additional keyword arguments are passed to each
            function call.

    Returns:
        object: Version of input, but after applying func.

    """
    if isinstance(x, (list, tuple)):
        out = [func(ix, **kwargs) for ix in x]
        if isinstance(x, tuple):
            out = tuple(out)
    elif isinstance(x, dict):
        out = {k: func(v, **kwargs) for k, v in x.items()}
    else:  # pragma: debug
        raise TypeError("Recursion not supported for type '%s'"
                        % type(x))
    return out


def bytes2str(x, recurse=False):
    r"""Convert bytes type to string type.

    Args:
        x (bytes): String.
        recurse (bool, optional): If True and x is a list, tuple, or
            dict, the coversion will recurse. Defaults to False.

    Returns:
        str: Decoded string version of x.

    """
    if isinstance(x, bytes):
        out = x.decode("utf-8")
    elif isinstance(x, str):
        out = str(x)
    elif isinstance(x, (list, tuple, dict)) and recurse:
        out = apply_recurse(x, bytes2str, recurse=True)
    else:  # pragma: debug
        raise TypeError("Cannot convert type '%s' to str." % type(x))
    return out


def str2bytes(x, recurse=False):
    r"""Convert string type to bytes type.

    Args:
        x (str): String.
        recurse (bool, optional): If True and x is a list, tuple, or
            dict, the coversion will recurse. Defaults to False.

    Returns:
        bytes: Encoded bytes version of x.

    """
    if isinstance(x, str):
        out = x.encode("utf-8")
    elif isinstance(x, bytes):
        out = bytes(x)
    elif isinstance(x, (list, tuple, dict)) and recurse:
        out = apply_recurse(x, str2bytes, recurse=True)
    else:  # pragma: debug
        raise TypeError("Cannot convert type '%s' to bytes." % type(x))
    return out


def add_line_numbers(lines, for_diff=False):
    r"""Add number to lines.

    Args:
        lines (list): Lines to number.
        for_diff (bool, optional): If True, those lines beginning with
            removed/notation diff characters (-, ?) will not be numbered.
            Defaults to False.

    Returns:
        list: Numbered lines.

    """
    out = []
    i = 0
    for line in lines:
        if for_diff and line.startswith(('-', '?')):
            out.append('    ' + line)
        else:
            i += 1
            out.append('%2d: %s' % (i, line))
    return out


def display_source(fname, number_lines=False, return_lines=False):
    r"""Display source code with syntax highlighting (if available).

    Args:
        fname (str, list): Full path(s) to one or more source files.
        number_lines (bool, optional): If True, line numbers will be added
            to the displayed examples. Defaults to False.
        return_lines (bool, optional): If True, the lines are returned rather
            than displayed. Defaults to False.

    """
    if isinstance(fname, list):
        out = ''
        for f in fname:
            iout = display_source(f, number_lines=number_lines,
                                  return_lines=return_lines)
            if return_lines:
                out += iout
        if return_lines:
            return out
        return
    with open(fname, 'r') as fd:
        lines = fd.read()
    language = constants.EXT2LANG[os.path.splitext(fname)[-1]]
    try:
        from pygments import highlight
        from pygments.lexers import PythonLexer
        from pygments.lexers.data import YamlLexer
        from pygments.lexers.c_cpp import CLexer, CppLexer
        from pygments.lexers.r import SLexer
        from pygments.lexers.fortran import FortranLexer
        from pygments.lexers.matlab import MatlabLexer
        from pygments.lexers.html import XmlLexer
        from pygments.formatters import Terminal256Formatter
        lexer_map = {'python': PythonLexer,
                     'yaml': YamlLexer,
                     'c': CLexer,
                     'c++': CppLexer,
                     'r': SLexer,
                     'fortran': FortranLexer,
                     'matlab': MatlabLexer,
                     'xml': XmlLexer}
        lines = highlight(lines, lexer_map[language](),
                          Terminal256Formatter())
    except ImportError:
        pass
    if number_lines:
        lines = '\n'.join(add_line_numbers(lines.splitlines()))
    lines = 'file: %s\n%s\n%s' % (fname, (len(fname) + 6) * '=', lines)
    if return_lines:
        return lines
    print(lines)


def display_source_diff(fname1, fname2, number_lines=False,
                        return_lines=False):
    r"""Display a diff between two source code files with syntax highlighting
    (if available).

    Args:
        fname1 (str): Name of first source file.
        fname2 (src): Name of second source file.
        number_lines (bool, optional): If True, line numbers will be added
            to the displayed examples. Defaults to False.
        return_lines (bool, optional): If True, the lines are returned rather
            than displayed. Defaults to False.

    """
    src1 = display_source(fname1, return_lines=True)
    src2 = display_source(fname2, return_lines=True)
    diff = difflib.ndiff(src1.splitlines(), src2.splitlines())
    if number_lines:
        diff = add_line_numbers(diff, for_diff=True)
    lines = 'file1: %s\nfile2: %s\n%s' % (fname1, fname2, '\n'.join(diff))
    if return_lines:
        return lines
    print(lines)
    

def get_fds():  # pragma: debug
    r"""Get a list of open file descriptors."""
    out = subprocess.check_output(
        'lsof -p {} | grep -v txt'.format(os.getpid()), shell=True)
    return out.splitlines()[1:]


def get_shell():
    r"""Get the type of shell that yggdrasil was called from.

    Returns:
        str: Name of the shell.

    """
    shell = os.environ.get('SHELL', None)
    if not shell:
        if platform._is_win:  # pragma: windows
            shell = os.environ.get('COMSPEC', None)
        else:
            shell = '/bin/sh'  # Default used by subprocess
        assert(shell)
    # return psutil.Process(os.getppid()).name()
    if platform._is_win:  # pragma: windows
        shell = shell.lower()
    return shell


def in_powershell():
    r"""Determine if yggdrasil is running from a Windows Powershell.

    Returns:
        bool: True if running from Powershell, False otherwise.

    """
    if not platform._is_win:
        return False
    shell = get_shell()
    return bool(re.match('pwsh|pwsh.exe|powershell.exe', shell))


def check_environ_bool(name, valid_values=['true', '1', True, 1]):
    r"""Check to see if a boolean environment variable is set to True.

    Args:
        name (str): Name of environment variable to check.
        valid_values (list, optional): Values for the environment variable
            that indicate it is True. These should all be lower case as
            the lower case version of the variable contents will be compared
            to the list. Defaults to ['true', '1'].

    Returns:
        bool: True if the environment variables is set and is one of the
            list valid_values (after being transformed to lower case).

    """
    return (os.environ.get(name, '').lower() in valid_values)


def get_python_c_library(allow_failure=False, libtype=None):
    r"""Determine the location of the Python C API library.

    Args:
        allow_failure (bool, optional): If True, the base name will be returned
            if the file cannot be located. Defaults to False.
        libtype (str, optional): Type of library that should be located.
            Valid values include 'static' and 'shared'. Defaults to 'shared'
            on Unix OSs and 'static' on Windows.

    Returns:
        str: Full path to the library.

    Raises:
        ValueError: If libtype is not 'static' or 'shared'.
        RuntimeError: If the base name for the library cannot be determined.
        RuntimeError: If the library cannot be located.

    """
    if libtype not in ['static', 'shared', None]:  # pragma: debug
        raise ValueError("libtype must be 'shared' or 'static', "
                         "'%s' not supported." % libtype)
    paths = sysconfig.get_paths()
    cvars = sysconfig.get_config_vars()
    if platform._is_win:  # pragma: windows
        libtype2ext = {'shared': '.dll', 'static': '.lib'}
        prefix = ''
        if libtype is None:
            libtype = 'shared'
        base = '%spython%s%s' % (prefix,
                                 cvars['py_version_nodot'],
                                 libtype2ext[libtype])
    elif sys.version_info[:2] < (3, 8):
        if libtype is None:
            libtype = 'shared'
        libtype2key = {'shared': 'LDLIBRARY', 'static': 'LIBRARY'}
        base = cvars.get(libtype2key[libtype], None)
    else:
        if libtype is None:
            libtype = 'shared'
        if platform._is_mac:
            libtype2ext = {'shared': '.dylib', 'static': '.a'}
        else:
            libtype2ext = {'shared': '.so', 'static': '.a'}
        prefix = 'lib'
        base = '%spython%s%s' % (prefix,
                                 cvars['py_version_short'],
                                 libtype2ext[libtype])
    if platform._is_mac and base.endswith('/Python'):  # pragma: no cover
        base = 'libpython%s.dylib' % cvars['py_version_short']
    if base is None:  # pragma: debug
        raise RuntimeError(("Could not determine base name for the Python "
                            "C API library.\n"
                            "sysconfig.get_paths():\n%s\n"
                            "sysconfig.get_config_vars():\n%s\n")
                           % (pprint.pformat(paths),
                              pprint.pformat(cvars)))
    dir_try = []
    for x in [get_conda_prefix(), cvars['prefix']]:
        if x:
            dir_try.append(x)
            if platform._is_win:  # pragma: windows
                dir_try.append(os.path.join(x, 'libs'))
            else:
                dir_try.append(os.path.join(x, 'lib'))
    for k in ["LIBPL", "LIBDIR", "LIBDEST", "Prefix", "ExecPrefix",
              "BaseExecPrefix"]:
        if cvars.get(k, None) and (cvars[k] not in dir_try):
            dir_try.append(cvars[k])
    for k in ['stdlib', 'purelib', 'platlib', 'platstdlib', 'data']:
        if paths.get(k, None) and (paths[k] not in dir_try):
            dir_try.append(paths[k])
    dir_try.append(os.path.join(paths['data'], 'lib'))
    if distutils_sysconfig is not None:
        dir_try.append(os.path.dirname(
            distutils_sysconfig.get_python_lib(True, True)))
    dir_try = set(dir_try)
    for idir in dir_try:
        x = os.path.join(idir, base)
        if os.path.isfile(x):
            return x
    if allow_failure:  # pragma: debug
        return base
    raise RuntimeError(("Could not determine the location of the Python "
                        "C API library: %s.\n"
                        "sysconfig.get_paths():\n%s\n"
                        "sysconfig.get_config_vars():\n%s\n")
                       % (base, pprint.pformat(paths),
                          pprint.pformat(cvars)))  # pragma: debug


def get_env_prefixes():
    r"""Determine the environment path prefix (virtualenv or conda) for
    the current environment.

    Returns:
        list: Full path to the directory prefixes used for the current
            environments if one (or more) exists. If neither a
            virtualenv or conda prefix can be located, None is returned.

    Raises:
        RuntimeError: If both virtualenv and conda environments are
            located.

    """
    out = []
    venv = get_venv_prefix()
    cenv = get_conda_prefix()
    if venv:
        out.append(venv)
    if cenv:
        out.append(cenv)
    return out


def get_venv_prefix():
    r"""Determine the virtualenv path prefix for the current environment.

    Returns:
        str: Full path to the directory prefix used for the current
            virtualenv environment if one exists. If virtualenv cannot
            be located, None is returned.

    """
    return os.environ.get('VIRTUAL_ENV', None)


def get_conda_prefix():
    r"""Determine the conda path prefix for the current environment.

    Returns:
        str: Full path to the directory prefix used for the current conda
            environment if one exists. If conda cannot be located, None is
            returned.

    """
    conda_prefix = os.environ.get('CONDA_PREFIX', None)
    # This part should be enabled if the conda base enviroment dosn't have
    # CONDA_PREFIX set. Older version of conda behaved this way so it is
    # possible that a future release will as well.
    # if not conda_prefix:
    #     conda_prefix = shutil.which('conda')
    #     if conda_prefix is not None:
    #         conda_prefix = os.path.dirname(os.path.dirname(conda_prefix))
    return conda_prefix


def get_conda_env():
    r"""Determine the name of the current conda environment.

    Returns:
        str: Name of the current conda environment if one is activated. If a
            conda environment is not activated, None is returned.

    """
    return os.environ.get('CONDA_DEFAULT_ENV', None)


def get_subprocess_language():
    r"""Determine the language of the calling process.

    Returns:
        str: Name of the programming language responsible for the subprocess.

    """
    return os.environ.get('YGG_MODEL_LANGUAGE', 'python')


def get_subprocess_language_driver():
    r"""Determine the driver for the langauge of the calling process.

    Returns:
        ModelDriver: Class used to handle running a model of the process language.

    """
    return import_component('model', get_subprocess_language())


def is_subprocess():
    r"""Determine if the current process is a subprocess.

    Returns:
        bool: True if YGG_SUBPROCESS environment variable is True, False
            otherwise.

    """
    return check_environ_bool('YGG_SUBPROCESS')


def find_all(name, path, verification_func=None):
    r"""Find all instances of a file with a given name within the directory
    tree starting at a given path.

    Args:
        name (str): Name of the file to be found (with the extension).
        path (str, None): Directory where search should start. If set to
            None on Windows, the current directory and PATH variable are
            searched.
        verification_func (function, optional): Function that returns
            True when a file is valid and should be returned and False
            otherwise. Defaults to None and is ignored.

    Returns:
        list: All instances of the specified file.

    """
    result = []
    try:
        if platform._is_win:  # pragma: windows
            if path is None:
                out = subprocess.check_output(["where", name],
                                              env=os.environ,
                                              stderr=subprocess.STDOUT)
            else:
                out = subprocess.check_output(["where", "/r", path, name],
                                              env=os.environ,
                                              stderr=subprocess.STDOUT)
        else:
            args = ["find", "-L", path, "-type", "f", "-name", name]
            pfind = subprocess.Popen(args, env=os.environ,
                                     stderr=subprocess.PIPE,
                                     stdout=subprocess.PIPE)
            (stdoutdata, stderrdata) = pfind.communicate()
            out = stdoutdata
            for line in stderrdata.splitlines():
                if b'Permission denied' not in line:
                    raise subprocess.CalledProcessError(pfind.returncode,
                                                        ' '.join(args),
                                                        output=stderrdata)
    except subprocess.CalledProcessError:
        out = ''
    if not out.isspace():
        result = sorted(out.splitlines())
    result = [os.path.normcase(os.path.normpath(bytes2str(m)))
              for m in result]
    if verification_func is not None:
        result = [x for x in result if verification_func(x)]
    return result


def locate_file(fname, environment_variable='PATH', directory_list=None,
                show_alternates=False, verification_func=None):
    r"""Locate a file within a set of paths defined by a list or environment
    variable.

    Args:
        fname (str, list): One or more possible names of the file that should be
            located. If a list is provided, the path for the first entry for
            which a match could be located will be returned and subsequent entries
            will not be checked.
        environment_variable (str): Environment variable containing the set of
            paths that should be searched. Defaults to 'PATH'. If None, this
            keyword argument will be ignored. If a list is provided, it is
            assumed to be a list of environment variables that should be
            searched in the specified order.
        directory_list (list): List of paths that should be searched in addition
            to those specified by environment_variable. Defaults to None and is
            ignored. These directories will be searched be for those in the
            specified environment variables.
        show_alternates (bool, optional): If True and there is more
            than one match, the alternate matches will be printed in
            a warning message. Defaults to False.
        verification_func (function, optional): Function that returns
            True when a file is valid and should be returned and False
            otherwise. Defaults to None and is ignored.

    Returns:
        bool, str: Full path to the located file if it was located, False
            otherwise.

    """
    if isinstance(fname, list):
        out = False
        for ifname in fname:
            out = locate_file(ifname, environment_variable=environment_variable,
                              directory_list=directory_list,
                              show_alternates=show_alternates,
                              verification_func=verification_func)
            if out:
                break
        return out
    out = []
    if ((platform._is_win and (environment_variable == 'PATH')
         and (directory_list is None))):  # pragma: windows
        out += find_all(fname, None,
                        verification_func=verification_func)
    else:
        if directory_list is None:
            directory_list = []
        if environment_variable is not None:
            if not isinstance(environment_variable, list):
                environment_variable = [environment_variable]
            for x in environment_variable:
                directory_list += os.environ.get(x, '').split(os.pathsep)
        for path in directory_list:
            if path:
                out += find_all(fname, path,
                                verification_func=verification_func)
            if out and (not show_alternates):
                break
    if not out:
        return False
    first = out[0]
    if show_alternates:  # pragma: debug
        out = set(out)
        out.remove(first)
        if len(out) > 0:
            warnings.warn(("More than one (%d) match to %s:\n%s\n "
                           + "Using first match (%s)") %
                          (len(out) + 1, fname, pprint.pformat(out),
                           first), RuntimeWarning)
    return first


def locate_path(fname, basedir=os.path.abspath(os.sep)):
    r"""Find the full path to a file using where on Windows."""
    try:
        if platform._is_win:  # pragma: windows
            out = subprocess.check_output(["dir", fname, "/s/b"], shell=True,
                                          cwd=basedir)
            # out = subprocess.check_output(["where", fname])
        else:
            # find . -name "filetofind" 2>&1 | grep -v 'permission denied'
            out = subprocess.check_output(["find", basedir, "-name", fname])  # ,
            # "2>&1", "|", "grep", "-v", "'permission denied'"])
            # out = subprocess.check_output(["locate", "-b", "--regex",
            #                                "^%s" % fname])
    except subprocess.CalledProcessError:  # pragma: debug
        return False
    if out.isspace():  # pragma: debug
        return False
    out = bytes2str(out).splitlines()
    return out


def remove_path(fpath, timer_class=None, timeout=None):
    r"""Delete a single file.

    Args:
        fpath (str): Full path to a file or directory that should be
            removed.
        timer_class (YggClass, optional): Class that should be used to
            generate a timer that is used to wait for file to be removed.
            Defaults to None and a new class instance will be created.
        timeout (float, optional): Time (in seconds) that should be
            waited before raising an error that a file cannot be removed.
            Defaults to None and will be set by the timer_class.

    Raises:
        RuntimeError: If the product cannot be removed.

    """
    if timer_class is None:
        timer_class = YggClass()
    if os.path.isdir(fpath):
        T = timer_class.start_timeout(t=timeout)
        while ((not T.is_out) and os.path.isdir(fpath)):
            try:
                shutil.rmtree(fpath)
            except BaseException:  # pragma: debug
                if os.path.isdir(fpath):
                    timer_class.sleep()
                if T.is_out:
                    raise
        timer_class.stop_timeout()
        if os.path.isdir(fpath):  # pragma: debug
            raise RuntimeError("Failed to remove directory: %s" % fpath)
    elif os.path.isfile(fpath):
        T = timer_class.start_timeout(t=timeout)
        while ((not T.is_out) and os.path.isfile(fpath)):
            try:
                os.remove(fpath)
            except BaseException:  # pragma: debug
                if os.path.isfile(fpath):
                    timer_class.sleep()
                if T.is_out:
                    raise
        timer_class.stop_timeout()
        if os.path.isfile(fpath):  # pragma: debug
            raise RuntimeError("Failed to remove file: %s" % fpath)


def get_supported_platforms():
    r"""Get a list of the platforms supported by yggdrasil.

    Returns:
        list: The name of platforms supported by yggdrasil.

    """
    return copy.deepcopy(platform._supported_platforms)


def get_supported_lang():
    r"""Get a list of the model programming languages that are supported
    by yggdrasil.

    Returns:
        list: The names of programming languages supported by yggdrasil.
    
    """
    # from yggdrasil import schema
    # s = schema.get_schema()
    # out = s['model'].subtypes
    # if 'r' in out:
    #     out[out.index('r')] = 'R'
    out = constants.LANGUAGES['all'].copy()
    if 'c++' in out:
        out[out.index('c++')] = 'cpp'
    return list(set(out))


def get_supported_type():
    r"""Get a list of the data types that are supported by yggdrasil.

    Returns:
        list: The names of data types supported by yggdrasil.

    """
    from yggdrasil.metaschema.datatypes import get_registered_types
    return list(get_registered_types().keys())


def get_supported_comm(dont_include_value=False):
    r"""Get a list of the communication mechanisms supported by yggdrasil.

    Args:
        dont_include_value (bool, optional): If True, don't include the
            ValueComm in the list returned. Defaults to False.

    Returns:
        list: The names of communication mechanisms supported by yggdrasil.

    """
    from yggdrasil import schema
    excl_list = ['CommBase', 'DefaultComm', 'default']
    if dont_include_value:
        excl_list += ['ValueComm', 'value']
    s = schema.get_schema()
    out = s['comm'].subtypes
    for k in excl_list:
        if k in out:
            out.remove(k)
    return list(set(out))


def is_lang_installed(lang):
    r"""Check to see if yggdrasil can run models written in a programming
    language on the current machine.

    Args:
        lang (str): Programming language to check.

    Returns:
        bool: True if models in the provided language can be run on the current
            machine, False otherwise.

    """
    drv = import_component('model', lang)
    return drv.is_installed()


def is_comm_installed(comm, language=None):
    r"""Check to see if yggdrasil can use a communication mechanism on the
    current machine.

    Args:
        comm (str): Communication mechanism to check.
        language (str, optional): Specific programming language that
            communication mechanism should be check for. Defaults to None and
            all supported languages will be checked.

    Returns:
        bool: True if the communication mechanism can be used on the current
            machine, False otherwise.

    """
    cmm = import_component('comm', comm)
    return cmm.is_installed(language=language)


def get_installed_lang():
    r"""Get a list of the languages that are supported by yggdrasil on the
    current machine. This checks for the necessary interpreters, licenses, and/or
    compilers.

    Returns:
        list: The name of languages supported on the current machine.
    
    """
    out = []
    all_lang = get_supported_lang()
    for k in all_lang:
        if is_lang_installed(k):
            out.append(k)
    return out


def get_installed_comm(language=None, dont_include_value=False):
    r"""Get a list of the communication channel types that are supported by
    yggdrasil on the current machine. This checks the operating system,
    supporting libraries, and broker credentials. The order indicates the
    prefered order of use.

    Args:
        language (str, optional): Specific programming language that installed
            comms should be located for. Defaults to None and all languages
            supported on the current platform will be checked.
        dont_include_value (bool, optional): If True, don't include the
            ValueComm in the list returned. Defaults to False.


    Returns:
        list: The names of the the communication channel types supported on
            the current machine.

    """
    out = []
    all_comm = get_supported_comm(dont_include_value=dont_include_value)
    for k in all_comm:
        if is_comm_installed(k, language=language):
            out.append(k)
    # Fix order to denote preference
    out_sorted = []
    for k in ['zmq', 'ipc', 'rmq']:
        if k in out:
            out.remove(k)
            out_sorted.append(k)
    out_sorted += out
    return out_sorted


def get_default_comm():
    r"""Get the default comm that should be used for message passing."""
    if 'YGG_DEFAULT_COMM' in os.environ:
        _default_comm = os.environ['YGG_DEFAULT_COMM']
        # if not is_comm_installed(_default_comm, language='any'):  # pragma: debug
        #     raise Exception('Unsupported default comm %s set by YGG_DEFAULT_COMM' % (
        #                     _default_comm))
    else:
        comm_list = get_installed_comm()
        if len(comm_list) > 0:
            _default_comm = comm_list[0]
        else:  # pragma: windows
            # Locate comm that maximizes languages that can be run
            tally = {}
            for c in get_supported_comm(dont_include_value=True):
                tally[c] = 0
                for lang in get_supported_lang():
                    if is_comm_installed(c, language=lang):
                        tally[c] += 1
            _default_comm = max(tally)
            if tally[_default_comm] == 0:  # pragma: debug
                raise Exception('Could not locate an installed comm.')
    if _default_comm.endswith('Comm'):
        _default_comm = import_component('comm', _default_comm)._commtype
    if _default_comm == 'rmq':  # pragma: debug
        raise NotImplementedError('RMQ cannot be the default comm because '
                                  + 'there is not an RMQ C interface.')
    return _default_comm


def get_YGG_MSG_MAX(comm_type=None):
    r"""Get the maximum message size for a given comm type.

    Args:
        comm_type (str, optional): The name of the communication type that the
            maximum message size should be returned for. Defaults to result of
            get_default_comm() if not provided.

    Returns:
        int: Maximum message size (in bytes).

    """
    if comm_type is None:
        comm_type = get_default_comm()
    if comm_type in ['ipc', 'IPCComm']:
        # OS X limit is 2kb
        out = 1024 * 2
    else:
        out = 2**20
    return out


# https://stackoverflow.com/questions/35772001/
# how-to-handle-the-signal-in-python-on-windows-machine
def kill(pid, signum):
    r"""Kill process by mapping signal number.

    Args:
        pid (int): Process ID.
        signum (int): Signal that should be sent.

    """
    if platform._is_win:  # pragma: debug
        sigmap = {signal.SIGINT: signal.CTRL_C_EVENT,
                  signal.SIGBREAK: signal.CTRL_BREAK_EVENT}
        if signum in sigmap and pid == os.getpid():
            # we don't know if the current process is a
            # process group leader, so just broadcast
            # to all processes attached to this console.
            pid = 0
        thread = threading.current_thread()
        handler = signal.getsignal(signum)
        # work around the synchronization problem when calling
        # kill from the main thread.
        if (((signum in sigmap) and (thread.name == 'MainThread')
             and callable(handler) and ((pid == os.getpid()) or (pid == 0)))):
            event = threading.Event()

            def handler_set_event(signum, frame):
                event.set()
                return handler(signum, frame)

            signal.signal(signum, handler_set_event)
            try:
                print("calling interrupt", pid)
                os.kill(pid, sigmap[signum])
                # busy wait because we can't block in the main
                # thread, else the signal handler can't execute.
                while not event.is_set():
                    pass
                print("after interrupt")
            finally:
                signal.signal(signum, handler)
                print("in finally")
        else:
            os.kill(pid, sigmap.get(signum, signum))
    else:
        os.kill(pid, signum)


def sleep(interval):
    r"""Sleep for a specified number of seconds.

    Args:
        interval (float): Time in seconds that process should sleep.

    """
    time.sleep(interval)


def safe_eval(statement, **kwargs):
    r"""Run eval with a limited set of builtins and Python libraries/functions.

    Args:
        statement (str): Statement that should be evaluated.
        **kwargs: Additional keyword arguments are variables that are made available
            to the statement during evaluation.

    Returns:
        object: Result of the eval.

    """
    safe_dict = {}
    _safe_lists = {'math': ['acos', 'asin', 'atan', 'atan2', 'ceil', 'cos',
                            'cosh', 'degrees', 'e', 'exp', 'fabs', 'floor', 'fmod',
                            'frexp', 'hypot', 'ldexp', 'log', 'log10', 'modf', 'pi',
                            'pow', 'radians', 'sin', 'sinh', 'sqrt', 'tan', 'tanh'],
                   'builtins': ['abs', 'any', 'bool', 'bytes', 'float', 'int', 'len',
                                'list', 'map', 'max', 'min', 'repr', 'set', 'str',
                                'sum', 'tuple', 'type'],
                   'numpy': ['array', 'int8', 'int16', 'int32', 'int64',
                             'uint8', 'uint16', 'uint32', 'uint64',
                             'float16', 'float32', 'float64'],
                   'yggdrasil.units': ['get_data', 'add_units'],
                   'unyt.array': ['unyt_quantity', 'unyt_array']}
    for mod_name, func_list in _safe_lists.items():
        mod = importlib.import_module(mod_name)
        for func in func_list:
            safe_dict[func] = getattr(mod, func)
    safe_dict.update(kwargs)
    # The following replaces <Class Name(a, b)> style reprs with calls to classes
    # identified in self._no_eval_class
    # regex = r'<([^<>]+)\(([^\(\)]+)\)>'
    # while True:
    #     match = re.search(regex, statement)
    #     if not match:
    #         break
    #     cls_repl = self._no_eval_class.get(match.group(1), False)
    #     if not cls_repl:
    #         raise ValueError("Expression '%s' in '%s' is not eval friendly."
    #                          % (match.group(0), statement))
    #     statement = statement.replace(match.group(0),
    #                                   '%s(%s)' % (cls_repl, match.group(2)), 1)
    return eval(statement, {"__builtins__": None}, safe_dict)


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


class ProxyMeta(type):
    r"""Metaclass for handling proxy."""

    _special_names = [
        '__abs__', '__add__', '__and__', '__call__', '__cmp__', '__coerce__',
        '__contains__', '__delitem__', '__delslice__', '__div__', '__divmod__',
        '__eq__', '__float__', '__floordiv__', '__ge__', '__getitem__',
        '__getslice__', '__gt__', '__hex__', '__iadd__', '__iand__',
        '__idiv__', '__idivmod__', '__ifloordiv__', '__ilshift__', '__imod__',
        '__imul__', '__int__', '__invert__', '__ior__', '__ipow__', '__irshift__',
        '__isub__', '__iter__', '__itruediv__', '__ixor__', '__le__', '__len__',
        '__long__', '__lshift__', '__lt__', '__mod__', '__mul__', '__ne__',
        '__neg__', '__oct__', '__or__', '__pos__', '__pow__', '__radd__',
        '__rand__', '__rdiv__', '__rdivmod__', '__reduce__', '__reduce_ex__',
        '__repr__', '__reversed__', '__rfloorfiv__', '__rlshift__', '__rmod__',
        '__rmul__', '__ror__', '__rpow__', '__rrshift__', '__rshift__', '__rsub__',
        '__rtruediv__', '__rxor__', '__setitem__', '__setslice__', '__sub__',
        '__truediv__', '__xor__', 'next', '__hash__'
    ]
    
    def __new__(cls, classname, bases, attrs):
        overrides = attrs.get('__overrides__', [])
        overrides.extend(attrs.get('__slots__', []))
        overrides.extend(k for k in attrs.keys() if k not in
                         ['__overrides__'])
        for base in bases:
            overrides.extend(getattr(base, '__overrides__', []))
        assert('_wrapped' in overrides)
        attrs['__overrides__'] = overrides
        
        def make_method(name):
            def method(self, *args, **kwargs):
                mtd = getattr(object.__getattribute__(self, "_wrapped"), name)
                return mtd(*args, **kwargs)
            return method

        for name in cls._special_names:
            if name not in overrides:
                attrs[name] = make_method(name)
        return type.__new__(cls, classname, bases, attrs)


class ProxyObject(metaclass=ProxyMeta):
    r"""Proxy for another object."""
    # http://code.activestate.com/recipes/496741-object-proxying/
    
    __slots__ = ["_wrapped", "__weakref__"]
    
    def __init__(self, wrapped):
        object.__setattr__(self, "_wrapped", wrapped)

    def __getattribute__(self, name):
        if name in object.__getattribute__(self, '__overrides__'):
            return object.__getattribute__(self, name)
        return getattr(object.__getattribute__(self, "_wrapped"), name)
    
    def __delattr__(self, name):
        if name in object.__getattribute__(self, '__overrides__'):
            object.__delattr__(self, name)
            return
        delattr(object.__getattribute__(self, "_wrapped"), name)
        
    def __setattr__(self, name, value):
        if name in object.__getattribute__(self, '__overrides__'):
            object.__setattr__(self, name, value)
            return
        setattr(object.__getattribute__(self, "_wrapped"), name, value)

    def __reduce__(self):
        return (object.__getattribute__(self, "__class__"),
                (object.__getattribute__(self, "_wrapped"), ))

    def __reduce_ex__(self, proto):
        return object.__getattribute__(self, "__reduce__")()
    
    # Special cases
    def __bool__(self):
        return bool(object.__getattribute__(self, "_wrapped"))
    
    def __str__(self):
        return str(object.__getattribute__(self, "_wrapped"))
    
    def __bytes__(self):
        return bytes(object.__getattribute__(self, "_wrapped"))
    
    def __repr__(self):
        return repr(object.__getattribute__(self, "_wrapped"))


class YggPopen(subprocess.Popen):
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
    def __init__(self, cmd_args, forward_signals=True, for_matlab=False, **kwargs):
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
        # To prevent forward of signals, process will have a new process group
        if not forward_signals:
            if platform._is_win:  # pragma: windows
                # TODO: Make sure that Matlab handled correctly since pty not
                # guaranteed on windows
                kwargs.setdefault('preexec_fn', None)
                kwargs.setdefault('creationflags',
                                  subprocess.CREATE_NEW_PROCESS_GROUP)
            else:
                if for_matlab:  # pragma: matlab
                    import pty
                    # Matlab requires a tty so a pty is used here to allow
                    # the process to be lanched in a new process group.
                    # Related Materials:
                    # - https://www.mathworks.com/matlabcentral/answers/
                    #       359992-system-call-bizarre-behavior
                    # - https://gist.github.com/thepaul/1206753
                    # - https://stackoverflow.com/questions/30139401/
                    #       filter-out-command-that-needs-a-terminal-in-python-
                    #       subprocess-module
                    master_fd, slave_fd = pty.openpty()
                    kwargs.setdefault('stdin', slave_fd)

                kwargs.setdefault('preexec_fn', os.setpgrp)
        # if platform._is_win:  # pragma: windows
        #     kwargs.setdefault('universal_newlines', True)
        super(YggPopen, self).__init__(cmd_args, **kwargs)

    def kill(self, *args, **kwargs):
        r"""On windows using CTRL_BREAK_EVENT to kill the process."""
        if platform._is_win:  # pragma: windows
            self.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            super(YggPopen, self).kill(*args, **kwargs)


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
        YggPopen: Process that was started.

    """
    return YggPopen(*args, **kwargs)


def pprint_encoded(obj, *args, **kwargs):
    r"""Pretty print an object, catching encoding errors as necessary.

    Args:
        obj (object): Python object to pprint.
        *args: Additional arguments are passed to pprint.pformat.
        **kwargs: Additional keyword arguments are passed to pprint.pformat.

    """
    print_encoded(pprint.pformat(obj, *args, **kwargs))


def print_encoded(msg, *args, **kwargs):
    r"""Print bytes to stdout, encoding if possible.

    Args:
        msg (str, bytes): Message to print.
        *args: Additional arguments are passed to print.
        **kwargs: Additional keyword arguments are passed to print.


    """
    if not isinstance(msg, (str, bytes)):
        msg = str(msg)
    try:
        print(bytes2str(msg), *args, **kwargs)
    except (UnicodeEncodeError, UnicodeDecodeError):  # pragma: debug
        logger.debug("sys.stdout.encoding = %s, cannot print unicode",
                     sys.stdout.encoding)
        kwargs.pop('end', None)
        try:
            print(msg, *args, **kwargs)
        except UnicodeEncodeError:  # pragma: debug
            print(str2bytes(msg), *args, **kwargs)


class TimeOut(object):
    r"""Class for checking if a period of time has been elapsed.

    Args:
        max_time (float, bbol): Maximum period of time that should elapse before
            'is_out' returns True. If False, 'is_out' will never return True.
            Providing 0 indicates that 'is_out' should immediately return True.
        key (str, optional): Key that was used to register the timeout. Defaults
            to None.

    Attributes:
        max_time (float): Maximum period of time that should elapsed before
            'is_out' returns True.
        start_time (float): Result of time.time() at start.
        key (str): Key that was used to register the timeout.

    """

    def __init__(self, max_time, key=None):
        self.max_time = max_time
        self.start_time = time.perf_counter()
        self.key = key
        self.checked = False

    @property
    def elapsed(self):
        r"""float: Total time that has elapsed since the start."""
        return time.perf_counter() - self.start_time
    
    @property
    def is_out(self):
        r"""bool: True if there is not any time remaining. False otherwise."""
        if self.max_time is False:
            return False
        if (not self.checked) and (self.max_time == 0):
            out = False
        else:
            out = (self.elapsed > self.max_time)
        self.checked = True
        return out


# def single_use_method(func):
#     r"""Decorator for marking functions that should only be called once."""
#     def wrapper(*args, **kwargs):
#         if getattr(func, '_single_use_method_called', False):
#             logger.info("METHOD %s ALREADY CALLED" % func)
#             return
#         else:
#             func._single_use_method_called = True
#             return func(*args, **kwargs)
#     return wrapper


class YggLoggerAdapter(logging.LoggerAdapter):
    r"""Logger adapter for use with YggClass."""

    def __init__(self, class_name, instance_name, *args, **kwargs):
        self._class_name = class_name
        self._instance_name = instance_name
        super(YggLoggerAdapter, self).__init__(*args, **kwargs)
    
    def process(self, msg, kwargs):
        r"""Process logging message."""
        if _stack_in_log:  # pragma: no cover
            stack = inspect.stack()
            the_class = os.path.splitext(os.path.basename(
                stack[2][0].f_globals["__file__"]))[0]
            the_line = stack[2][2]
            the_func = stack[2][3]
            prefix = '%s(%s).%s[%d]' % (the_class,
                                        self._instance_name,
                                        the_func, the_line)
        else:
            prefix = '%s(%s)' % (self._class_name,
                                 self._instance_name)
        new_msg = '%s: %s' % (prefix, self.as_str(msg))
        return new_msg, kwargs

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


class YggClass(ComponentBase):
    r"""Base class for Ygg classes.

    Args:
        name (str): Name used for component in log messages.
        uuid (str, optional): Unique ID for this instance. Defaults to None
            and is assigned.
        working_dir (str, optional): Working directory. If not provided, the
            current working directory is used.
        timeout (float, optional): Maximum time (in seconds) that should be
            spent waiting on a process. Defaults to 60.
        sleeptime (float, optional): Time that class should sleep for when
            sleep is called. Defaults to 0.01.
        **kwargs: Additional keyword arguments are passed to the ComponentBase
            initializer.

    Attributes:
        name (str): Class name.
        uuid (str): Unique ID for this instance.
        sleeptime (float): Time that class should sleep for when sleep called.
        longsleep (float): Time that the class will sleep for when waiting for
            longer tasks to complete (10x longer than sleeptime).
        timeout (float): Maximum time that should be spent waiting on a process.
        working_dir (str): Working directory.
        errors (list): List of errors.
        sched_out (obj): Output from the last scheduled task with output.
        logger (logging.Logger): Logger object for this object.
        suppress_special_debug (bool): If True, special_debug log messages
            are suppressed.

    """

    _base_defaults = ['name', 'uuid', 'working_dir', 'timeout', 'sleeptime']

    def __init__(self, name=None, uuid=None, working_dir=None,
                 timeout=60.0, sleeptime=0.01, **kwargs):
        # Defaults
        if name is None:
            name = ''
        if uuid is None:
            uuid = str(uuid_gen.uuid4())
        if working_dir is None:
            working_dir = os.getcwd()
        # Assign attributes
        self._name = name
        self.uuid = uuid
        self.sleeptime = sleeptime
        self.longsleep = self.sleeptime * 10
        self.timeout = timeout
        self._timeouts = {}
        self.working_dir = working_dir
        self.errors = []
        self.sched_out = None
        self.suppress_special_debug = False
        self._periodic_logs = {}
        self._old_loglevel = None
        self._old_encoding = None
        self.debug_flag = False
        # Call super class, adding in schema properties
        for k in self._base_defaults:
            if k in self._schema_properties:
                kwargs[k] = getattr(self, k)
        super(YggClass, self).__init__(**kwargs)
        self.logger = YggLoggerAdapter(
            self.__class__.__name__, self.print_name,
            logging.getLogger(self.__module__), {})

    def __getstate__(self):
        state = super(YggClass, self).__getstate__()
        del state['logger']
        # thread_attr = {}
        for k, v in list(state.items()):
            if isinstance(v, (threading._CRLock, threading._RLock,
                              threading.Event, threading.Thread)):  # pragma: debug
                self.warning("Special treatment of threading objects "
                             "currently disabled.")
            # if isinstance(v, (threading._CRLock, threading._RLock)):
            #     thread_attr.setdefault('threading.RLock', [])
            #     thread_attr['threading.RLock'].append((k, (), {}))
            # elif isinstance(v, threading.Event):
            #     thread_attr.setdefault('threading.Event', [])
            #     thread_attr['threading.Event'].append((k, (), {}))
            # elif isinstance(v, threading.Thread):
            #     assert(not v.is_alive())
            #     attr = {'name': v._name, 'group': None,
            #             'daemon': v.daemon, 'target': v._target,
            #             'args': v._args, 'kwargs': v._kwargs}
            #     thread_attr.setdefault('threading.Thread', [])
            #     thread_attr['threading.Thread'].append((k, (), attr))
        # for attr_list in thread_attr.values():
        #     for k in attr_list:
        #         state.pop(k[0])
        # state['thread_attr'] = thread_attr
        return state

    def __setstate__(self, state):
        super(YggClass, self).__setstate__(state)
        self.logger = YggLoggerAdapter(
            self.__class__.__name__, self.print_name,
            logging.getLogger(self.__module__), {})

    def __deepcopy__(self, memo):
        r"""Don't deep copy since threads cannot be copied."""
        return self

    @property
    def name(self):
        r"""str: Name of the class object."""
        return self._name

    @property
    def print_name(self):
        r"""str: Name of the class object."""
        return self._name.replace('%', '%%')

    def language_info(self, languages):
        r"""Only do info debug message if the language is one of those specified."""
        if not isinstance(languages, (list, tuple)):
            languages = [languages]
        languages = [lang.lower() for lang in languages]
        if get_subprocess_language().lower() in languages:  # pragma: debug
            return self.logger.info
        else:
            return self.dummy_log

    @property
    def interface_info(self):
        r"""Only do info debug message if is interface."""
        if is_subprocess():  # pragma: debug
            return self.logger.info
        else:
            return self.dummy_log

    def debug_log(self):  # pragma: debug
        r"""Turn on debugging."""
        self.info("Setting debug_log")
        from yggdrasil.config import get_ygg_loglevel, set_ygg_loglevel
        self._old_loglevel = get_ygg_loglevel()
        set_ygg_loglevel('DEBUG')

    def reset_log(self):  # pragma: debug
        r"""Resetting logging to prior value."""
        from yggdrasil.config import set_ygg_loglevel
        if self._old_loglevel is not None:
            set_ygg_loglevel(self._old_loglevel)

    def pprint(self, obj, block_indent=0, indent_str='    ', **kwargs):
        r"""Use pprint to represent an object as a string.

        Args:
            obj (object): Python object to represent.
            block_indent (int, optional): Number of indents that should be
                placed in front of the entire block. Defaults to 0.
            indent_str (str, optional): String that should be used to indent.
                Defaults to 4 spaces.
            **kwargs: Additional keyword arguments are passed to pprint.pformat.

        Returns:
            str: String representation of object using pprint.

        """
        sblock = block_indent * indent_str
        out = sblock + pprint.pformat(obj, **kwargs).replace('\n', '\n' + sblock)
        return out

    def display(self, msg='', *args, **kwargs):
        r"""Print a message, no log."""
        msg, kwargs = self.logger.process(msg, kwargs)
        print(msg % args)

    def verbose_debug(self, *args, **kwargs):
        r"""Log a verbose debug level message."""
        return self.logger.log(9, *args, **kwargs)
        
    def dummy_log(self, *args, **kwargs):
        r"""Dummy log function that dosn't do anything."""
        pass

    def periodic_debug(self, key, period=10):
        r"""Log that should occur periodically rather than with every call.

        Arguments:
            key (str): Key that should be used to identify the debug message.
            period (int, optional): Period (in number of messages) that messages
                should be logged at. Defaults to 10.

        Returns:
            method: Logging method to be used.

        """
        if key in self._periodic_logs:
            self._periodic_logs[key] += 1
        else:
            self._periodic_logs[key] = 0
        if (self._periodic_logs[key] % period) == 0:
            return self.logger.debug
        else:
            return self.dummy_log

    @property
    def special_debug(self):
        r"""Log debug level message contingent of supression flag."""
        if not self.suppress_special_debug:
            return self.logger.debug
        else:
            return self.dummy_log

    @property
    def info(self):
        r"""Log an info level message."""
        return self.logger.info

    @property
    def debug(self):
        r"""Log a debug level message."""
        return self.logger.debug

    @property
    def critical(self):
        r"""Log a critical level message."""
        return self.logger.critical

    @property
    def warn(self):
        r"""Log a warning level message."""
        return self.logger.warning

    @property
    def warning(self):
        r"""Log a warning level message."""
        return self.logger.warning

    @property
    def error(self):
        r"""Log an error level message."""
        self.errors.append('ERROR')
        return self.logger.error
        # return super(YggClass, self).error

    @property
    def exception(self):
        r"""Log an exception level message."""
        exc_info = sys.exc_info()
        if exc_info is not None and exc_info != (None, None, None):
            self.errors.append('ERROR')
            return self.logger.exception
            # return super(YggClass, self).exception
        else:
            return self.error

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
        self.logger.info('%s(%s): ', self.__module__, self.print_name)

    def _task_with_output(self, func, *args, **kwargs):
        self.sched_out = func(*args, **kwargs)

    def sched_task(self, t, func, args=None, kwargs=None, store_output=False,
                   name=None):
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
            name (str, optional): Name for the task.

        Returns:
            threading.Timer: The timer object.

        """
        if args is None:
            args = []
        if kwargs is None:
            kwargs = {}
        self.sched_out = None
        if store_output:
            args = [func] + args
            func = self._task_with_output
        tobj = threading.Timer(t, func, args=args, kwargs=kwargs)
        if name is not None:
            tobj.name = name
        tobj.start()
        return tobj

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
    def timeout_key(self):  # pragma: no cover
        r"""str: Key identifying calling object and method."""
        return self.get_timeout_key()

    def get_timeout_key(self, key_level=0, key_suffix=None):
        r"""Return a key for a given level in the stack, relative to the
        function calling get_timeout_key.

        Args:
            key_level (int, optional): Positive integer indicating the level of
                the calling class and function/method that should be used to
                key the timeout. 0 is the class and function/method that is 2
                steps higher in the stack. Higher values use classes and
                function/methods further up in the stack. Defaults to 0.
            key_suffix (str, optional): String that should be appended to the
                end of the generated key. Defaults to None and is ignored.

        Returns:
            str: Key identifying calling object and method.

        """
        if _stack_in_timeout:  # pragma: debug
            stack = inspect.stack()
            fcn = stack[key_level + 2][3]
            cls = os.path.splitext(os.path.basename(stack[key_level + 2][1]))[0]
            key = '%s(%s).%s.%s' % (cls, self.print_name, fcn,
                                    threading.current_thread().name)
        else:
            key = '%s(%s).%s' % (str(self.__class__).split("'")[1], self.print_name,
                                 threading.current_thread().name)
        if key_suffix is not None:
            key += key_suffix
        return key

    def start_timeout(self, t=None, key=None, key_level=0, key_suffix=None):
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
            key_suffix (str, optional): String that should be appended to the
                end of the generated key. Defaults to None and is ignored.

        Raises:
            KeyError: If the key already exists.

        """
        if t is None:
            t = self.timeout
        if key is None:
            key = self.get_timeout_key(key_level=key_level, key_suffix=key_suffix)
        if key in self._timeouts:
            raise KeyError("Timeout already registered for %s" % key)
        self._timeouts[key] = TimeOut(t, key=key)
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
        
    def stop_timeout(self, key=None, key_level=0, key_suffix=None, quiet=False):
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
            key_suffix (str, optional): String that should be appended to the
                end of the generated key. Defaults to None and is ignored.
            quiet (bool, optional): If True, error message on timeout exceeded
                will be debug log. Defaults to False.

        Raises:
            KeyError: If there is not a timeout registered for the specified
                key.

        """
        if key is None:
            key = self.get_timeout_key(key_level=key_level, key_suffix=key_suffix)
        if key not in self._timeouts:
            raise KeyError("No timeout registered for %s" % key)
        t = self._timeouts[key]
        if t.is_out and t.max_time > 0:
            if quiet:
                self.debug("Timeout for %s at %5.2f/%5.2f s" % (
                    key, t.elapsed, t.max_time))
            else:
                self.info("Timeout for %s at %5.2f/%5.2f s" % (
                    key, t.elapsed, t.max_time))
        del self._timeouts[key]
