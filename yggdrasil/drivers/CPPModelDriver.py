import os
import copy
from yggdrasil import platform
from yggdrasil.drivers.CModelDriver import (
    CCompilerBase, CModelDriver, GCCCompiler, ClangCompiler, MSVCCompiler,
    ClangLinker)


class CPPCompilerBase(CCompilerBase):
    r"""Base class for C++ compilers."""
    languages = ['c++']
    default_executable_env = 'CXX'
    default_flags_env = 'CXXFLAGS'
    cpp_std = 'c++14'
    search_path_flags = ['-E', '-v', '-xc++', '/dev/null']
    default_linker = None
    default_executable = None

    @classmethod
    def add_standard_flag(cls, flags):
        r"""Add a standard flag to the list of flags.

        Args:
            flags (list): Compilation flags.

        """
        std_flag = None
        for i, a in enumerate(flags):
            if a.startswith('-std='):
                std_flag = i
                break
        if std_flag is None:
            flags.append('-std=%s' % cls.cpp_std)
        return flags


class GPPCompiler(CPPCompilerBase, GCCCompiler):
    r"""Interface class for G++ compiler/linker."""
    toolname = 'g++'
    aliases = ['gnu-c++']

    @classmethod
    def get_flags(cls, skip_standard_flag=False, **kwargs):
        r"""Get a list of compiler flags.

        Args:
            skip_standard_flag (bool, optional): If True, the C++ standard flag
                will not be added. Defaults to False.
            **kwargs: Additional keyword arguments are passed to the parent
                class's method.

        Returns:
            list: Compiler flags.

        """
        out = super(GPPCompiler, cls).get_flags(**kwargs)
        # Add standard library flag
        if not skip_standard_flag:
            out = cls.add_standard_flag(out)
        return out


class ClangPPCompiler(CPPCompilerBase, ClangCompiler):
    r"""Interface class for clang++ compiler."""
    toolname = 'clang++'
    default_linker = 'clang++'
    # Set to False since ClangLinker has its own class to handle
    # conflict between versions of clang and ld.
    is_linker = False

    @staticmethod
    def before_registration(cls):
        r"""Operations that should be performed to modify class attributes prior
        to registration including things like platform dependent properties and
        checking environment variables for default settings.
        """
        if platform._is_win:  # pragma: windows
            cls.default_executable = 'clang'
        CPPCompilerBase.before_registration(cls)

    @classmethod
    def get_flags(cls, skip_standard_flag=False, **kwargs):
        r"""Get a list of compiler flags.

        Args:
            skip_standard_flag (bool, optional): If True, the C++ standard flag
                will not be added. Defaults to False.
            **kwargs: Additional keyword arguments are passed to the parent
                class's method.

        Returns:
            list: Compiler flags.

        """
        out = super(ClangPPCompiler, cls).get_flags(**kwargs)
        # Add standard library flag
        if not skip_standard_flag:
            out = cls.add_standard_flag(out)
        return out
        
    @classmethod
    def get_executable_command(cls, args, skip_flags=False, unused_kwargs=None,
                               **kwargs):
        r"""Determine the command required to run the tool using the specified
        arguments and options.

        Args:
            args (list): The arguments that should be passed to the tool. If
                skip_flags is False, these are treated as input files that will
                be used by the tool.
            **kwargs: Additional keyword arguments will be passed to the parent
                class's method.

        Returns:
            str: Output to stdout from the command execution.

        """
        if platform._is_win:  # pragma: windows
            for a in args:
                if a.endswith('.c'):
                    kwargs['skip_standard_flag'] = True
                    break
        return super(ClangPPCompiler, cls).get_executable_command(args, **kwargs)


class MSVCPPCompiler(CPPCompilerBase, MSVCCompiler):
    r"""Inteface class for MSVC compiler when compiling C++."""
    toolname = 'cl++'
    default_linker = MSVCCompiler.default_linker
    default_archiver = MSVCCompiler.default_archiver
    default_executable = MSVCCompiler.default_executable
    search_path_flags = None
    dont_create_linker = True
    
    @staticmethod
    def before_registration(cls):
        r"""Operations that should be performed to modify class attributes prior
        to registration including things like platform dependent properties and
        checking environment variables for default settings.
        """
        return MSVCCompiler.before_registration(cls)


class ClangPPLinker(ClangLinker):
    r"""Interface class for clang++ linker (calls to ld)."""
    toolname = ClangPPCompiler.toolname
    languages = ClangPPCompiler.languages
    default_executable = ClangPPCompiler.default_executable
    toolset = ClangPPCompiler.toolset


class CPPModelDriver(CModelDriver):
    r"""Class for running C++ models."""
                
    _schema_subtype_description = ('Model is written in C++.')
    language = 'c++'
    language_ext = ['.cpp', '.CPP', '.cxx', '.C', '.c++', '.cc', '.cp', '.tcc',
                    '.hpp', '.HPP', '.hxx', '.H', '.h++', '.hh', '.hp', '.h']
    language_aliases = ['cpp', 'cxx']
    base_languages = ['c']
    interface_library = 'ygg++'
    # To prevent inheritance
    default_compiler = None
    default_linker = None
    function_param = dict(
        CModelDriver.function_param,
        input='YggInput {channel}(\"{channel_name}\", {channel_type});',
        output='YggOutput {channel}(\"{channel_name}\", {channel_type});',
        recv_heap='{channel}.recvRealloc',
        recv_stack='{channel}.recv',
        recv_function='{channel}.recvRealloc',
        send_function='{channel}.send',
        exec_prefix=('#include <iostream>\n'
                     '#include <exception>\n'),
        print_generic='std::cout << {object} << std::endl << std::flush;',
        error='throw \"{error_msg}\";',
        try_begin='try {',
        try_error_type='const std::exception&',
        try_except='}} catch ({error_type} {error_var}) {{',
        function_def_regex=(
            r'(?P<flag_type>.+?)\s*{function_name}\s*'
            r'\((?P<inputs>(?:[^{{\&])*?)'
            r'(?:,\s*(?P<outputs>'
            r'(?:\s*(?:[^\s\&]+)'
            r'(?:(?:\&\s+)|(?:\s+(?:\()?\&))'
            r'(?:[^{{])+)+))?\)\s*\{{'
            r'(?P<body>(?:.*?\n?)*?)'
            r'(?:(?:return +(?P<flag_var>.+?)?;(?:.*?\n?)*?\}})'
            r'|(?:\}}))'),
        outputs_def_regex=(
            r'\s*(?P<native_type>(?:[^\s])+)(\s+)?'
            r'(\()?(?P<ref>\&)(?(1)(?:\s*)|(?:\s+))'
            r'(?P<name>.+?)(?(2)(?:\)|(?:)))(?P<shape>(?:\[.+?\])+)?\s*(?:,|$)(?:\n)?'))
    include_arg_count = True
    include_channel_obj = False
    dont_declare_channel = True
    
    @staticmethod
    def after_registration(cls, **kwargs):
        r"""Operations that should be performed to modify class attributes after
        registration."""
        if cls.default_compiler is None:
            if platform._is_linux:
                cls.default_compiler = 'g++'
            elif platform._is_mac:
                cls.default_compiler = 'clang++'
            elif platform._is_win:  # pragma: windows
                cls.default_compiler = 'cl'
        cls.function_param['print'] = 'std::cout << "{message}" << std::endl;'
        CModelDriver.after_registration(cls, **kwargs)
        if kwargs.get('second_pass', False):
            return
        internal_libs = copy.deepcopy(cls.internal_libraries)
        internal_libs[cls.interface_library] = internal_libs.pop(
            CModelDriver.interface_library)
        internal_libs[cls.interface_library]['source'] = os.path.join(
            cls.get_language_dir(),
            os.path.splitext(os.path.basename(
                internal_libs[cls.interface_library]['source']))[0]
            + cls.language_ext[0])
        internal_libs[cls.interface_library]['include_dirs'].append(
            cls.get_language_dir())
        internal_libs[cls.interface_library]['language'] = cls.language
        cls.internal_libraries = internal_libs

    @classmethod
    def set_env_class(cls, **kwargs):
        r"""Set environment variables that are instance independent.

        Args:
            **kwargs: Additional keyword arguments are passed to the parent
                class's method and update_ld_library_path.

        Returns:
            dict: Environment variables for the model process.

        """
        out = super(CPPModelDriver, cls).set_env_class(**kwargs)
        out = CModelDriver.update_ld_library_path(out, **kwargs)
        return out
        
    @classmethod
    def write_try_except(cls, try_contents, except_contents, error_var='e',
                         error_type=None, **kwargs):
        r"""Return the lines required to complete a try/except block.

        Args:
            try_contents (list): Lines of code that should be executed inside
                the try block.
            except_contents (list): Lines of code that should be executed inside
                the except block.
            error_var (str, optional): Name of variable where the caught error
                should be stored. Defaults to 'e'. If '...', the catch clause
                will catch all errors, but there will not be a name error.
            error_type (str, optional): Name of error type that should be caught.
                If not provided, defaults to None and will be set based on the
                class function_param entry for 'try_error_type'. If '...', the
                catch clause will catch all errors and error_var will be
                ignored.
            **kwargs: Additional keyword arguments are passed to the parent
                class's method.

        Returns:
            Lines of code perfoming a try/except block.

        """
        if (error_type == '...') or (error_var == '...'):
            error_type = ''
            error_var = '...'
        kwargs.update(error_var=error_var, error_type=error_type)
        return super(CPPModelDriver, cls).write_try_except(
            try_contents, except_contents, **kwargs)

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
        out = super(CModelDriver, cls).output2input(var)
        if isinstance(var, dict):
            if in_definition:
                out = dict(out, name='&' + out['name'])
                if ((('shape' in out.get('datatype', {}))
                     or ('length' in out.get('datatype', {})))):
                    out['name'] = '(%s)' % out['name']
            else:
                if not (out.get('ref', False)
                        or out.get('is_length_var', False)):
                    out = dict(out, name='&' + out['name'])
        return out
