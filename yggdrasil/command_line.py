#!/usr/bin/python
import os
import sys
import copy
import logging
import subprocess
import argparse
import pprint
import shutil
from yggdrasil.constants import LANGUAGES, LANGUAGES_WITH_ALIASES


logger = logging.getLogger(__name__)
package_dir = os.path.dirname(os.path.abspath(__file__))


def githook():
    r"""Git hook to determine if the Github workflow need to be
    re-generated."""
    try:
        files = subprocess.check_output(
            ["git", "diff-index", "--cached", "--name-only",
             "--diff-filter=ACMRTUXB", "HEAD"],
            stderr=subprocess.PIPE).decode('utf-8').splitlines()
    except subprocess.CalledProcessError:
        return 1
    regen = (os.path.join('utils', 'test-install-base.yml') in files)
    if regen:
        try:
            gitdir = subprocess.check_output(
                ["git", "rev-parse", "--git-dir"],
                stderr=subprocess.PIPE).decode('utf-8').strip()
        except subprocess.CalledProcessError:
            return 1
        workflow_dir = os.path.join(gitdir, '..', '.github', 'workflows')
        generate_gha_workflow(args=[], gitdir=gitdir)
        try:
            subprocess.run(
                ['git', 'add',
                 os.path.join(workflow_dir, 'test-install.yml')],
                check=True,
                stderr=subprocess.STDOUT,
                stdout=subprocess.PIPE)
        except subprocess.CalledProcessError:
            return 1
    return 0


class ArgumentTuple(tuple):

    def __new__(self, args, kwargs):
        return tuple.__new__(ArgumentTuple, (args, kwargs))


class ConditionalArgumentTuple(ArgumentTuple):

    def __new__(cls, args, kwargs, conditions=None):
        out = ArgumentTuple.__new__(ConditionalArgumentTuple,
                                    args, kwargs)
        out.conditions = conditions
        if out.conditions is None:
            out.conditions = {}
        return out
            

class ArgumentBase(object):
    
    def __init__(self, arguments=None, conditions=None, **kwargs):
        self.arguments = arguments
        if self.arguments is None:
            self.arguments = []
        self.conditions = conditions
        if self.conditions is None:
            self.conditions = {}
        self.kwargs = kwargs


class ArgumentParser(ArgumentBase):
    pass


class ArgumentGroup(ArgumentBase):

    def __init__(self, exclusive=False, **kwargs):
        self.exclusive = exclusive
        super(ArgumentGroup, self).__init__(**kwargs)


class ArgumentSubparser(ArgumentBase):

    def __init__(self, parsers=None, **kwargs):
        self.parsers = parsers
        if self.parsers is None:
            self.parsers = []
        super(ArgumentSubparser, self).__init__(**kwargs)


class SubCommandMeta(type):
    r"""Meta class for subcommands."""

    def __call__(cls, *args, **kwargs):
        return cls.call(*args, **kwargs)


def ReplacementWarning(old, new):
    import warnings
    warnings.warn(("'%s' will soon be removed. Use '%s' instead.")
                  % (old, new), FutureWarning)


class SubCommand(metaclass=SubCommandMeta):
    r"""Class for handling subcommands so that they can be run
    as subcommands or individually."""

    name = None
    help = None
    arguments = []
    allow_unknown = False

    @classmethod
    def parse_args(cls, parser, args=None, allow_unknown=False):
        # TODO: Check choices for positional arguments that can
        # have more than one element
        if isinstance(args, argparse.Namespace):
            return args
        if cls.allow_unknown or allow_unknown:
            args, extra = parser.parse_known_args(args=args)
            args._extra_commands = extra
        else:
            args = parser.parse_args(args=args)
        for k in ['language', 'languages']:
            v = getattr(args, k, None)
            if isinstance(v, list):
                v_flag = getattr(args, k + '_flag', None)
                if isinstance(v_flag, list):
                    v.extend(v_flag)
                if (len(v) == 0) or ('all' in v):
                    setattr(args, k, LANGUAGES['all'])
                    args.all_languages = True
        return args

    @classmethod
    def func(cls, args):  # pragma: debug
        raise NotImplementedError

    @classmethod
    def call(cls, args=None, **kwargs):
        parser = cls.get_parser(args=args)
        args = cls.parse_args(parser, args=args)
        return cls.func(args, **kwargs)

    @classmethod
    def get_parser(cls, args=None):
        parser = argparse.ArgumentParser(cls.help)
        cls.add_arguments(parser, args=args)
        return parser

    @classmethod
    def add_argument_to_parser(cls, parser, x):
        if hasattr(x, 'conditions') and x.conditions:
            for k, v in x.conditions.items():
                if k == 'os':
                    from yggdrasil import platform
                    if platform._platform not in v:
                        return
                else:  # pragma: debug
                    raise NotImplementedError(k)
        if isinstance(x, list):
            for xx in x:
                cls.add_argument_to_parser(parser, xx)
        elif isinstance(x, (tuple, ArgumentTuple,
                            ConditionalArgumentTuple)):
            assert(len(x) == 2)
            args, kwargs = x[:]
            try:
                parser.add_argument(*args, **kwargs)
            except ValueError:
                if kwargs.get('action', None) == 'extend':
                    kwargs['action'] = 'append'
                    kwargs.pop('nargs', None)
                    parser.add_argument(*args, **kwargs)
                else:
                    raise
        elif isinstance(x, ArgumentGroup):
            if x.exclusive:
                group = parser.add_mutually_exclusive_group(**x.kwargs)
            else:
                group = parser.add_argument_group(**x.kwargs)
            cls.add_argument_to_parser(group, x.arguments)
        elif isinstance(x, ArgumentSubparser):
            subparsers = parser.add_subparsers(**x.kwargs)
            for xx in x.parsers:
                isubparser = subparsers.add_parser(**xx.kwargs)
                cls.add_argument_to_parser(isubparser, x.arguments)
                cls.add_argument_to_parser(isubparser, xx.arguments)
        else:
            raise NotImplementedError("type(x) = %s" % type(x))

    @classmethod
    def add_arguments(cls, parser, args=None):
        cls.add_argument_to_parser(parser, cls.arguments)

    @classmethod
    def add_subparser(cls, subparsers, args=None):
        parser = subparsers.add_parser(cls.name, help=cls.help)
        cls.add_arguments(parser, args=args)
        parser.set_defaults(func=cls.func)


class main(SubCommand):
    r"""Runner for yggdrasil CLI."""

    name = "yggdrasil"
    help = (
        "Command line interface for the yggdrasil package.")
    arguments = []

    @classmethod
    def get_parser(cls, **kwargs):
        from yggdrasil import __version__ as ver
        parser = super(main, cls).get_parser(**kwargs)
        parser.add_argument('--version', action='version',
                            version=('yggdrasil %s' % ver))
        subparsers = parser.add_subparsers(title='subcommands',
                                           dest='subcommand')
        parser._ygg_subparsers = {}
        for x in [yggrun, ygginfo, validate_yaml,
                  yggcc, yggcompile, yggclean,
                  ygginstall, update_config,
                  regen_metaschema, regen_schema,
                  yggmodelform, yggdevup, run_tsts,
                  timing_plots, generate_gha_workflow]:
            x.add_subparser(subparsers, args=kwargs.get('args', None))
            parser._ygg_subparsers[x.name] = x
        return parser

    @classmethod
    def parse_args(cls, parser, args=None, **kwargs):
        if args is None:
            args = sys.argv[1:]
        if isinstance(args, list) and ('test' in args):
            kwargs['allow_unknown'] = True
        args = super(main, cls).parse_args(parser, args=args, **kwargs)
        if args.subcommand:
            args = parser._ygg_subparsers[args.subcommand].parse_args(
                parser, args=args, **kwargs)
        return args

    @classmethod
    def func(cls, args):
        args.func(args)


class yggrun(SubCommand):
    r"""Start a run."""

    name = "run"
    help = "Run an integration."
    arguments = [
        (('yamlfile', ),
         {'nargs': '+',
          'help': "One or more yaml specification files."}),
        (('--with-mpi', '--mpi-nproc'),
         {'type': int, 'default': 1,
          'help': 'Number of MPI processes to run on.'})]

    @classmethod
    def add_arguments(cls, parser, **kwargs):
        from yggdrasil import config
        super(yggrun, cls).add_arguments(parser, **kwargs)
        config.get_config_parser(parser, skip_sections='testing')

    @classmethod
    def func(cls, args):
        if args.with_mpi > 1:
            new_args = ['mpiexec', '-n', str(args.with_mpi)]
            i = 0
            while i < len(sys.argv):
                x = sys.argv[i]
                if x.startswith(('--with-mpi', '--mpi-nproc')):
                    if '=' not in x:
                        i += 1
                else:
                    new_args.append(x)
                i += 1
            return subprocess.check_call(new_args)
        from yggdrasil import runner, config
        prog = sys.argv[0].split(os.path.sep)[-1]
        with config.parser_config(args):
            runner.run(args.yamlfile, ygg_debug_prefix=prog,
                       production_run=args.production_run)


class ygginfo(SubCommand):
    r"""Print information about yggdrasil installation."""

    name = 'info'
    help = ('Display information about the current yggdrasil '
            'installation.')
    arguments = [
        (('--no-languages', ),
         {'action': 'store_true', 'dest': 'no_languages',
          'help': ('Don\'t print information about individual '
                   'languages.')}),
        (('--no-comms', ),
         {'action': 'store_true', 'dest': 'no_comms',
          'help': ('Don\'t print information about individual '
                   'comms.')}),
        (('--verbose', '-v'),
         {'action': 'store_true',
          'help': ('Increase the verbosity of the printed '
                   'information.')}),
        ArgumentSubparser(
            title='tool', dest='tool',
            description='Compilation tool types to get info about.',
            arguments=[
                (('language', ),
                 {'choices': LANGUAGES_WITH_ALIASES['compiled'],
                  'type': str.lower,
                  'help': 'Language to get tool information for.'}),
                (('--toolname', ),
                 {'default': None,
                  'help': ('Name of tool to get information for. '
                           'If not provided, information for the '
                           'default tool will be returned.')}),
                (('--flags', ),
                 {'action': 'store_true',
                  'help': ('Display the flags that yggdrasil will '
                           ' pass to the tool when it is called.')}),
                (('--fullpath', ),
                 {'action': 'store_true',
                  'help': 'Get the full path to the tool exectuable.'})],
            parsers=[
                ArgumentParser(
                    name='compiler',
                    help='Get information about a compiler.'),
                ArgumentParser(
                    name='linker',
                    help='Get information about a linker.',
                    arguments=[
                        (('--library', ),
                         {'action': 'store_true',
                          'help': 'Get flags for linking a library.'})]),
                ArgumentParser(
                    name='archiver',
                    help='Get information about a archiver.')])]

    @classmethod
    def func(cls, args, return_str=False):
        from yggdrasil import platform
        from yggdrasil.components import import_component
        if args.tool:
            drv = import_component('model', args.language)
            if args.flags:
                if args.tool == 'compiler':
                    flags = drv.get_compiler_flags(
                        for_model=True, toolname=args.toolname,
                        dry_run=True, dont_link=True)
                    if '/link' in flags:  # pragma: windows
                        flags = flags[:flags.index('/link')]
                    for k in ['-c']:
                        if k in flags:
                            flags.remove(k)
                else:
                    if args.tool == 'archiver':
                        libtype = 'static'
                    elif getattr(args, 'library', False):
                        libtype = 'shared'
                    else:
                        libtype = 'object'
                    flags = drv.get_linker_flags(
                        for_model=True, toolname=args.toolname,
                        dry_run=True, libtype=libtype)
                out = ' '.join(flags)
                if platform._is_win:  # pragma: windows:
                    out = out.replace('/', '-')
                    out = out.replace('\\', '/')
            elif args.fullpath:
                out = drv.get_tool(args.tool).get_executable(full_path=True)
            else:
                out = drv.get_tool(args.tool, return_prop='name')
            if return_str:
                return out
            print(out)
            return
        from yggdrasil import tools, config, __version__
        lang_list = tools.get_installed_lang()
        comm_list = tools.get_installed_comm()
        comm_lang_list = []
        prefix = '    '
        curr_prefix = ''
        vardict = [
            ('Location', os.path.dirname(__file__)),
            ('Version', __version__),
            ('Languages', ', '.join(lang_list)),
            ('Communication Mechanisms',
             ', '.join(tools.get_installed_comm())),
            ('Default Comm Mechanism', tools.get_default_comm()),
            ('Config File', config.usr_config_file)]
        try:
            # Add language information
            if not args.no_languages:
                # Install languages
                vardict.append(('Installed Languages:', ''))
                curr_prefix += prefix
                for lang in sorted(lang_list):
                    drv = import_component('model', lang)
                    vardict.append(
                        (curr_prefix + '%s:' % lang.upper(), ''))
                    if not drv.comms_implicit:
                        comm_lang_list.append(lang)
                    curr_prefix += prefix
                    exec_name = drv.language_executable()
                    if exec_name:
                        if not os.path.isabs(exec_name):
                            exec_name = shutil.which(exec_name)
                        vardict.append((curr_prefix + 'Location',
                                        exec_name))
                    vardict.append((curr_prefix + 'Version',
                                    drv.language_version()))
                    curr_prefix = curr_prefix.rsplit(prefix, 1)[0]
                curr_prefix = curr_prefix.rsplit(prefix, 1)[0]
                # Not installed languages
                vardict.append(("Languages Not Installed:", ''))
                curr_prefix += prefix
                for lang in tools.get_supported_lang():
                    if lang in lang_list:
                        continue
                    drv = import_component('model', lang)
                    vardict.append(
                        (curr_prefix + '%s:' % lang.upper(), ''))
                    curr_prefix += prefix
                    vardict.append(
                        (curr_prefix + "Language Installed",
                         drv.is_language_installed()))
                    if drv.executable_type == 'compiler':
                        curr_prefix += prefix
                        vardict += [
                            (curr_prefix
                             + ("%s Installed (%s)"
                                % (x.title(),
                                   getattr(drv, 'default_%s' % x, None))),
                             drv.is_tool_installed(x))
                            for x in ['compiler', 'linker', 'archiver']]
                        curr_prefix = curr_prefix.rsplit(prefix, 1)[0]
                    vardict.append(
                        (curr_prefix + "Base Languages Installed",
                         drv.are_base_languages_installed()))
                    missing = []
                    if not drv.are_base_languages_installed(
                            missing=missing):
                        vardict.append(
                            (curr_prefix
                             + "Base Languages Not Installed",
                             missing))
                    vardict.append(
                        (curr_prefix + "Dependencies Installed",
                         drv.are_dependencies_installed()))
                    if not drv.are_dependencies_installed():
                        vardict.append(
                            (curr_prefix
                             + "Dependencies Not Installed",
                             [b for b in drv.interface_dependencies if
                              (not drv.is_library_installed(b))]))
                    vardict.append(
                        (curr_prefix + "Interface Installed",
                         drv.is_interface_installed()))
                    vardict.append((curr_prefix + "Comm Installed",
                                    drv.is_comm_installed()))
                    vardict.append((curr_prefix + "Configured",
                                    drv.is_configured()))
                    vardict.append((curr_prefix + "Disabled",
                                    drv.is_disabled()))
                    curr_prefix = curr_prefix.rsplit(prefix, 1)[0]
                curr_prefix = curr_prefix.rsplit(prefix, 1)[0]
            # Add comm information
            if not args.no_comms:
                # Fully installed comms
                vardict.append(
                    ('Comms Available for All Languages:', ''))
                curr_prefix += prefix
                for comm in sorted(comm_list):
                    cmm = import_component('comm', comm)
                    vardict.append(
                        (curr_prefix + '%s' % comm.upper(), ''))
                curr_prefix = curr_prefix.rsplit(prefix, 1)[0]
                # Partially installed comms
                vardict.append(
                    ('Comms Available for Some/No Languages:', ''))
                curr_prefix += prefix
                for comm in tools.get_supported_comm():
                    if comm in comm_list:
                        continue
                    cmm = import_component('comm', comm)
                    vardict.append(
                        (curr_prefix + '%s:' % comm.upper(), ''))
                    curr_prefix += prefix
                    avail = [cmm.is_installed(language=lang)
                             for lang in comm_lang_list]
                    vardict.append(
                        (curr_prefix + "Available for ",
                         sorted([comm_lang_list[i].upper()
                                 for i in range(len(avail))
                                 if avail[i]])))
                    vardict.append(
                        (curr_prefix + "Not Available for ",
                         sorted([comm_lang_list[i].upper()
                                 for i in range(len(avail))
                                 if not avail[i]])))
                    curr_prefix = curr_prefix.rsplit(prefix, 1)[0]
                curr_prefix = curr_prefix.rsplit(prefix, 1)[0]
            # Add verbose information
            if args.verbose:
                # Path variables
                path_vars = ['PATH', 'C_INCLUDE_PATH', 'INCLUDE',
                             'LIBRARY_PATH', 'LD_LIBRARY_PATH', 'LIB']
                vardict.append(('Environment paths:', ''))
                curr_prefix += prefix
                for k in path_vars:
                    if os.environ.get(k, ''):
                        vardict.append(
                            (curr_prefix + k, '\n%s%s'
                             % (curr_prefix + prefix,
                                ("\n" + curr_prefix + prefix).join(
                                    os.environ[k].split(os.pathsep)))))
                    else:
                        vardict.append((curr_prefix + k, ''))
                curr_prefix = curr_prefix.rsplit(prefix, 1)[0]
                # Environment variabless
                env_vars = ['CONDA_PREFIX', 'CONDA', 'SDKROOT', 'CC',
                            'CXX', 'FC', 'GFORTRAN', 'DISPLAY', 'CL',
                            '_CL_']
                if platform._is_win:  # pragma: windows
                    env_vars += ['VCPKG_ROOT']
                vardict.append(('Environment variables:', ''))
                curr_prefix += prefix
                for k in env_vars:
                    vardict.append(
                        (curr_prefix + k, os.environ.get(k, None)))
                curr_prefix = curr_prefix.rsplit(prefix, 1)[0]
                # Conda info
                if os.environ.get('CONDA_PREFIX', ''):
                    if platform._is_win:  # pragma: windows
                        out = tools.bytes2str(subprocess.check_output(
                            'conda info', shell=True)).strip()
                    else:
                        out = tools.bytes2str(subprocess.check_output(
                            ['conda', 'info'])).strip()
                    curr_prefix += prefix
                    vardict.append(
                        (curr_prefix + 'Conda Info:', "\n%s%s"
                         % (curr_prefix + prefix,
                            ("\n" + curr_prefix + prefix).join(
                                out.splitlines(False)))))
                    curr_prefix = curr_prefix.rsplit(prefix, 1)[0]
                # Configuration
                with open(config.usr_config_file, 'r') as fd:
                    contents = fd.read()
                vardict.append(
                    ('Configuration file:', '%s\n\t%s' % (
                        config.usr_config_file,
                        '\n\t'.join(contents.splitlines()))))
                # R and reticulate info
                Rdrv = import_component("model", "R")
                if Rdrv.is_installed():
                    env_reticulate = copy.deepcopy(os.environ)
                    env_reticulate['RETICULATE_PYTHON'] = sys.executable
                    # Stack size
                    out = Rdrv.run_executable(
                        ["-e", "Cstack_info()"]).strip()
                    vardict.append(
                        (curr_prefix + "R Cstack_info:", "\n%s%s"
                         % (curr_prefix + prefix,
                            ("\n" + curr_prefix + prefix).join(
                                out.splitlines(False)))))
                    # Compilation tools
                    interp = 'R'.join(
                        Rdrv.get_interpreter().rsplit('Rscript', 1))
                    vardict.append(
                        (curr_prefix + "R C Compiler:", ""))
                    curr_prefix += prefix
                    for x in ['CC', 'CFLAGS', 'CXX', 'CXXFLAGS']:
                        try:
                            out = tools.bytes2str(
                                subprocess.check_output(
                                    [interp, 'CMD', 'config', x],
                                    stderr=subprocess.STDOUT)).strip()
                        except subprocess.CalledProcessError:
                            out = 'ERROR (missing Rtools?)'
                        vardict.append(
                            (curr_prefix + x, "%s"
                             % ("\n" + curr_prefix + prefix).join(
                                 out.splitlines(False))))
                    curr_prefix = curr_prefix.rsplit(prefix, 1)[0]
                    # Session info
                    out = Rdrv.run_executable(
                        ["-e", "sessionInfo()"]).strip()
                    vardict.append(
                        (curr_prefix + "R sessionInfo:", "\n%s%s"
                         % (curr_prefix + prefix,
                            ("\n" + curr_prefix + prefix).join(
                                out.splitlines(False)))))
                    # Reticulate conda_list
                    if os.environ.get('CONDA_PREFIX', ''):
                        if platform._is_win:  # pragma: windows
                            out = tools.bytes2str(subprocess.check_output(
                                'conda info --json', shell=True)).strip()
                        else:
                            out = tools.bytes2str(subprocess.check_output(
                                ['conda', 'info', '--json'])).strip()
                        vardict.append(
                            (curr_prefix
                             + "conda info --json",
                             "\n%s%s" % (
                                 curr_prefix + prefix,
                                 ("\n" + curr_prefix + prefix).join(
                                     out.splitlines(False)))))
                        try:
                            out = Rdrv.run_executable(
                                ["-e", ("library(reticulate); "
                                        "reticulate::conda_list()")],
                                env=env_reticulate).strip()
                        except BaseException:  # pragma: debug
                            out = 'ERROR'
                        vardict.append(
                            (curr_prefix
                             + "R reticulate::conda_list():",
                             "\n%s%s" % (
                                 curr_prefix + prefix,
                                 ("\n" + curr_prefix + prefix).join(
                                     out.splitlines(False)))))
                    # Windows python versions
                    if platform._is_win:  # pragma: windows
                        out = Rdrv.run_executable(
                            ["-e",
                             ("library(reticulate); "
                              "reticulate::py_versions_windows()")],
                            env=env_reticulate).strip()
                        vardict.append(
                            (curr_prefix
                             + "R reticulate::py_versions_windows():",
                             "\n%s%s" % (
                                 curr_prefix + prefix,
                                 ("\n" + curr_prefix + prefix).join(
                                     out.splitlines(False)))))
                    # conda_binary
                    if platform._is_win and shutil.which('conda'):  # pragma: windows
                        out = Rdrv.run_executable(
                            ["-e",
                             ("library(reticulate); "
                              "conda <- reticulate:::conda_binary(\"auto\"); "
                              "system(paste(conda, \"info --json\"))")],
                            env=env_reticulate).strip()
                        vardict.append(
                            (curr_prefix
                             + "R reticulate::py_versions_windows():",
                             "\n%s%s" % (
                                 curr_prefix + prefix,
                                 ("\n" + curr_prefix + prefix).join(
                                     out.splitlines(False)))))
                    # Reticulate py_config
                    out = Rdrv.run_executable(
                        ["-e", ("library(reticulate); "
                                "reticulate::py_config()")],
                        env=env_reticulate).strip()
                    vardict.append(
                        (curr_prefix + "R reticulate::py_config():",
                         "\n%s%s" % (
                             curr_prefix + prefix,
                             ("\n" + curr_prefix + prefix).join(
                                 out.splitlines(False)))))
        finally:
            # Print things
            max_len = max(len(x[0]) for x in vardict)
            lines = []
            line_format = '%-' + str(max_len) + 's' + prefix + '%s'
            for k, v in vardict:
                lines.append(line_format % (k, v))
            msg = "yggdrasil info:\n%s" % '\n'.join(lines)
            if return_str:
                return msg
            logger.info(msg)

        
class validate_yaml(SubCommand):
    r"""Validate a set of or or more YAMLs defining an integration."""

    name = "validate"
    help = 'Validate a set of YAML specification files for an integration.'
    arguments = [
        (('yamlfile', ),
         {'nargs': '+',
          'help': 'One or more YAML specification files.'})]

    @classmethod
    def func(cls, args):
        from yggdrasil import yamlfile
        yamlfile.parse_yaml(args.yamlfile)
        logger.info("Validation succesful.")


class yggcc(SubCommand):
    r"""Compile a program."""

    name = "compile"
    help = ("Compile a program from source files for use in an "
            "yggdrasil integration.")
    arguments = [
        (('source', ),
         {'nargs': '+',
          'help': ("One or more source files or the directory containing an "
                   "R package.")}),
        (('--language', ),
         {'default': None,
          'choices': [None] + LANGUAGES_WITH_ALIASES['compiled'] + ['R', 'r'],
          'help': ("Language of the source code. If not provided, "
                   "the language will be determined from the "
                   "source extension.")}),
        (('--toolname', ),
         {'help': "Name of compilation tool that should be used"}),
        (('--flags', ),
         {'nargs': '*',
          'help': ("Additional flags that should be added to the compilation "
                   "command")}),
        (('--use-ccache', ),
         {'action': 'store_true', 'help': "Run compilation with ccache."}),
        (('--Rpkg-language', ),
         {'help': ("Language that R package is written in "
                   "(only used if the specified language is R).")})]

    @classmethod
    def func(cls, args):
        from yggdrasil.components import import_component
        from yggdrasil.constants import EXT2LANG
        if args.language is None:
            if (((len(args.source) == 1) and os.path.isdir(args.source[0])
                 and os.path.isdir(os.path.join(args.source[0], 'R')))):
                args.language = 'R'
            else:
                args.language = EXT2LANG[os.path.splitext(args.source[0])[-1]]
        drv = import_component('model', args.language)
        kws = {'toolname': args.toolname, 'flags': args.flags,
               'use_ccache': args.use_ccache}
        if (args.language in ['r', 'R']) and args.Rpkg_language:
            kws['language'] = args.Rpkg_language
        print("executable: %s" % drv.call_compiler(args.source, **kws))


class yggcompile(SubCommand):
    r"""Compile interface library/libraries."""

    name = "compile-deps"
    help = ("Compile yggdrasil dependency libraries. Existing "
            "libraries are first deleted.")
    arguments = [
        (('language', ),
         {'nargs': '*', 'default': ['all'],
          # 'choices': (['all'] + LANGUAGES_WITH_ALIASES['compiled']
          #             + LANGUAGES_WITH_ALIASES['compiled_dsl']),
          'help': ("One or more languages to compile dependencies "
                   "for.")}),
        (('--toolname', ),
         {'help': "Name of compilation tool that should be used"})]

    @classmethod
    def func(cls, args):
        from yggdrasil.components import import_component
        yggclean.func(args, verbose=False)
        error_on_missing = (not getattr(args, 'all_languages', False))
        missing = []
        for lang in args.language:
            import_component('model', lang).cleanup_dependencies()
            drv = import_component('model', lang)
            if ((hasattr(drv, 'compile_dependencies')
                 and (not getattr(drv, 'is_build_tool', False)))):
                if drv.is_installed():
                    drv.compile_dependencies(toolname=args.toolname)
                else:
                    missing.append(lang)
        if error_on_missing and missing:  # pragma: debug
            raise Exception(("One or more of the requested languages "
                             "are not fully installed for use with "
                             "yggdrasil: %s") % missing)


class yggclean(SubCommand):
    r"""Cleanup dependency files."""

    name = "clean"
    help = "Remove dependency libraries compiled by yggdrasil."
    arguments = [
        (('language', ),
         {'nargs': '*', 'default': ['all'],
          # 'choices': ['all'] + LANGUAGES_WITH_ALIASES['all'],
          'help': ("One or more languages to clean up dependencies "
                   "for.")})]

    @classmethod
    def func(cls, args, verbose=True):
        from yggdrasil.components import import_component
        for lang in args.language:
            if lang in ['ipc', 'ipcs']:
                from yggdrasil.communication.IPCComm import ipcrm_queues
                ipcrm_queues()
            else:
                import_component('model', lang).cleanup_dependencies(
                    verbose=verbose)


class cc_toolname(SubCommand):
    r"""Output the name of the compiler used to compile C or C++ programs."""

    name = "compiler-tool"
    help = 'Get the compiler used for C/C++ programs.'
    arguments = [
        (('--cpp', ),
         {'action': 'store_true',
          'help': 'Get the compiler used for C++ programs.'}),
        (('--fullpath', ),
         {'action': 'store_true',
          'help': 'Get the full path to the tool exectuable.'})]

    @classmethod
    def parse_args(cls, *args, **kwargs):
        args = super(cc_toolname, cls).parse_args(*args, **kwargs)
        args.tool = 'compiler'
        args.toolname = None
        args.flags = False
        if args.cpp:
            args.language = 'cpp'
        else:
            args.language = 'c'
        return args

    @classmethod
    def func(cls, args, **kwargs):
        ygginfo.func(args, **kwargs)


class ld_toolname(cc_toolname):
    r"""Output the name of the linker used to compile C or C++ programs."""

    name = "linker-tool"
    help = 'Get the linker used for C/C++ programs.'
    arguments = [
        (('--cpp', ),
         {'action': 'store_true',
          'help': 'Get the linker used for C++ programs.'}),
        (('--fullpath', ),
         {'action': 'store_true',
          'help': 'Get the full path to the tool exectuable.'})]

    @classmethod
    def parse_args(cls, *args, **kwargs):
        args = super(ld_toolname, cls).parse_args(*args, **kwargs)
        args.tool = 'linker'
        return args


class cc_flags(cc_toolname):
    r"""Get the compiler flags necessary for including the interface
    library in a C or C++ program."""

    name = "compiler-flags"
    help = 'Get the compilation flags necessary for a C/C++ program.'
    arguments = [
        (('--cpp', ),
         {'action': 'store_true',
          'help': 'Get the compilation flags used for C++ programs.'}),
        (('--toolname', ),
         {'default': None,
          'help': 'Name of the tool that associated flags be returned for.'})]

    @classmethod
    def parse_args(cls, *args, **kwargs):
        args = super(cc_flags, cls).parse_args(*args, **kwargs)
        args.flags = True
        return args


class ld_flags(cc_toolname):
    r"""Get the linker flags necessary for including the interface
    library in a C or C++ program."""

    name = "linker-flags"
    help = 'Get the compilation flags necessary for a C/C++ program.'
    arguments = [
        (('--cpp', ),
         {'action': 'store_true',
          'help': 'Get the compilation flags used for C++ programs.'}),
        (('--toolname', ),
         {'default': None,
          'help': 'Name of the tool that associated flags be returned for.'})]

    @classmethod
    def parse_args(cls, *args, **kwargs):
        args = super(ld_flags, cls).parse_args(*args, **kwargs)
        args.tool = 'linker'
        args.flags = True
        return args


class ygginstall(SubCommand):
    r"""Call installation script."""

    name = "install"

    @classmethod
    def get_parser(cls, **kwargs):
        from yggdrasil.languages import install_languages
        # TODO: Migrate
        return install_languages.update_argparser()

    @classmethod
    def func(cls, args):
        from yggdrasil.languages import install_languages
        for x in args.language:
            install_languages.install_language(x, args=args)


class update_config(SubCommand):
    r"""Update the user config file for yggdrasil."""

    name = "config"
    help = 'Update the user config file.'
    arguments = (
        [(('languages', ),
          {'nargs': '*',
           # 'choices': ['all'] + LANGUAGES_WITH_ALIASES['all'],
           'default': [],
           'help': 'One or more languages that should be configured.'}),
         (('--languages', ),
          {'nargs': '+', 'dest': 'languages_flag',
           # 'choices': ['all'] + LANGUAGES_WITH_ALIASES['all'],
           'default': [],
           'help': 'One or more languages that should be configured.'}),
         (('--show-file', ),
          {'action': 'store_true',
           'help': 'Print the path to the config file without updating it.'}),
         (('--remove-file', ),
          {'action': 'store_true',
           'help': 'Remove the existing config file and return.'}),
         (('--overwrite', ),
          {'action': 'store_true',
           'help': 'Overwrite the existing file.'}),
         (('--disable-languages', ),
          {'nargs': '+', 'default': [],
           'choices': LANGUAGES_WITH_ALIASES['all'],
           'help': 'One or more languages that should be disabled.'}),
         (('--enable-languages', ),
          {'nargs': '+', 'default': [],
           'choices': LANGUAGES_WITH_ALIASES['all'],
           'help': 'One or more languages that should be enabled.'}),
         (('--quiet', '-q'),
          {'action': 'store_true',
           'help': 'Suppress output.'}),
         (('--allow-multiple-omp', ),
          {'action': 'store_true',
           'help': ('Have yggdrasil set the environment variable '
                    'KMP_DUPLICATE_LIB_OK to \'True\' during model runs '
                    'to disable errors resembling '
                    '"OMP: Error #15: Initializing libomp.dylib..." '
                    'that result from having multiple versions of OpenMP '
                    'loaded during runtime.')}),
         (('--dont-allow-multiple-omp', ),
          {'action': 'store_false',
           'dest': 'allow_multiple_omp',
           'help': ('Don\'t set the KMP_DUPLICATE_LIB_OK environment variable '
                    'when running models (see help for \'--allow-multiple-omp\' '
                    'for more information).')})]
        + [(('--%s-compiler' % k, ),
            {'help': ('Name or path to compiler that should be used to compile '
                      'models written in %s.' % k)})
           for k in LANGUAGES['compiled']]
        + [(('--%s-linker' % k, ),
            {'help': ('Name or path to linker that should be used to link '
                      'models written in %s.' % k)})
           for k in LANGUAGES['compiled']]
        + [(('--%s-archiver' % k, ),
            {'help': ('Name or path to archiver that should be used to create '
                      'static libraries for models written in %s.' % k)})
           for k in LANGUAGES['compiled']]
    )
    # TODO: Move these into the language directories?
    language_arguments = {
        'c': [
            ConditionalArgumentTuple(
                ('--vcpkg-dir', ),
                {'help': 'Directory containing the vcpkg installation.'},
                conditions={'os': ['Windows']}),
            ConditionalArgumentTuple(
                ('--macos-sdkroot', '--sdkroot'),
                {'help': ('The full path to the MacOS SDK that '
                          'should be used.')},
                conditions={'os': ['MacOS']})],
        'matlab': [
            (('--disable-matlab-engine-for-python', ),
             {'action': 'store_true',
              'dest': 'disable_engine',
              'help': 'Disable use of the Matlab engine for Python.'}),
            (('--enable-matlab-engine-for-python', ),
             {'action': 'store_false',
              'dest': 'disable_engine',
              'help': 'Enable use of the Matlab engine for Python.'}),
            (('--hide-matlab-libiomp', ),
             {'action': 'store_true',
              'help': ('Hide the version of libiomp installed by Matlab '
                       'by slightly changing the filename so that the '
                       'conda version of libomp is used instead. This '
                       'helps to solve the error "'
                       'OMP: Error #15: Initializing libomp.dylib..." '
                       'that can occur when using a conda environment. '
                       'The hidden file location will be set in the '
                       'configuration file and can be restored via the '
                       '\'--restore-matlab-libiomp\' option.')}),
            (('--restore-matlab-libiomp', ),
             {'action': 'store_false',
              'dest': 'hide_matlab_libiomp',
              'help': ('Restore the version of libiomp installed by Matlab. '
                       '(See help for \'--hide-matlab-libiomp\')')}),
        ]}
        
    @classmethod
    def add_arguments(cls, parser, **kwargs):
        super(update_config, cls).add_arguments(parser, **kwargs)
        args = kwargs.get('args', None)
        if args is None:
            args = sys.argv[1:]
        if ('-h' in args) or ('--help' in args):
            args = [x for x in args if x not in ['-h', '--help']]
        preargs = parser.parse_known_args(args=args)[0]
        prelang = preargs.languages
        if preargs.languages_flag:
            prelang += preargs.languages_flag
        if (len(prelang) == 0) or ('all' in prelang):
            prelang = LANGUAGES['all']
        # TODO: The languages could be subparsers
        for k, v in cls.language_arguments.items():
            if k in prelang:
                cls.add_argument_to_parser(parser, v)

    @classmethod
    def func(cls, args):
        from yggdrasil import config
        if args.show_file:
            print('Config file located here: %s'
                  % config.usr_config_file)
        if args.remove_file and os.path.isfile(config.usr_config_file):
            os.remove(config.usr_config_file)
        if args.show_file or args.remove_file:
            return
        lang_kwargs = {}
        for k, v in cls.language_arguments.items():
            for v_args in v:
                name = v_args[1].get(
                    'dest',
                    v_args[0][0].lstrip('-').replace('-', '_'))
                if hasattr(args, name):
                    lang_kwargs.setdefault(k, {})
                    lang_kwargs[k][name] = getattr(args, name)
        for x in ['compiler', 'linker', 'archiver']:
            for k in LANGUAGES['compiled']:
                if getattr(args, '%s_%s' % (k, x), None):
                    lang_kwargs.setdefault(k, {})
                    lang_kwargs[k][x] = getattr(args, '%s_%s' % (k, x))
        config.update_language_config(
            args.languages, overwrite=args.overwrite,
            verbose=(not args.quiet),
            disable_languages=args.disable_languages,
            enable_languages=args.enable_languages,
            allow_multiple_omp=args.allow_multiple_omp,
            lang_kwargs=lang_kwargs)


class regen_metaschema(SubCommand):
    r"""Regenerate the yggdrasil metaschema."""

    name = "metaschema"
    help = "Regenerate the yggdrasil metaschema."

    @classmethod
    def func(cls, args):
        from yggdrasil import metaschema
        if os.path.isfile(metaschema._metaschema_fname):
            os.remove(metaschema._metaschema_fname)
        metaschema._metaschema = None
        metaschema._validator = None
        metaschema.get_metaschema()


class regen_schema(SubCommand):
    r"""Regenerate the yggdrasil schema."""

    name = "schema"
    help = "Regenerate the yggdrasil schema."
    arguments = [
        (('--only-constants', ),
         {'action': 'store_true',
          'help': ('Only update the constants.py file without updating '
                   'the schema.')})]

    @classmethod
    def func(cls, args):
        from yggdrasil import schema
        if not args.only_constants:
            if os.path.isfile(schema._schema_fname):
                os.remove(schema._schema_fname)
            schema.clear_schema()
            schema.init_schema()
        schema.update_constants()


class yggmodelform(SubCommand):
    r"""Save/print a JSON schema that can be used for generating a
    form for composing a model specification files."""

    name = "model-form-schema"
    help = ('Save/print the JSON schema for generating the model '
            'specification form.')
    arguments = [
        (('--file', ),
         {'help': 'Path to file where the schema should be saved.'})]

    @classmethod
    def func(cls, args):
        from yggdrasil.schema import get_model_form_schema
        out = get_model_form_schema(fname_dst=args.file)
        if not args.file:
            pprint.pprint(out)


class yggdevup(SubCommand):
    r"""Cleanup old libraries, re-install languages, and re-compile
    interface libraries following an update to the code (when doing
    development)."""

    name = "dev-update"
    help = ('Perform cleanup and reinitialization following an '
            'update to the code during development.')

    @classmethod
    def func(cls, args):
        yggclean(args=['all'])
        ygginstall(args=['all'])
        yggcompile(args=['all'])
        ygginfo(args=[])


class run_tsts(SubCommand):
    r"""Run yggdrasil test suite."""
    # TODO: Move this into a pytest extension?

    name = "test"
    help = 'Run yggdrasil tests.'
    arguments = [
        (('--withcoverage', '--with-coverage'),
         {'action': 'store_true',
          'help': 'Record coverage during tests.'}),
        (('--verbose', '-v'),
         {'action': 'store_true',
          'help': 'Increase verbosity of output from the test runner'}),
        (('--nocapture', '-s'),
         {'action': 'store_true',
          'help': 'Don\'t capture output from tests.'}),
        (('--stop', '-x'),
         {'action': 'store_true',
          'help': 'Stop after first test failure.'}),
        (('--nologcapture', ),
         {'action': 'store_true',
          'help': ('Don\'t capture output from log messages '
                   'generated during tests.')}),
        (('--noflaky', '--no-flaky'),
         {'action': 'store_true',
          'help': 'Don\'t re-run flaky tests.'}),
        (('--ci', ),
         {'action': 'store_true',
          'help': ('Perform addition operations required for '
                   'testing on continuous integration services.')}),
        (('--test-suite', '--test-suites'),
         {'nargs': '+', 'action': 'extend', 'type': str,
          'choices': ['all', 'top', 'examples', 'examples_part1',
                      'examples_part2', 'demos', 'types', 'timing',
                      'connections', 'models', 'mpi'],
          'help': 'Test suite(s) that should be run.',
          'dest': 'test_suites'}),
        (('--pytest-config', '-c'),
         {'help': ('Pytest configuration file that should be used '
                   'instead of the defaults.')}),
        (('--cov-config', ),
         {'help': 'Config file for coverage. Default: .coveragerc'}),
        (('--ignore', ),
         {'action': 'append',
          'help': 'Ignore path during collection.'}),
        (('--rootdir', ),
         {'help': 'Define root directory for tests.'}),
        (('--count', ),
         {'type': int, 'default': 1,
          'help': 'Number of times to repeat a test.'}),
        (('--with-mpi', '--mpi-nproc'),
         {'type': int, 'default': 1,
          'help': 'Number of MPI processes to run tests on.'}),
        (('--additional-info', '-r'),
         {'type': str, 'default': '',
          'help': 'Display additional info for test results.'})]
    allow_unknown = True

    @classmethod
    def add_arguments(cls, parser, **kwargs):
        from yggdrasil import config
        super(run_tsts, cls).add_arguments(parser, **kwargs)
        parser = config.get_config_parser(parser)

    @classmethod
    def parse_args(cls, *args, **kwargs):
        from yggdrasil import config, platform
        args = super(run_tsts, cls).parse_args(*args, **kwargs)
        extra = args._extra_commands
        if args.ci:
            args.verbose = True
            args.withcoverage = True
            args.setup_cfg = 'setup.cfg'
            args.pytest_config = args.setup_cfg
            args.cov_config = '.coveragerc'
            if not args.ignore:
                args.ignore = []
            args.ignore.append('yggdrasil/rapidjson/')
            args.rootdir = package_dir
            extra += ['--reruns=2', '--reruns-delay=1', '--timeout=900']
        # Separate out paths from options
        test_paths = []
        if args.test_suites:
            if 'all' in args.test_suites:
                args.test_suites.remove('all')
                for x in ['top', 'examples', 'demos', 'types', 'timing',
                          'connections', 'models', 'mpi']:
                    if x not in args.test_suites:
                        args.test_suites.append(x)
            for x in args.test_suites:
                if x == 'top':
                    test_paths.append(package_dir)
                elif x == 'examples':
                    args.enable_examples = True
                    test_paths.append('examples')
                elif x == 'examples_part1':
                    args.enable_examples = True
                    if platform._is_win:  # pragma: windows
                        pattern = 'test_[a-g]*.py'
                    else:
                        pattern = 'test_[A-Za-g]*.py'
                    test_paths.append(os.path.join(
                        'examples', 'tests', pattern))
                elif x == 'examples_part2':
                    args.enable_examples = True
                    pattern = 'test_[h-z]*.py'
                    test_paths.append(os.path.join(
                        'examples', 'tests', pattern))
                elif x == 'demos':
                    args.enable_demos = True
                    test_paths.append('demos')
                elif x == 'types':
                    args.enable_examples = True
                    args.long_running = True
                    test_paths.append(os.path.join('examples', 'tests',
                                                   'test_types.py'))
                elif x == 'timing':
                    args.long_running = True
                    args.enable_production_runs = True
                    test_paths.append(os.path.join('tests', 'test_timing.py'))
                elif x == 'connections':
                    for f in ['test_ConnectionDriver.py',
                              'test_FileInputDriver.py',
                              'test_FileOutputDriver.py',
                              'test_RPCRequestDriver.py']:
                        test_paths.append(
                            os.path.join('drivers', 'tests', f))
                elif x == 'models':
                    test_paths.append(
                        os.path.join('drivers', 'tests',
                                     'test_*ModelDriver.py'))
                elif x == 'mpi':
                    args.enable_examples = True
                    if args.with_mpi == 1:
                        args.with_mpi = 2
                    test_paths += [
                        os.path.join('communication', 'tests',
                                     'test_MPIComm.py'),
                        os.path.join('examples', 'tests',
                                     'test_gs_lesson4.py'),
                        os.path.join('examples', 'tests',
                                     'test_rpc_lesson3b.py')]
        if (not test_paths) and all(x.startswith('-') for x in extra):
            test_paths.append(package_dir)
        # Get expanded tests to allow for paths that are relative to
        # either the yggdrasil root directory or the current working
        # directory
        args = config.resolve_config_parser(args)
        args.extra = []
        cls.expand_and_add(extra + test_paths, args.extra,
                           [package_dir, os.getcwd()],
                           add_on_nomatch=True)
        return args

    @classmethod
    def expand_and_add(cls, path, path_list, dir_list,
                       add_on_nomatch=False):
        r"""Expand the specified path and add it's expanded forms to
        the provided list.

        Args:
            path (str): Absolute/relative path with or without regex
                wildcard expressions to expand.
            path_list (list): Existing list that expansions should be
                added to.
            dir_list (list): Directories that should be tried for
                relative paths.
            add_on_nomatch (bool, optional): If True, path will be added
                to path_list even if there are not matches. Defaults to
                False.

        Returns:
            int: The number of expansions added to path_list.

        """
        import glob
        if isinstance(path, list):
            nadded = 0
            for x in path:
                nadded += cls.expand_and_add(x, path_list, dir_list,
                                             add_on_nomatch=add_on_nomatch)
            return nadded
        if path.startswith('-'):
            if add_on_nomatch:
                path_list.append(path)
                return 1
            return 0
        elif path.endswith('yggtest'):
            return 0
        elif os.path.isabs(path):
            matches = sorted(glob.glob(path))
            path_list += matches
            if (not matches) and add_on_nomatch:
                path_list.append(path)
                return 1
            return len(matches)
        # Try checking for function
        for func_sep in ['::', ':']:
            if (func_sep in path):
                prepath, mod = path.rsplit(func_sep, 1)
                nadded = cls.expand_and_add(prepath, path_list, dir_list)
                if nadded:
                    for i in range(-nadded, 0):
                        path_list[i] += '%s%s' % (func_sep, mod)
                    return nadded
        # Try directory prefixes
        for path_prefix in dir_list:
            nadded = cls.expand_and_add(os.path.join(path_prefix, path),
                                        path_list, dir_list)
            if nadded:
                return nadded
        if add_on_nomatch:
            path_list.append(path)
            return 1
        return 0

    @classmethod
    def func(cls, args):
        from yggdrasil import config
        argv = [sys.executable, '-m', 'pytest']
        # test_paths = args.test_paths
        if args.with_mpi > 1:
            argv = ['mpiexec', '-n', str(args.with_mpi)] + argv + ['--with-mpi']
        if args.verbose:
            argv.append('-v')
        if args.nocapture:
            argv.append('-s')
            argv += ['-o', 'log_cli=true']
        if args.nologcapture:
            argv += ['-o', 'log_cli=true']
        if args.stop:
            argv.append('-x')
        if args.withcoverage:
            # See information about getting coverage of test fixtures
            # https://pytest-cov.readthedocs.io/en/stable/plugins.html
            argv.append('--cov=%s' % package_dir)
            # argv.append('--cov-append')
        if args.noflaky:
            argv += ['-p', 'no:flaky']
        if args.pytest_config:
            argv += ['-c', args.pytest_config]
        if args.cov_config:
            argv += ['--cov-config=%s' % args.cov_config]
        if args.ignore:
            argv += ['--ignore=%s' % x for x in args.ignore]
        if args.rootdir:
            argv += ['--rootdir=%s' % args.rootdir]
        if args.additional_info:
            argv += ['-r', args.additional_info]
        argv += args.extra
        # Run test command and perform cleanup before logging any errors
        logger.info("Running %s from %s", argv, os.getcwd())
        new_config = {}
        # pth_file = 'ygg_coverage.pth'
        # assert(not os.path.isfile(pth_file))
        # # Get arguments for temporary test environment
        # if args.withcoverage:
        #     new_config['COVERAGE_PROCESS_START'] = 'True'
        #     with open(pth_file, 'w') as fd:
        #         fd.write("import coverage; coverage.process_startup()")
        initial_dir = os.getcwd()
        error_code = 0
        with config.parser_config(args, **new_config):
            try:
                # Perform CI specific pretest operations
                if args.ci:
                    if not os.path.isfile(args.setup_cfg):
                        raise RuntimeError("The CI tests must be run "
                                           "from the root directory "
                                           "of the yggdrasil git "
                                           "repository.")
                    top_dir = os.path.dirname(os.getcwd())
                    src_cmd = ('python -c \"import versioneer; '
                               'print(versioneer.get_version())\"')
                    dst_cmd = ('python -c \"import yggdrasil; '
                               'print(yggdrasil.__version__)\"')
                    src_ver = subprocess.check_output(src_cmd,
                                                      shell=True)
                    dst_ver = subprocess.check_output(dst_cmd,
                                                      shell=True,
                                                      cwd=top_dir)
                    if src_ver != dst_ver:  # pragma: debug
                        raise RuntimeError(("Versions do not match:\n"
                                            "\tSource version: %s\n"
                                            "\tBuild  version: %s\n")
                                           % (src_ver, dst_ver))
                    subprocess.check_call(
                        ["flake8", "yggdrasil", "--append-config",
                         args.setup_cfg])
                    if os.environ.get("YGG_CONDA", None):
                        subprocess.check_call(
                            ["python", "create_coveragerc.py"])
                    if not os.path.isfile(".coveragerc"):
                        raise RuntimeError(".coveragerc file dosn't "
                                           "exist.")
                    with open(".coveragerc", "r") as fd:
                        print(fd.read())
                    subprocess.check_call(["yggdrasil", "info",
                                           "--verbose"])
                error_code = 0
                for x in range(args.count):
                    x_error_code = subprocess.call(argv)
                    if x_error_code != 0:
                        error_code = x_error_code
                        if args.stop:
                            break
            # except BaseException:
            #     logger.exception('Error in running test.')
            #     error_code = -1
            finally:
                os.chdir(initial_dir)
                # if os.path.isfile(pth_file):
                #     os.remove(pth_file)
        return error_code


class timing_plots(SubCommand):
    r"""Create performance plots using timing results."""

    name = "timing"
    help = "Create performance plots using timing results."
    arguments = [
        ArgumentSubparser(
            title='comparison', dest='comparison',
            description='Comparison plot that should be created.',
            parsers=[
                ArgumentParser(
                    name='commtype',
                    help='Compare different communication avenues.'),
                ArgumentParser(
                    name='language',
                    help='Compare different programming languages.'),
                ArgumentParser(
                    name='os',
                    help='Compare different operating systems.'),
                ArgumentParser(
                    name='python',
                    help='Compare different versions of Python.'),
                ArgumentParser(
                    name='lang2019',
                    help='Create plots from Lang (2019) paper.')])]

    @classmethod
    def func(cls, args):
        from yggdrasil import timing
        if args.comparison == 'lang2019':
            _lang_list = timing._lang_list
            _lang_list_nomatlab = copy.deepcopy(_lang_list)
            _lang_list_nomatlab.remove('matlab')
            timing.plot_scalings(compare='platform', python_ver='2.7')
            # All plots on Linux, no matlab
            timing.plot_scalings(compare='comm_type',
                                 platform='Linux',
                                 python_ver='2.7')
            timing.plot_scalings(compare='python_ver',
                                 platform='Linux')
            timing.plot_scalings(compare='language',
                                 platform='Linux',
                                 python_ver='2.7',
                                 compare_values=_lang_list_nomatlab)
            # Language comparision on MacOS, with matlab
            timing.plot_scalings(compare='language',
                                 platform='MacOS',
                                 python_ver='2.7',
                                 compare_values=_lang_list)
        else:
            if args.comparison == 'commtype':
                args.comparison = 'comm_type'
            elif args.comparison == 'os':
                args.comparison = 'platform'
            timing.plot_scalings(compare=args.comparison)


class generate_gha_workflow(SubCommand):
    r"""Re-generate the Github actions workflow yaml."""

    name = "gha"
    help = (
        "Generate a Github Actions (GHA) workflow yaml file from "
        "a version of the file that uses anchors (not supported by "
        "GHA as of 2021-01-14).")
    arguments = [
        (('--base', '--base-file'),
         {'help': (
             "Version of GHA workflow yaml that contains anchors.")}),
        (('--dest', ),
         {'help': (
             "Name of target GHA workflow yaml file.")}),
        (('--verbose', ),
         {'action': 'store_true', 'help': "Print yaml contents."})]

    @classmethod
    def func(cls, args, gitdir=None):
        import yaml
        from yggdrasil.metaschema.encoder import decode_yaml, encode_yaml
        from collections import OrderedDict

        class NoAliasDumper(yaml.SafeDumper):
            def ignore_aliases(self, data):
                return True
        if gitdir is None:
            try:
                gitdir = subprocess.check_output(
                    ["git", "rev-parse", "--git-dir"],
                    stderr=subprocess.PIPE).decode('utf-8').strip()
            except subprocess.CalledProcessError:
                return 1
        if args.base is None:
            args.base = os.path.join(gitdir, '..', 'utils',
                                     'test-install-base.yml')
        if args.dest is None:
            args.dest = os.path.join(gitdir, '..', '.github', 'workflows',
                                     'test-install.yml')
        with open(args.base, 'r') as fd:
            contents = decode_yaml(fd.read(), sorted_dict_type=OrderedDict)
            # contents = yaml.load(fd, Loader=yaml.SafeLoader)
        if args.verbose:
            pprint.pprint(contents)
        with open(args.dest, 'w') as fd:
            fd.write(('# DO NOT MODIFY THIS FILE, IT IS GENERATED.\n'
                      '# To make changes, modify \'%s\'\n'
                      '# and run \'ygggha\'\n')
                     % args.base)
            fd.write(encode_yaml(contents, sorted_dict_type=OrderedDict,
                                 Dumper=NoAliasDumper))
            # yaml.dump(contents, fd, Dumper=NoAliasDumper)


def rebuild_c_api():
    r"""Rebuild the C/C++ API."""
    ReplacementWarning('yggbuildapi_c', 'yggdrasil compile-deps c cpp')
    yggcompile(args=['c', 'cpp'] + sys.argv[1:])


def yggtime_comm():
    r"""Plot timing statistics comparing the different communication mechanisms."""
    ReplacementWarning('yggtime_comm', 'yggdrasil timing commtype')
    timing_plots(args=['commtype'] + sys.argv[1:])


def yggtime_lang():
    r"""Plot timing statistics comparing the different languages."""
    ReplacementWarning('yggtime_lang', 'yggdrasil timing language')
    timing_plots(args=['language'] + sys.argv[1:])


def yggtime_os():
    r"""Plot timing statistics comparing the different operating systems."""
    ReplacementWarning('yggtime_os', 'yggdrasil timing os')
    timing_plots(args=['os'] + sys.argv[1:])


def yggtime_py():
    r"""Plot timing statistics comparing the different versions of Python."""
    ReplacementWarning('yggtime_py', 'yggdrasil timing python')
    timing_plots(args=['python'] + sys.argv[1:])


def yggtime_paper():
    r"""Create plots for timing."""
    ReplacementWarning('yggtime_paper', 'yggdrasil timing lang2019')
    timing_plots(args=['lang2019'] + sys.argv[1:])


if __name__ == '__main__':
    yggrun()
    sys.exit(0)
