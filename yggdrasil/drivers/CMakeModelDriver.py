import os
import re
import sys
import copy
import shutil
import logging
import sysconfig
import threading
from collections import OrderedDict
from yggdrasil import platform, constants
from yggdrasil.components import import_component
from yggdrasil.drivers.CompiledModelDriver import (
    LinkerBase, get_compilation_tool, get_compatible_tool)
from yggdrasil.drivers.BuildModelDriver import (
    BuildModelDriver, BuildToolBase)
from yggdrasil.drivers import CModelDriver


logger = logging.getLogger(__name__)
_buildfile_locks_lock = threading.RLock()
_buildfile_locks = {}


def get_buildfile_lock(fname, context):
    r"""Get a lock for a buildfile to prevent simultaneous access,
    creating one as necessary.

    Args:
        name (str): Build file.
        context (threading.Context): Threading context.

    Returns:
        threading.RLock: Lock for the buildfile.

    """
    global _buildfile_locks
    with _buildfile_locks_lock:
        if fname not in _buildfile_locks:
            _buildfile_locks[fname] = context.RLock()
    return _buildfile_locks[fname]


class CMakeConfigure(BuildToolBase):
    r"""CMake configuration tool."""
    toolname = 'cmake'
    languages = ['cmake']
    is_linker = False
    default_flags = []  # '-H']
    flag_options = OrderedDict([('definitions', '-D%s'),
                                ('sourcedir', ''),  # '-S'
                                ('builddir', '-B%s'),
                                ('configuration', '-DCMAKE_BUILD_TYPE=%s'),
                                ('generator', '-G%s'),
                                ('toolset', '-T%s'),
                                ('platform', '-A%s')])
    output_key = None
    compile_only_flag = None
    default_builddir = '.'
    default_archiver = False
    add_libraries = False
    product_files = ['Makefile', 'CMakeCache.txt',
                     'cmake_install.cmake', 'CMakeFiles']
    remove_product_exts = ['CMakeFiles']

    @staticmethod
    def before_registration(cls):
        r"""Operations that should be performed to modify class attributes prior
        to registration including things like platform dependent properties and
        checking environment variables for default settings.
        """
        BuildToolBase.before_registration(cls)
        if platform._is_win:  # pragma: windows
            cls.product_files += ['ALL_BUILD.vcxproj',
                                  'ALL_BUILD.vcxproj.filters',
                                  'Debug', 'Release', 'Win32', 'Win64', 'x64',
                                  'ZERO_CHECK.vcxproj',
                                  'ZERO_CHECK.vcxproj.filters']
            cls.remove_product_exts += ['Debug', 'Release', 'Win32', 'Win64',
                                        'x64', '.dir']

    # The method generator and generator2toolset will only be called
    # if the VC 15 build tools are installed by MSVC 19+ which is not
    # currently supported by Appveyor CI.
    @classmethod
    def generator(cls, return_default=False, default=None, **kwargs):  # pragma: no cover
        r"""Determine the generator that should be used.

        Args:
            return_default (bool, optional): If True, the default generator will
                be returned even if the environment variable is set. Defaults to
                False.
            default (str, optional): Value that should be returned if a generator
                cannot be located. Defaults to None.
            **kwargs: Keyword arguments are passed to cls.call.

        Returns:
            str: Name of the generator.

        """
        out = default
        if not return_default:
            out = os.environ.get('CMAKE_GENERATOR', default)
        if not out:
            lines = cls.call(['--help'], skip_flags=True,
                             allow_error=True, **kwargs)
            if 'Generators' not in lines:  # pragma: debug
                raise RuntimeError("Generator call failed:\n%s" % lines)
            gen_list = (lines.split('Generators')[-1]).splitlines()
            for x in gen_list:
                if x.startswith('*'):
                    out = (x.split('=')[0]).strip()
                    out = (out.strip('*')).strip()
                    break
        return out

    @classmethod
    def generator2toolset(cls, generator):  # pragma: no cover
        r"""Determine the toolset string option that corresponds to the provided
        generator name.

        Args:
            generator (str): Name of the generator.

        Returns:
            str: Name of the toolset.

        Raises:
            NotImplementedError: If the platform is not windows.
            ValueError: If the generator is not a flavor of Visual Studio.
            ValueError: If a tool set cannot be located for the specified generator.

        """
        if not platform._is_win:  # pragma: debug
            raise NotImplementedError("generator2toolset only available on Windows")
        if not generator.startswith("Visual Studio"):  # pragma: debug
            raise ValueError("Toolsets only available for Visual Studio generators.")
        if generator.endswith(('Win64', 'ARM', 'IA64')):
            generator = (generator.rsplit(' ', 1)[0]).strip()
        vs_generator_map = {'Visual Studio 16 2019': 'v142',
                            'Visual Studio 15 2017': 'v141',
                            'Visual Studio 14 2015': 'v140',
                            'Visual Studio 12 2013': 'v120',
                            'Visual Studio 11 2012': 'v110',
                            'Visual Studio 10 2010': 'v100',
                            'Visual Studio 9 2008': 'v90'}
        out = vs_generator_map.get(generator, None)
        if out is None:  # pragma: debug
            raise ValueError("Failed to locate toolset for generator: %s" % generator)
        return out
        
    @classmethod
    def append_product(cls, products, src, new, **kwargs):
        r"""Append a product to the specified list along with additional values
        indicated by cls.product_exts.

        Args:
            products (list): List of of existing products that new product
                should be appended to.
            src (list): Input arguments to compilation call that was used to
                generate the output file (usually one or more source files).
            new (str): New product that should be appended to the list.
            **kwargs: Additional keyword arguments are passed to the parent
                class's method.

        """
        kwargs.setdefault('new_dir', new)
        kwargs.setdefault('dont_append_src', True)
        return super(CMakeConfigure, cls).append_product(products, src,
                                                         new, **kwargs)
        
    @classmethod
    def get_output_file(cls, src, dont_link=False, dont_build=None,
                        sourcedir=None, builddir=None, working_dir=None,
                        **kwargs):
        r"""Determine the appropriate output file or directory that will result
        when configuring/building a given source directory.

        Args:
            src (str): Directory containing source files being compiled.
            dont_link (bool, optional): If True, the result assumes that the
                source is just compiled and not linked. If False, the result
                will be the final result after linking.
            dont_build (bool, optional): Alias for dont_link. If not None, this
                keyword overrides the value of dont_link. Defaults to None.
            sourcedir (str, optional): Directory where sources files are located.
                Defaults to None. If None, src will be used to determine the
                value.
            builddir (str, optional): Directory where build tree should be
                created. Defaults to None. If None, sourcedir will be used.
            working_dir (str, optional): Working directory where output file
                should be located. Defaults to None and is ignored.
            **kwargs: Additional keyword arguments are ignored unless dont_link
                is False; then they are passed to get_linker_output_file

        Returns:
            str: Full path to file that will be produced.

        """
        if dont_build is not None:
            dont_link = dont_build
        if isinstance(src, list):
            src = src[0]
        if sourcedir is None:
            if os.path.isfile(src) or os.path.splitext(src)[-1]:
                sourcedir = os.path.dirname(src)
            else:
                sourcedir = src
        if builddir is None:
            builddir = os.path.normpath(os.path.join(sourcedir,
                                                     cls.default_builddir))
        if dont_link:
            out = builddir
            if (not os.path.isabs(out)) and (working_dir is not None):
                out = os.path.normpath(os.path.join(working_dir, out))
        else:
            out = super(CMakeConfigure, cls).get_output_file(
                src, dont_link=dont_link, sourcedir=sourcedir,
                builddir=builddir, working_dir=working_dir, **kwargs)
        return out

    @classmethod
    def call(cls, args, **kwargs):
        r"""Call the tool with the provided arguments. If the first argument
        resembles the name of the tool executable, the executable will not be
        added.

        Args:
            args (list): The arguments that should be passed to the tool.
            **kwargs: Additional keyword arguments are passed to the parent
                class's method and the associated linker/archiver's call method
                if dont_link is False.

        Returns:
            str: Output to stdout from the command execution if skip_flags is
                True, produced file otherwise.

        """
        try:
            out = super(CMakeConfigure, cls).call(args, **kwargs)
        except RuntimeError as e:
            if platform._is_win:  # pragma: windows
                error_MSB4019 = (r'error MSB4019: The imported project '
                                 r'"C:\Microsoft.Cpp.Default.props" was not found.')
                error_NOVS = r'could not find any instance of Visual Studio.'
                # This will only be called if the VC 15 build tools
                # are installed by MSVC 19+ which is not currently
                # supported by Appveyor CI.
                if (error_MSB4019 in str(e)) or (error_NOVS in str(e)):  # pragma: debug
                    old_generator = os.environ.get('CMAKE_GENERATOR', None)
                    new_generator = cls.generator(return_default=True)
                    if old_generator and (old_generator != new_generator):
                        kwargs['generator'] = new_generator
                        kwargs['toolset'] = cls.generator2toolset(old_generator)
                        return super(CMakeConfigure, cls).call(args, **kwargs)
            raise
        return out

    @classmethod
    def get_flags(cls, sourcedir='.', builddir=None, target_compiler=None,
                  target_linker=None, **kwargs):
        r"""Get a list of configuration/generation flags.

        Args:
            sourcedir (str, optional): Directory containing the source files to
                be compiled and the target CMakeLists.txt file. Defaults to '.'
                (the current working directory).
            builddir (str, optional): Directory that will contain the build tree.
                Defaults to '.' (this current working directory).
            target_compiler (str, optional): Compiler that should be used by cmake.
                Defaults to None and the default for the target language will be used.
            target_linker (str, optional): Linker that should be used by cmake.
                Defaults to None and the default for the target language will be used.
            **kwargs: Additional keyword arguments are passed to the parent
                class's method.

        Returns:
            list: Compiler flags.

        Raises:
            RuntimeError: If dont_link is True and the provide outfile and
                builddir keyword arguments point to conflicting paths.
            ValueError: If 'include_dirs' is set ('sourcedir' should be used
                for cmake to specify the location of the source).

        """
        if kwargs.get('dont_link', False):
            if builddir is None:
                outfile = kwargs.get('outfile', None)
                if outfile is None:
                    builddir = os.path.normpath(os.path.join(sourcedir,
                                                             cls.default_builddir))
                else:
                    builddir = outfile
        kwargs.setdefault('definitions', [])
        kwargs['definitions'].append('CMAKE_VERBOSE_MAKEFILE:BOOL=ON')
        if CModelDriver._osx_sysroot is not None:
            kwargs.setdefault('definitions', [])
            kwargs['definitions'].append(
                'CMAKE_OSX_SYSROOT=%s' % CModelDriver._osx_sysroot)
            if os.environ.get('MACOSX_DEPLOYMENT_TARGET', None):
                kwargs['definitions'].append(
                    'CMAKE_OSX_DEPLOYMENT_TARGET=%s'
                    % os.environ['MACOSX_DEPLOYMENT_TARGET'])
        # Pop target (used for build stage file name, but not for any other
        # part of the build stage)
        kwargs.pop('target', None)
        # Add env prefix
        # for iprefix in cls.get_env_prefixes():
        #     kwargs.setdefault('definitions', [])
        #     kwargs['definitions'].append('CMAKE_PREFIX_PATH=%s'
        #                                  % os.path.join(iprefix, 'lib'))
        #     kwargs['definitions'].append('CMAKE_LIBRARY_PATH=%s'
        #                                  % os.path.join(iprefix, 'lib'))
        out = super(CMakeConfigure, cls).get_flags(sourcedir=sourcedir,
                                                   builddir=builddir, **kwargs)
        if platform._is_win and ('platform' not in kwargs):  # pragma: windows
            generator = kwargs.get('generator', None)
            if generator is None:
                generator = cls.generator()
            if (((generator is not None) and generator.startswith('Visual')
                 and (not generator.endswith(('Win64', 'ARM')))
                 and platform._is_64bit)):
                out.append('-DCMAKE_GENERATOR_PLATFORM=x64')
        if target_compiler in ['cl', 'cl++']:
            compiler = get_compilation_tool('compiler', target_compiler)
            if target_linker is None:
                linker = compiler.linker()
            else:
                linker = get_compilation_tool('linker', target_linker)
            cmake_vars = {'c_compiler': 'CMAKE_C_COMPILER',
                          'c_flags': 'CMAKE_C_FLAGS',
                          'c++_compiler': 'CMAKE_CXX_COMPILER',
                          'c++_flags': 'CMAKE_CXX_FLAGS',
                          'fortran_compiler': 'CMAKE_Fortran_COMPILER',
                          'fortran_flags': 'CMAKE_Fortran_FLAGS'}
            for k in constants.LANGUAGES['compiled']:
                try:
                    itool = get_compatible_tool(compiler, 'compiler', k)
                except ValueError:
                    continue
                if not itool.is_installed():  # pragma: debug
                    continue
                if itool.toolname in ['cl', 'cl++']:
                    out.append('-D%s:FILEPATH=%s' % (
                        cmake_vars['%s_compiler' % k],
                        itool.get_executable(full_path=True)))
                    out.append('-D%s=%s' % (
                        cmake_vars['%s_flags' % k], ''))
            out.append('-DCMAKE_LINKER=%s' % linker.get_executable(full_path=True))
        return out

    @classmethod
    def get_executable_command(cls, args, **kwargs):
        r"""Determine the command required to run the tool using the specified
        arguments and options.

        Args:
            args (list): The arguments that should be passed to the tool. If
                skip_flags is False, these are treated as input files that will
                be used by the tool.
            **kwargs: Additional keyword arguments are passed to the parent
                class's method.

        Returns:
            str: Output to stdout from the command execution.

        """
        assert(len(args) == 1)
        new_args = []
        if (args == cls.version_flags) or ('--help' in args):
            new_args = args
        if not kwargs.get('skip_flags', False):
            sourcedir = kwargs.get('sourcedir', args[0])
            if sourcedir != args[0]:  # pragma: debug
                raise RuntimeError(("The argument list "
                                    "contents (='%s') and 'sourcedir' (='%s') "
                                    "keyword specify the same thing, but those "
                                    "provided do not match.")
                                   % (args[0], sourcedir))
            kwargs['sourcedir'] = args[0]
        return super(CMakeConfigure, cls).get_executable_command(new_args, **kwargs)
    
    @classmethod
    def fix_path(cls, x, is_gnu=False):
        r"""Fix paths so that they conform to the format expected by the OS
        and/or build tool."""
        if platform._is_win:  # pragma: windows
            # if ' ' in x:
            #     x = "%s" % x
            if is_gnu:
                x = x.replace('\\', re.escape('/'))
            else:
                x = x.replace('\\', re.escape('\\'))
        return x
        
    @classmethod
    def create_include(cls, fname, target,
                       compiler=None, compiler_flags=None,
                       linker=None, linker_flags=None,
                       library_flags=None, internal_library_flags=None,
                       configuration='Release', verbose=False, **kwargs):
        r"""Create CMakeList include file with necessary includes,
        definitions, and linker flags.

        Args:
            fname (str): File where the include file should be saved.
            target (str): Target that links should be added to.
            compiler (CompilerBase): Compiler that should be used to generate the
                list of compilation flags.
            compile_flags (list, optional): Additional compile flags that
                should be set. Defaults to [].
            linker (LinkerBase): Linker that should be used to generate the
                list of compilation flags.
            linker_flags (list, optional): Additional linker flags that
                should be set. Defaults to [].
            library_flags (list, optional): List of library flags to add.
                Defaults to [].
            internal_library_flags (list, optional): List of library flags
                associated with yggdrasil libraries. Defaults to [].
            configuration (str, optional): Build type/configuration that should
                be built. Defaults to 'Release'. Only used on Windows to
                determin the standard library.
            verbose (bool, optional): If True, the contents of the created file
                are displayed. Defaults to False.
            **kwargs: Additional keyword arguments are ignored.

        Returns:
            list: Lines that should be added before the executable is defined
                in the CMakeLists.txt (e.g. LINK_DIRECTORIES commands).

        Raises:
            ValueError: If a linker or compiler flag cannot be interpreted.

        """
        if target is None:
            target = '${PROJECT_NAME}'
        if compiler_flags is None:
            compiler_flags = []
        if linker_flags is None:
            linker_flags = []
        if library_flags is None:
            library_flags = []
        if internal_library_flags is None:
            internal_library_flags = []
        assert(compiler is not None)
        assert(linker is not None)
        lines = []
        pretarget_lines = []
        preamble_lines = []
        # Suppress warnings on windows about the security of strcpy etc.
        # and target x64 if the current platform is 64bit
        is_gnu = True
        if platform._is_win:  # pragma: windows
            is_gnu = compiler.is_gnu
            new_flags = compiler.default_flags
            def_flags = compiler.get_env_flags()
            if (((compiler.toolname in ['cl', 'msvc', 'cl++'])
                 and (not (('/MD' in def_flags) or ('-MD' in def_flags))))):
                if configuration.lower() == 'debug':  # pragma: debug
                    new_flags.append("/MTd")
                else:
                    new_flags.append("/MT")
            else:
                preamble_lines += ['SET(CMAKE_FIND_LIBRARY_PREFIXES "")',
                                   'SET(CMAKE_FIND_LIBRARY_SUFFIXES ".lib" ".dll")']
            for x in new_flags:
                if x not in compiler_flags:
                    compiler_flags.append(x)
        # Find Python using cmake
        # https://martinopilia.com/posts/2018/09/15/building-python-extension.html
        # preamble_lines.append('find_package(PythonInterp REQUIRED)')
        # preamble_lines.append('find_package(PythonLibs REQUIRED)')
        # preamble_lines.append('INCLUDE_DIRECTORIES(${PYTHON_INCLUDE_DIRS})')
        # lines.append('TARGET_LINK_LIBRARIES(%s ${PYTHON_LIBRARIES})'
        #              % target)
        # Compilation flags
        for x in compiler_flags:
            if x.startswith('-D'):
                preamble_lines.append('ADD_DEFINITIONS(%s)' % x)
            elif x.startswith('-I'):
                xdir = cls.fix_path(x.split('-I', 1)[-1], is_gnu=is_gnu)
                new_dir = 'INCLUDE_DIRECTORIES(%s)' % xdir
                if new_dir not in preamble_lines:
                    preamble_lines.append(new_dir)
            elif x.startswith('-std=c++') or x.startswith('/std=c++'):
                new_def = 'SET(CMAKE_CXX_STANDARD %s)' % x.split('c++')[-1]
                if new_def not in preamble_lines:
                    preamble_lines.append(new_def)
            elif x.startswith('-') or x.startswith('/'):
                new_def = 'ADD_DEFINITIONS(%s)' % x
                if new_def not in preamble_lines:
                    preamble_lines.append(new_def)
            else:
                raise ValueError("Could not parse compiler flag '%s'." % x)
        # Linker flags
        for x in linker_flags:
            if x.startswith('-l'):
                lines.append('TARGET_LINK_LIBRARIES(%s %s)' % (target, x))
            elif x.startswith('-L'):
                libdir = cls.fix_path(x.split('-L')[-1], is_gnu=is_gnu)
                pretarget_lines.append('LINK_DIRECTORIES(%s)' % libdir)
            elif x.startswith('/LIBPATH:'):  # pragma: windows
                libdir = x.split('/LIBPATH:')[-1]
                if '"' in libdir:
                    libdir = libdir.split('"')[1]
                libdir = cls.fix_path(libdir, is_gnu=is_gnu)
                pretarget_lines.append('LINK_DIRECTORIES(%s)' % libdir)
            elif os.path.isfile(x):
                library_flags.append(x)
            elif x.startswith('-mlinker-version='):  # pragma: version
                # Currently this only called when clang is >=10
                # and ld is <520 or mlinker is set in the env
                # flags via CFLAGS, CXXFLAGS, etc.
                preamble_lines.insert(0, 'target_link_options(%s PRIVATE %s)'
                                      % (target, x))
            elif x.startswith('-') or x.startswith('/'):
                raise ValueError("Could not parse linker flag '%s'." % x)
            else:
                lines.append('TARGET_LINK_LIBRARIES(%s %s)' % (target, x))
        # Libraries
        for x in library_flags:
            xorig = x
            xd, xf = os.path.split(x)
            xl, xe = os.path.splitext(xf)
            xl = linker.libpath2libname(xf)
            x = cls.fix_path(x, is_gnu=is_gnu)
            xd = cls.fix_path(xd, is_gnu=is_gnu)
            xn = os.path.splitext(xl)[0]
            new_dir = 'LINK_DIRECTORIES(%s)' % xd
            if new_dir not in preamble_lines:
                pretarget_lines.append(new_dir)
            if cls.add_libraries or (xorig in internal_library_flags):
                # Version adding library
                lines.append('if (NOT TARGET %s)' % xl)
                if xe.lower() in ['.so', '.dll', '.dylib']:
                    lines.append('    ADD_LIBRARY(%s SHARED IMPORTED)' % xl)
                else:
                    lines.append('    ADD_LIBRARY(%s STATIC IMPORTED)' % xl)
                lines += ['    SET_TARGET_PROPERTIES(',
                          '        %s PROPERTIES' % xl]
                # Untested on appveyor, but required when using dynamic
                # library directly (if dll2a not used).
                # if xe.lower() == '.dll':
                #     lines.append('        IMPORTED_IMPLIB %s'
                #                  % x.replace('.dll', '.lib'))
                lines += ['        IMPORTED_LOCATION %s)' % x,
                          'endif()',
                          'TARGET_LINK_LIBRARIES(%s %s)' % (target, xl)]
            else:
                # Version finding library
                lines.append('FIND_LIBRARY(%s_LIBRARY NAMES %s %s HINTS %s)'
                             % (xn.upper(), xf, xn, xd))
                lines.append('TARGET_LINK_LIBRARIES(%s ${%s_LIBRARY})'
                             % (target, xn.upper()))
        lines = preamble_lines + lines
        log_msg = (
            'CMake compiler flags:\n\t%s\n'
            'CMake linker flags:\n\t%s\n'
            'CMake library flags:\n\t%s\n'
            'CMake include file:\n\t%s') % (
                ' '.join(compiler_flags), ' '.join(linker_flags),
                ' '.join(library_flags), '\n\t'.join(lines))
        if verbose:
            logger.info(log_msg)
        else:
            logger.debug(log_msg)
        if fname is None:
            return pretarget_lines + lines
        else:
            if os.path.isfile(fname):
                os.remove(fname)
            with open(fname, 'w') as fd:
                fd.write('\n'.join(lines))
            return pretarget_lines

    
class CMakeBuilder(LinkerBase):
    r"""CMake build tool."""
    toolname = 'cmake'
    languages = ['cmake']
    default_flags = []  # '--clean-first']
    output_key = None
    flag_options = OrderedDict([('builddir', {'key': '--build',
                                              'position': 0}),
                                ('target', '--target'),
                                ('configuration', '--config')])
    executable_ext = ''
    tool_suffix_format = ''

    @classmethod
    def call(cls, *args, **kwargs):
        r"""Print contents of CMakeCache.txt before raising error."""
        try:
            return super(CMakeBuilder, cls).call(*args, **kwargs)
        except BaseException:  # pragma: debug
            cache = 'CMakeCache.txt'
            if ((isinstance(kwargs.get('builddir', None), str)
                 and os.path.isdir(kwargs['builddir']))):
                cache = os.path.join(kwargs['builddir'], cache)
            if kwargs.get('working_dir', None):
                cache = os.path.join(kwargs['working_dir'], cache)
            if os.path.isfile(cache):
                with open(cache, 'r') as fd:
                    logger.info('CMakeCache.txt:\n%s' % fd.read())
            else:
                logger.error('Cache file does not exist: %s' % cache)
            raise

    @classmethod
    def extract_kwargs(cls, kwargs, **kwargs_ex):
        r"""Extract linker kwargs, leaving behind just compiler kwargs.

        Args:
            kwargs (dict): Keyword arguments passed to the compiler that should
                be sorted into kwargs used by either the compiler or linker or
                both. Keywords that are not used by the compiler will be removed
                from this dictionary.
            **kwargs_ex: Additional keyword arguments are passed to the parent
                class's method.

        Returns:
            dict: Keyword arguments that should be passed to the linker.

        """
        kwargs_ex['add_kws_both'] = (kwargs.get('add_kws_both', [])
                                     + ['builddir', 'target'])
        return super(CMakeBuilder, cls).extract_kwargs(kwargs, **kwargs_ex)

    @classmethod
    def get_output_file(cls, obj, target=None, builddir=None, **kwargs):
        r"""Determine the appropriate output file that will result when bulding
        a given directory.

        Args:
            obj (str): Directory being built or a file in the directory being
                built.
            target (str, optional): Target that will be used to create the
                output file. Defaults to None. Target is required in order
                to determine the name of the file that will be created.
            builddir (str, optional): Directory where build tree should be
                created. Defaults to None and obj will used (if its a directory)
                or the directory containing obj will be used (if its a file).
            **kwargs: Additional keyword arguments are passed to the parent
                class's method.

        Returns:
            str: Full path to file that will be produced.

        Raises:
            RuntimeError: If target is None.

        """
        if builddir is None:
            if os.path.isfile(obj) or os.path.splitext(obj)[-1]:
                builddir = os.path.dirname(obj)
            else:
                builddir = obj
        if target is None:
            if os.path.isfile(obj) or os.path.splitext(obj)[-1]:
                target = os.path.splitext(os.path.basename(obj))[0]
            else:
                raise RuntimeError("Target is required.")
        elif target == 'clean':
            return target
        out = super(CMakeBuilder, cls).get_output_file(
            os.path.join(builddir, target), **kwargs)
        return out

    @classmethod
    def get_flags(cls, target=None, builddir=None, **kwargs):
        r"""Get a list of build flags for building a project using cmake.

        Args:
            target (str, optional): Target that should be built. Defaults to
                to None and is ignored.
            builddir (str, optional): Directory containing the build tree.
                Defaults to None and is set based on outfile is provided or
                cls.default_builddir if not.
                Defaults to '.' (which will be the current working directory).
            **kwargs: Additional keyword arguments are ignored.

        Returns:
            list: Linker flags.

        """
        outfile = kwargs.get('outfile', None)
        if outfile is not None:
            if target is None:
                target = os.path.splitext(os.path.basename(outfile))[0]
            if builddir is None:
                builddir = os.path.dirname(outfile)
        if builddir is None:
            builddir = CMakeConfigure.default_builddir
        out = super(CMakeBuilder, cls).get_flags(target=target,
                                                 builddir=builddir, **kwargs)
        return out

    @classmethod
    def get_executable_command(cls, args, **kwargs):
        r"""Determine the command required to run the tool using the specified
        arguments and options.

        Args:
            args (list): The arguments that should be passed to the tool. If
                skip_flags is False, these are treated as input files that will
                be used by the tool.
            **kwargs: Additional keyword arguments are passed to the parent
                class's method.

        Returns:
            str: Output to stdout from the command execution.

        """
        assert(len(args) == 1)
        if not kwargs.get('skip_flags', False):
            builddir = kwargs.get('builddir', args[0])
            if not os.path.isabs(builddir) and os.path.isabs(args[0]):
                builddir = os.path.join(os.path.dirname(args[0]), builddir)
            if builddir != args[0]:  # pragma: debug
                raise RuntimeError(("The argument list "
                                    "contents (='%s') and 'builddir' (='%s') "
                                    "keyword specify the same thing, but those "
                                    "provided do not match.")
                                   % (args[0], builddir))
            kwargs['builddir'] = args[0]
        return super(CMakeBuilder, cls).get_executable_command([], **kwargs)
    

class CMakeModelDriver(BuildModelDriver):
    r"""Class for running cmake compiled drivers. Before running the
    cmake command, the cmake commands for setting the necessary compiler & linker
    flags for the interface's C/C++ library are written to a file called
    'ygg_cmake.txt' that should be included in the CMakeLists.txt file (after
    the target executable has been added).

    Args:
        name (str): Driver name.
        args (str, list): Executable that should be created (cmake target) and
            any arguments for the executable.
        sourcedir (str, optional): Source directory to call cmake on. If not
            provided it is set to working_dir. This should be the directory
            containing the CMakeLists.txt file. It can be relative to
            working_dir or absolute.
        builddir (str, optional): Directory where the build should be saved.
            Defaults to <sourcedir>/build. It can be relative to working_dir
            or absolute.
        configuration (str, optional): Build type/configuration that should be
            built. Defaults to 'Release'.
        **kwargs: Additional keyword arguments are passed to parent class.

    Attributes:
        sourcedir (str): Source directory to call cmake on.
        add_libraries (bool): If True, interface libraries and dependency
            libraries are added using CMake's ADD_LIBRARY directive. If False,
            interface libraries are found using FIND_LIBRARY.
        configuration (str): Build type/configuration that should be built.
            This is only used on Windows.

    Raises:
        RuntimeError: If neither the IPC or ZMQ C libraries are available.

    """

    _schema_subtype_description = ('Model is written in C/C++ and has a '
                                   'CMake build system.')
    _schema_properties = {'sourcedir': {'type': 'string'},
                          'configuration': {'type': 'string',
                                            'default': 'Release'}}
    language = 'cmake'
    add_libraries = CMakeConfigure.add_libraries
    sourcedir_as_sourcefile = True
    use_env_vars = False
    buildfile_base = 'CMakeLists.txt'

    def parse_arguments(self, args, **kwargs):
        r"""Sort arguments based on their syntax to determine if an argument
        is a source file, compilation flag, or runtime option/flag that should
        be passed to the model executable.

        Args:
            args (list): List of arguments provided.
            **kwargs: Additional keyword arguments are passed to the parent
                class's method.

        """
        if self.target is None:
            self.builddir_base = 'build'
        else:
            self.builddir_base = 'build_%s' % self.target
        super(CMakeModelDriver, self).parse_arguments(args, **kwargs)
        self.buildfile_lock = get_buildfile_lock(self.buildfile, self.context)
        if self._mpi_rank > 0:
            self.send_mpi(self.buildfile, tag=self._mpi_tags['CMAKE_FILE'])

    @property
    def buildfile_orig(self):
        r"""str: Full path to where the original CMakeLists.txt file will
        be stored during compilation of the modified file."""
        return '_orig'.join(os.path.splitext(self.buildfile))

    @property
    def buildfile_ygg(self):
        r"""str: Full path to the verison of the CMakeLists.txt that has been
        updated w/ yggdrasil compilation flags."""
        return ('_ygg_%s' % self.name).join(os.path.splitext(self.buildfile))
    
    def write_wrappers(self, **kwargs):
        r"""Write any wrappers needed to compile and/or run a model.

        Args:
            **kwargs: Keyword arguments are passed to the parent class's method.

        Returns:
            list: Full paths to any created wrappers.

        """
        out = super(CMakeModelDriver, self).write_wrappers(**kwargs)
        # Create cmake files that can be included
        if self.target is None:
            include_base = 'ygg_cmake.txt'
        else:
            include_base = 'ygg_cmake_%s.txt' % self.target
        include_file = os.path.join(self.sourcedir, include_base)
        out.append(include_file)
        out.append(self.buildfile_ygg)
        if os.path.isfile(self.buildfile_ygg) and (not self.overwrite):
            return out
        kws = dict(compiler=self.target_language_info['compiler'],
                   linker=self.target_language_info['linker'],
                   configuration=self.configuration,
                   verbose=kwargs.get('verbose', False))
        if not self.use_env_vars:
            kws.update(
                compiler_flags=self.target_language_info['compiler_flags'],
                linker_flags=self.target_language_info['linker_flags'],
                library_flags=self.target_language_info['library_flags'],
                internal_library_flags=(
                    self.target_language_info['internal_library_flags']))
        newlines_before = self.get_tool_instance('compiler').create_include(
            include_file, self.target, **kws)
        assert(os.path.isfile(include_file))
        # Create copy of cmakelists and modify
        newlines_after = []
        if os.path.isfile(self.buildfile):
            with open(self.buildfile, 'r') as fd:
                contents = fd.read().splitlines()
            # Prevent error when cross compiling by building static lib as test
            newlines_before.append(
                'set(CMAKE_TRY_COMPILE_TARGET_TYPE "STATIC_LIBRARY")')
            # Add env prefix as first line so that env installed C libraries are
            # used
            for iprefix in self.get_tool_instance('compiler').get_env_prefixes():
                if platform._is_win:  # pragma: windows
                    env_lib = os.path.join(iprefix, 'libs').replace('\\', '\\\\')
                else:
                    env_lib = os.path.join(iprefix, 'lib')
                newlines_before.append('LINK_DIRECTORIES(%s)' % env_lib)
            # Explicitly set Release/Debug directories to builddir on windows
            if platform._is_win:  # pragma: windows
                for artifact in ['runtime', 'library', 'archive']:
                    for conf in ['release', 'debug']:
                        newlines_before.append(
                            'SET( CMAKE_%s_OUTPUT_DIRECTORY_%s '
                            % (artifact.upper(), conf.upper())
                            + '"${OUTPUT_DIRECTORY}")')
            # Add yggdrasil created include if not already in the file
            newlines_after.append(
                'INCLUDE(%s)' % os.path.basename(include_file))
            # Consolidate lines, checking for lines that already exist
            lines = []
            for newline in newlines_before:
                if newline not in contents:
                    lines.append(newline)
            lines += contents
            for newline in newlines_after:
                if newline not in contents:
                    lines.append(newline)
            # Write contents to the build file, check for new lines that may
            # already be included
            log_msg = 'New CMakeLists.txt:\n\t' + '\n\t'.join(lines)
            if kwargs.get('verbose', False):
                logger.info(log_msg)
            else:
                logger.debug(log_msg)
            with open(self.buildfile_ygg, 'w') as fd:
                fd.write('\n'.join(lines))
        return out

    @classmethod
    def get_language_for_buildfile(cls, buildfile, target=None):
        r"""Determine the target language based on the contents of a build
        file.

        Args:
            buildfile (str): Full path to the build configuration file.
            target (str, optional): Target that will be built. Defaults to None
                and the default target in the build file will be used.

        """
        with open(buildfile, 'r') as fd:
            lines = fd.readlines()
        for x in lines:
            if not x.strip().upper().startswith('ADD_EXECUTABLE'):
                continue
            varlist = x.split('(', 1)[-1].rsplit(')', 1)[0].split()
            if (target is None) or (target == varlist[0]):
                try:
                    return cls.get_language_for_source(
                        varlist[1:], early_exit=True, call_base=True)
                except ValueError:  # pragma: debug
                    pass
        return super(CMakeModelDriver, cls).get_language_for_buildfile(
            buildfile)  # pragma: debug

    @classmethod
    def fix_path(cls, path, for_env=False, **kwargs):
        r"""Update a path.

        Args:
            path (str): Path that should be formatted.
            for_env (bool, optional): If True, the path is formatted for use in
                and environment variable. Defaults to False.
            **kwargs: Additional keyword arguments are passed to the parent
                class's method.

        Returns:
            str: Updated path.

        """
        out = super(CMakeModelDriver, cls).fix_path(path, for_env=for_env,
                                                    **kwargs)
        if platform._is_win and for_env:
            out = ''
        return out

    @classmethod
    def get_target_language_info(cls, target_compiler_flags=None,
                                 target_linker_flags=None,
                                 compiler_flag_kwargs=None,
                                 linker_flag_kwargs=None,
                                 without_wrapper=False, **kwargs):
        r"""Get a dictionary of information about language compilation tools.

        Args:
            target_compiler_flags (list, optional): Compilation flags that
                should be passed to the target language compiler. Defaults
                to [].
            target_linker_flags (list, optional): Linking flags that should
                be passed to the target language linker. Defaults to [].
            compiler_flag_kwargs (dict, optional): Keyword arguments to pass
                to the get_compiler_flags method. Defaults to None.
            linker_flag_kwargs (dict, optional): Keyword arguments to pass
                to the get_linker_flags method. Defaults to None.
            **kwargs: Keyword arguments are passed to the parent class's
                method.
        
        Returns:
            dict: Information about language compilers and linkers.

        """
        if target_compiler_flags is None:
            target_compiler_flags = []
        if target_linker_flags is None:
            target_linker_flags = []
        if compiler_flag_kwargs is None:
            compiler_flag_kwargs = {}
        if linker_flag_kwargs is None:
            linker_flag_kwargs = {}
        if not (cls.use_env_vars or without_wrapper):
            compiler_flag_kwargs.setdefault('dont_skip_env_defaults', False)
            compiler_flag_kwargs.setdefault('skip_sysroot', True)
            compiler_flag_kwargs.setdefault('use_library_path', True)
            linker_flag_kwargs.setdefault('dont_skip_env_defaults', False)
            linker_flag_kwargs.setdefault('skip_library_libs', True)
            linker_flag_kwargs.setdefault('library_flags', [])
            linker_flag_kwargs.setdefault('use_library_path',
                                          'external_library_flags')
            linker_flag_kwargs.setdefault(
                linker_flag_kwargs['use_library_path'], [])
            external_library_flags = linker_flag_kwargs[
                linker_flag_kwargs['use_library_path']]
            linker_flag_kwargs.setdefault('use_library_path_internal',
                                          'internal_library_flags')
            linker_flag_kwargs.setdefault(
                linker_flag_kwargs['use_library_path_internal'], [])
            internal_library_flags = linker_flag_kwargs[
                linker_flag_kwargs['use_library_path_internal']]
        # Add python flags
        python_flags = sysconfig.get_config_var('LIBS')
        if python_flags:
            for x in python_flags.split():
                if x.startswith(('-L', '-l')) and (x not in target_linker_flags):
                    target_linker_flags.append(x)
        # Link local lib on MacOS because on Mac >=10.14 setting sysroot
        # clobbers the default paths.
        # https://stackoverflow.com/questions/54068035/linking-not-working-in
        # -homebrews-cmake-since-mojave
        if platform._is_mac:
            target_linker_flags += ['-L/usr/lib', '-L/usr/local/lib']
        out = super(CMakeModelDriver, cls).get_target_language_info(
            target_compiler_flags=target_compiler_flags,
            target_linker_flags=target_linker_flags,
            compiler_flag_kwargs=compiler_flag_kwargs,
            linker_flag_kwargs=linker_flag_kwargs,
            without_wrapper=without_wrapper, **kwargs)
        if not (cls.use_env_vars or without_wrapper):
            out.update(
                library_flags=(linker_flag_kwargs['library_flags']
                               + external_library_flags
                               + internal_library_flags),
                external_library_flags=external_library_flags,
                internal_library_flags=internal_library_flags)
        for k in constants.LANGUAGES['compiled']:
            if k == out['driver'].language:
                continue
            try:
                itool = get_compatible_tool(out['compiler'], 'compiler', k)
            except ValueError:
                continue
            if not itool.is_installed():
                continue
            if itool.default_executable_env:
                out['env'][itool.default_executable_env] = (
                    itool.get_executable(full_path=True))
                if platform._is_win:  # pragma: windows
                    out['env'][itool.default_executable_env] = cls.fix_path(
                        out['env'][itool.default_executable_env], for_env=True)
            if itool.default_flags_env:
                # TODO: Getting the flags is slower, but may be necessary
                # for projects that include more than one language. In
                # such cases it may be necessary to allow multiple values
                # for target_language or to add flags for all compiled
                # languages.
                drv_kws = copy.deepcopy(compiler_flag_kwargs)
                drv_kws['toolname'] = itool.toolname
                drv = import_component('model', k)
                out['env'][itool.default_flags_env] = ' '.join(
                    drv.get_compiler_flags(**drv_kws))
        return out
        
    def compile_model(self, target=None, **kwargs):
        r"""Compile model executable(s) and appends any products produced by
        the compilation that should be removed after the run is complete.

        Args:
            target (str, optional): Target to build.
            **kwargs: Keyword arguments are passed on to the call_compiler
                method.

        """
        if target is None:
            target = self.target
        if target == 'clean':
            return self.call_linker(self.builddir, target=target, out=target,
                                    overwrite=True, working_dir=self.working_dir,
                                    allow_error=True, **kwargs)
        if not kwargs.get('dry_run', False):
            self.buildfile_lock.acquire()
        out = None
        try:
            default_kwargs = dict(target=target,
                                  sourcedir=self.sourcedir,
                                  builddir=self.builddir,
                                  skip_interface_flags=True)
            default_kwargs['configuration'] = self.configuration
            for k, v in default_kwargs.items():
                kwargs.setdefault(k, v)
            if (not kwargs.get('dry_run', False)) and os.path.isfile(self.buildfile):
                if not os.path.isfile(self.buildfile_orig):
                    shutil.copy2(self.buildfile, self.buildfile_orig)
                    self.modified_files.append((self.buildfile_orig,
                                                self.buildfile))
                shutil.copy2(self.buildfile_ygg, self.buildfile)
            out = super(CMakeModelDriver, self).compile_model(**kwargs)
        finally:
            if not kwargs.get('dry_run', False):
                if self._mpi_rank > 0:
                    self.send_mpi('CMAKE_FINISHED_COMPILE',
                                  tag=self._mpi_tags['CMAKE_COMPILED'])
                self.buildfile_lock.release()
        return out

    @classmethod
    def prune_sh_gcc(cls, path, gcc):  # pragma: appveyor
        r"""Remove instances of sh.exe from the path that are not
        associated with the selected gcc compiler. This can happen
        on windows when rtools or git install a version of sh.exe
        that is added to the path before the compiler.

        Args:
            path (str): Contents of the path variable.
            gcc (str): Full path to the gcc executable.

        Returns:
            str: Modified path that removes the extra instances
                of sh.exe.

        """
        # This method is not covered because it is not called on
        # github actions where bash is always present
        sh_path = shutil.which('sh', path=path)
        while sh_path:
            for k in ['rtools', 'git']:
                if k in sh_path.lower():
                    break
            else:  # pragma: debug
                break
            if k not in gcc.lower():
                paths = path.split(os.pathsep)
                paths.remove(os.path.dirname(sh_path))
                path = os.pathsep.join(paths)
                sh_path = shutil.which('sh', path=path)
            else:  # pragma: debug
                break
        return path

    @classmethod
    def update_compiler_kwargs(cls, **kwargs):
        r"""Update keyword arguments supplied to the compiler get_flags method
        for various options.

        Args:
            **kwargs: Additional keyword arguments are passed to the parent
                class's method.

        Returns:
            dict: Keyword arguments for a get_flags method providing compiler
                flags.

        """
        if platform._is_win and (kwargs.get('target_compiler', None)
                                 in ['gcc', 'g++', 'gfortran']):  # pragma: windows
            gcc = get_compilation_tool('compiler',
                                       kwargs['target_compiler'],
                                       None)
            if gcc:
                path = cls.prune_sh_gcc(
                    kwargs['env']['PATH'],
                    gcc.get_executable(full_path=True))
                kwargs['env']['PATH'] = path
                if not shutil.which('sh', path=path):  # pragma: appveyor
                    # This will not be run on Github actions where
                    # the shell is always set
                    kwargs.setdefault('generator', 'MinGW Makefiles')
                elif shutil.which('make', path=path):
                    kwargs.setdefault('generator', 'Unix Makefiles')
                # This is not currently tested
                # else:
                #     kwargs.setdefault('generator', 'MSYS Makefiles')
        out = super(CMakeModelDriver, cls).update_compiler_kwargs(**kwargs)
        out.setdefault('definitions', [])
        out['definitions'].append('PYTHON_EXECUTABLE=%s' % sys.executable)
        return out
