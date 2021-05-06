import re
import os
import numpy as np
import pandas as pd
import logging
from collections import OrderedDict
from yggdrasil import serialize, platform, constants
from yggdrasil.drivers.InterpretedModelDriver import InterpretedModelDriver
from yggdrasil.drivers.PythonModelDriver import PythonModelDriver
from yggdrasil.drivers.CModelDriver import CModelDriver
from yggdrasil.languages.R import install


logger = logging.getLogger(__name__)


class RModelDriver(InterpretedModelDriver):  # pragma: R
    r"""Base class for running R models.

    Args:
        name (str): Driver name.
        args (str or list): Argument(s) for running the model in matlab.
            Generally, this should be the full path to a Matlab script.
        **kwargs: Additional keyword arguments are passed to parent class's
            __init__ method.

    """
    _schema_subtype_description = ('Model is written in R.')
    language = 'R'
    language_aliases = ['r']
    language_ext = '.R'
    base_languages = ['python']
    default_interpreter = 'Rscript'
    # Dynamically setting the interface library causes circular a import so
    # it is defined here statically. For dynamic import, use the following:
    #     interface_library = PythonModelDriver.interface_library
    interface_library = 'yggdrasil'
    interface_dependencies = [x.split()[0] for x in
                              install.requirements_from_description()]
    # The Batch version causes output to saved to a file rather than directed to
    # stdout so use Rscript instead. For the batch version, use the following:
    #     default_interpreter_flags = ['CMD', 'BATCH' '--vanilla', '--silent']
    default_interpreter_flags = ['--default-packages=methods,utils']
    send_converters = {'table': serialize.consolidate_array}
    type_map = {
        'int': 'integer, bit64::integer64',
        'float': 'double',
        'string': 'character',
        'array': 'list',
        'object': 'list',
        'boolean': 'logical',
        'null': 'NA',
        'uint': 'integer',
        'complex': 'complex',
        'bytes': 'char (utf-8)',
        'unicode': 'char',
        '1darray': 'list',
        'ndarray': 'list',
        'ply': 'PlyDict',
        'obj': 'ObjDict',
        'schema': 'list'}
    function_param = {
        'import': 'source(\"{filename}\")',
        'istype': 'is({variable}, \"{type}\")',
        'len': 'length({variable})',
        'index': '{variable}[[{index}]]',
        'first_index': 1,
        'interface': 'library(yggdrasil)',
        'input': '{channel} <- YggInterface(\"YggInput\", \"{channel_name}\")',
        'output': '{channel} <- YggInterface(\"YggOutput\", \"{channel_name}\")',
        'python_interface': ('{channel} <- YggInterface(\"{python_interface}\", '
                             '\"{channel_name}\")'),
        'python_interface_format': ('{channel} <- YggInterface('
                                    '\"{python_interface}\", '
                                    '\"{channel_name}\", '
                                    '\"{format_str}\")'),
        'recv_function': '{channel}$recv',
        'send_function': '{channel}$send',
        'multiple_outputs': 'c({outputs})',
        'multiple_outputs_def': 'list({outputs})',
        'true': 'TRUE',
        'false': 'FALSE',
        'not': '!',
        'and': '&&',
        'comment': '#',
        'indent': 2 * ' ',
        'quote': '\"',
        'print_generic': 'print({object})',
        'print': 'print(\"{message}\")',
        'fprintf': 'print(sprintf(\"{message}\", {variables}))',
        'error': 'stop(\"{error_msg}\")',
        'block_end': '}',
        'if_begin': 'if ({cond}) {{',
        'if_elif': '}} else if ({cond}) {{',
        'if_else': '}} else {{',
        'for_begin': 'for ({iter_var} in {iter_begin}:{iter_end}) {{',
        'while_begin': 'while ({cond}) {{',
        'try_begin': 'tryCatch({',
        'try_except': '}}, error = function({error_var}) {{',
        'try_end': '})',
        'assign': '{name} <- {value}',
        'assign_mult': '{name} %<-% {value}',
        'function_def_begin': '{function_name} <- function({input_var}) {{',
        'return': 'return({output_var})',
        'function_def_regex': (
            r'{function_name} *(?:(?:\<-)|(?:=)) *function'
            r'\((?P<inputs>(?:.|(?:\r?\n))*?)\)\s*\{{'
            r'(?P<body>(?:.|(?:\r?\n))*?)'
            r'(?:return\((list\()?'
            r'(?P<outputs>(?:.|(?:\r?\n))*?)(?(3)\))\)'
            r'(?:.|(?:\r?\n))*?\}})'
            r'|(?:\}})'),
        'inputs_def_regex': r'\s*(?P<name>.+?)\s*(?:,|$)',
        'outputs_def_regex': r'\s*(?P<name>.+?)\s*(?:,|$)',
        'interface_regex': (
            r'(?P<indent>[ \t]*)'
            r'(?P<variable>[a-zA-Z\_]+[a-zA-Z\_0-9]*)\s*\<\-\s*'
            r'YggInterface\(\'(?P<class>[a-zA-Z\_]+[a-zA-Z\_0-9]*)\'\s*\,\s*'
            r'\'(?P<channel>[a-zA-Z\_]+[a-zA-Z\_0-9]*)\'\s*'
            r'(?P<args>[^\)]*)\)')}
    brackets = (r'{', r'}')
    zero_based = False

    @classmethod
    def is_library_installed(cls, lib, **kwargs):
        r"""Determine if a dependency is installed.

        Args:
            lib (str): Name of the library that should be checked.
            **kwargs: Additional keyword arguments are ignored.

        Returns:
            bool: True if the library is installed, False otherwise.

        """
        if lib not in cls._library_cache:
            try:
                cls.run_executable(['-e', 'library(%s)' % lib.split()[0]])
                cls._library_cache[lib] = True
            except RuntimeError as e:
                logger.info('Error checking for R library %s: %s' % (lib, e))
                cls._library_cache[lib] = False
        return cls._library_cache[lib]
        
    @classmethod
    def language_version(cls, **kwargs):
        r"""Determine the version of this language.

        Args:
            **kwargs: Keyword arguments are passed to the parent class's
                method.

        Returns:
            str: Version of compiler/interpreter for this language.

        """
        kwargs.setdefault('skip_interpreter_flags', True)
        return super(RModelDriver, cls).language_version(**kwargs)

    def run_model(self, *args, **kwargs):
        r"""Run the model. Unless overridden, the model will be run using
        run_executable.

        Args:
            *args: Arguments are passed to the parent class's method.
            **kwargs: Keyword arguments are passed to the parent class's
                method.

        """
        if self.with_valgrind:
            interp = kwargs.pop('interpreter', self.get_interpreter())
            interp_flags = kwargs.pop('interpreter_flags', [])
            if 'Rscript' in interp:
                interp = 'R'.join(interp.rsplit('Rscript', 1))
                interp_flags = []
                kwargs['skip_interpreter_flags'] = True
            interp_flags += [
                '--vanilla', '-d', 'valgrind %s'
                % ' '.join(self.valgrind_flags), '-f']
            kwargs['interpreter'] = interp
            kwargs['interpreter_flags'] = interp_flags
            kwargs['debug_flags'] = []
        return super(RModelDriver, self).run_model(*args, **kwargs)
        
    def set_env(self, **kwargs):
        r"""Get environment variables that should be set for the model process.

        Returns:
            dict: Environment variables for the model process.

        """
        out = super(RModelDriver, self).set_env(**kwargs)
        out['RETICULATE_PYTHON'] = PythonModelDriver.get_interpreter()
        if CModelDriver.is_language_installed():
            c_linker = CModelDriver.get_tool('linker')
            search_dirs = c_linker.get_search_path(env_only=True)
            out = CModelDriver.update_ld_library_path(out, paths_to_add=search_dirs,
                                                      add_to_front=True)
        return out
        
    @classmethod
    def comm_atexit(cls, comm):  # pragma: no cover
        r"""Operations performed on comm at exit including draining receive.
        
        Args:
            comm (CommBase): Communication object.

        """
        if comm.direction == 'recv':
            while comm.recv(timeout=0)[0]:
                comm.sleep()
        else:
            comm.send_eof()
            comm.linger()
        if not getattr(comm, 'dont_backlog', True):
            comm.linger_close()

    @classmethod
    def python2language(cls, pyobj):
        r"""Prepare a python object for transformation in R.

        Args:
            pyobj (object): Python object.

        Returns:
            object: Python object in a form that is R friendly.

        """
        logger.debug("python2language: %s, %s" % (pyobj, type(pyobj)))
        if isinstance(pyobj, tuple):
            return tuple([cls.python2language(x) for x in pyobj])
        elif isinstance(pyobj, list):
            return [cls.python2language(x) for x in pyobj]
        elif isinstance(pyobj, OrderedDict):
            return OrderedDict([(cls.python2language(k),
                                 cls.python2language(v))
                                for k, v in pyobj.items()])
        elif isinstance(pyobj, dict):
            return {cls.python2language(k): cls.python2language(v)
                    for k, v in pyobj.items()}
        elif isinstance(pyobj, np.string_):
            return pyobj.decode("utf-8")
        elif isinstance(pyobj, pd.DataFrame):
            # R dosn't have int64 and will cast 64bit ints as floats if passed
            # without casting them to int32 first
            for n in pyobj.columns:
                if pyobj[n].dtype == np.dtype('int64'):
                    pyobj[n] = pyobj[n].astype('int32')
        return pyobj
    
    @classmethod
    def write_model_wrapper(cls, model_file, model_function, **kwargs):
        r"""Return the lines required to wrap a model function as an integrated
        model.

        Args:
            model_file (str): Full path to the file containing the model
                function's declaration.
            model_function (str): Name of the model function.
            **kwargs: Additional keyword arguments are passed to the parent
                class's method.

        Returns:
            list: Lines of code wrapping the provided model with the necessary
                code to run it as part of an integration.

        """
        if platform._is_win:  # pragma: windows
            model_file = model_file.replace('\\', '/')
        return super(RModelDriver, cls).write_model_wrapper(
            model_file, model_function, **kwargs)

    @classmethod
    def write_executable_import(cls, **kwargs):
        r"""Add import statements to executable lines.
       
        Args:
            **kwargs: Keyword arguments for import statement.

        Returns:
            list: Lines required to complete the import.
 
        """
        if kwargs.get('filename', None) and os.path.isfile(kwargs['filename']):
            with open(kwargs['filename'], 'r') as fd:
                contents = fd.read()
            # For functions that contain interface calls, split them out
            # and assign them to the global level
            if re.search(cls.function_param['interface_regex'], contents):
                new_contents = contents
                for m in re.finditer(cls.function_param['interface_regex'],
                                     contents):
                    mdict = m.groupdict()
                    assert('global_scope' in mdict['args'])
                    # if 'global_scope' not in mdict['args']:
                    #     mdict['args'] += ', global_scope=TRUE'
                    new_channel = (
                        '{indent}if (!exists("{variable}")) {{\n'
                        '{indent}  assign("{variable}", YggInterface('
                        '\'{class}\', \'{channel}\'{args}), '
                        'envir = .GlobalEnv)\n'
                        '{indent}}}').format(**mdict)
                    new_contents = new_contents.replace(m.group(0),
                                                        new_channel)
                out = new_contents.splitlines()
                return out
        return super(RModelDriver, cls).write_executable_import(**kwargs)

    # The following is only provided for the yggcc CLI for building R
    # packages and should not be used directly
    @classmethod
    def call_compiler(cls, package_dir, toolname=None, flags=None,
                      language='c++', verbose=False,
                      use_ccache=False):  # pragma: no cover
        r"""Build an R package w/ the yggdrasil compilers.

        Args:
            package_dir (str): Full path to the package directory.
            toolname (str, optional): Compilation tool that should be used.
                Defaults to None and the default tools will be used.
            flags (list, optional): Additional flags that should be passed
                to the build command. Defaults to [].
            language (str, optional): Language that the package is written in
                (e.g. c, fortran). Defautls to 'c++'.
            verbose (bool, optional): If True, information about the build
                process will be displayed. Defaults to False.
            use_ccache (bool, optional): If True, ccache will be added to
                the compilation executable. Defaults to False.

        """
        import shutil
        import subprocess
        from yggdrasil.components import import_component
        if flags is None:
            flags = []
        if isinstance(package_dir, list):
            assert(len(package_dir) == 1)
            package_dir = package_dir[0]
        cexec_vars = {'c': ['CC', 'CC_FOR_BUILD'],
                      'c++': ['CXX', 'CPP', 'CXX98', 'CXX11', 'CXX14',
                              'CXX17', 'CXX20', 'CXX_FOR_BUILD'],
                      'fortran': ['FC', 'F77']}
        cflag_vars = {'c': ['CFLAGS'],
                      'c++': ['CXXFLAGS', 'CXX98FLAGS', 'CXX11FLAGS',
                              'CXX14FLAGS', 'CXX17FLAGS', 'CXX20FLAGS'],
                      'fortran': ['FFFLAGS', 'FCFLAGS']}
        cstd_vars = {'c': [],
                     'c++': ['CXXSTD', 'CXX11STD', 'CXX14STD',
                             'CXX17STD', 'CXX20STD'],
                     'fortran': []}
        env = os.environ.copy()
        new_env = {}
        for x in constants.LANGUAGES['compiled']:
            # for x in [language]:
            drv = import_component('model', x)
            compiler = drv.get_tool('compiler', toolname=toolname)
            # archiver = compiler.archiver()
            env = drv.set_env_compiler(existing=env, compiler=compiler)
            cexec = compiler.get_executable(full_path=True)
            if use_ccache and shutil.which('ccache'):
                cexec = '%s %s' % ('ccache', cexec)
                env['CCACHE_NOHASHDIR'] = 'true'
            kws = {}
            if x == 'c++':
                kws['skip_standard_flag'] = True
            cflags0 = drv.get_compiler_flags(for_model=True, toolname=toolname,
                                             dry_run=True, compiler=compiler,
                                             dont_link=True, **kws)
            lflags = drv.get_linker_flags(for_model=True, toolname=toolname,
                                          dry_run=True, libtype='shared')
            # Remove flags that are unnecessary
            cflags = []
            stdflags = []
            for k in cflags0:
                if k.startswith("-std="):
                    stdflags.append(k)
                else:
                    cflags.append(k)
            for k in ['-c']:
                if k in cflags:
                    cflags.remove(k)
            for k in ['-shared']:
                if k in lflags:
                    lflags.remove(k)
            for k in cexec_vars[x]:
                env[k] = cexec
                new_env[k] = cexec
            for k in cflag_vars[x]:
                env[k] = ''
                new_env[k] = ' '.join(cflags)
            for k in cstd_vars[x]:
                env[k] = ''
                new_env[k] = ' '.join(stdflags)
            if language == x:
                env['LDFLAGS'] = ''
                new_env['LDFLAGS'] = ' '.join(lflags)
        cmd = ['R', 'CMD', 'INSTALL', '--no-html', '--no-help', '--no-docs',
               '--no-demo', '--no-multiarch', package_dir] + flags
        makevar = os.path.expanduser(os.path.join('~', '.R', 'Makevars'))
        makevar_copy = makevar + '_copy'
        try:
            if os.path.isfile(makevar):
                shutil.move(makevar, makevar_copy)
            with open(makevar, 'w') as fd:
                for k, v in new_env.items():
                    if k.startswith('PKG_'):
                        fd.write('%s+=%s\n' % (k, v))
                    else:
                        fd.write('%s=%s\n' % (k, v))
            if verbose:
                with open(makevar, 'r') as fd:
                    print(fd.read())
            subprocess.check_call(cmd, env=env)
        finally:
            os.remove(makevar)
            if os.path.isfile(makevar_copy):
                shutil.move(makevar_copy, makevar)
