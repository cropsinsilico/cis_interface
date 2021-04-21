import os
import six
import uuid
import unittest
import tempfile
import shutil
import itertools
import flaky
import subprocess
from yggdrasil.components import ComponentMeta, import_component
from yggdrasil import runner, tools, platform
from yggdrasil.examples import (
    get_example_yaml, get_example_source, get_example_languages,
    ext_map, display_example)
from yggdrasil.tests import YggTestBase, check_enabled_languages, assert_raises
from yggdrasil.tests import timeout as timeout_dec


_ext2lang = {v: k for k, v in ext_map.items()}
_test_registry = {}
_default_comm = tools.get_default_comm()


def test_get_example_yaml():
    r"""Test get_example_yaml."""
    assert_raises(KeyError, get_example_yaml, 'invalid', 'invalid')
    assert_raises(KeyError, get_example_yaml, 'hello', 'invalid')
    get_example_yaml('hello', 'r')
    get_example_yaml('hello', 'R')


def test_get_example_source():
    r"""Test get_example_source."""
    assert_raises(KeyError, get_example_source, 'invalid', 'invalid')
    assert_raises(KeyError, get_example_source, 'hello', 'invalid')
    get_example_source('hello', 'r')
    get_example_source('hello', 'R')


def test_get_example_languages():
    r"""Test get_example_languages."""
    assert_raises(KeyError, get_example_languages, 'invalid')
    get_example_languages('ascii_io')
    get_example_languages('ascii_io', language='python')
    get_example_languages('ascii_io', language='all')
    get_example_languages('ascii_io', language='all_nomatlab')


def test_display_example():
    r"""Test display_example."""
    display_example('hello', 'r')


def iter_pattern_match(a, b):
    r"""Determine if two sets of iteration parameters match, allowing
    for wild cards.

    Args:
        a (tuple): Iteration parameters.
        b (tuple): Iteration parameters.

    Returns:
        bool: True if the parameters match, False otherwise.

    """
    assert(not isinstance(a, list))
    if isinstance(b, list):
        matches = [iter_pattern_match(a, ib) for ib in b]
        return any(matches)
    matches = []
    for ia, ib in zip(a, b):
        if not ((ia == ib) or (ia == '*') or (ib == '*')
                or (isinstance(ia, tuple) and (ib in ia))
                or (isinstance(ib, tuple) and (ia in ib))
                or (isinstance(ia, set) and (ib not in ia))
                or (isinstance(ib, set) and (ia not in ib))):
            return False
    return True


def make_iter_test(is_flaky=False, **kwargs):
    def itest(self):
        if is_flaky:
            self.sleep(1.0)
        self.run_iteration(**kwargs)
    if is_flaky:
        itest = flaky.flaky(max_runs=3)(itest)
    return itest


def example_decorator(name, x, iter_over, timeout):
    r"""Consolidate decorator based on iteration values.

    Args:
        name (str): Example name.
        x (list): Iteration parameters.
        iter_over (list): Iteration dimensions.
        timeout (float): Test timeout.

    Returns:
        function: Decorator.

    """

    def deco(func):
        deco_list = [
            timeout_dec(timeout=timeout),
            unittest.skipIf(
                (not tools.check_environ_bool('YGG_ENABLE_EXAMPLE_TESTS')),
                "Example tests not enabled."),
        ]
        for i, k in enumerate(iter_over):
            v = x[i]
            flag = None
            msg = None
            if k == 'comm':
                flag = tools.is_comm_installed(v)
            elif k == 'language':
                flag = True
                for vv in get_example_languages(name, language=v):
                    if not tools.is_lang_installed(vv):
                        flag = False
                        break
            if flag is not None:
                if msg is None:
                    msg = "%s %s not installed." % (k.title(), v)
                deco_list.append(unittest.skipIf(not flag, msg))
        for v in deco_list:
            func = v(func)
        return func

    return deco


class ExampleMeta(ComponentMeta):

    def __new__(cls, name, bases, dct):
        if dct.get('example_name', None) is not None:
            dct.setdefault('iter_list_language',
                           get_example_languages(dct['example_name']))
        timeout = dct.get('timeout', 600)
        iter_lists = []
        iter_keys = []
        test_name_fmt = 'test'
        iter_skip = dct.get('iter_skip', [])
        iter_flaky = dct.get('iter_flaky', [])
        iter_over = dct.get('iter_over', ['language'])
        iter_aliases = {'lang': 'language',
                        'type': 'datatype',
                        'types': 'datatype'}
        iter_over = [iter_aliases.get(x, x) for x in iter_over]
        for x in iter_over:
            test_name_fmt += '_%s'
            x_iter_list = dct.get('iter_list_%s' % x, None)
            for ibase in bases:
                if x_iter_list is not None:
                    break
                x_iter_list = getattr(ibase, 'iter_list_%s' % x, None)
            if x_iter_list is not None:
                iter_lists.append(x_iter_list)
                iter_keys.append(x)
            elif dct.get('example_name', None) is not None:  # pragma: debug
                raise ValueError("Unsupported iter dimension: %s" % x)
        if dct.get('example_name', None) is not None:
            for x in itertools.product(*iter_lists):
                if iter_pattern_match(x, iter_skip):
                    continue
                itest_name = (test_name_fmt % x)
                if itest_name not in dct:
                    itest_func = make_iter_test(
                        is_flaky=iter_pattern_match(x, iter_flaky),
                        **{k: v for k, v in
                           zip(iter_keys, x)})
                    itest_func.__name__ = itest_name
                    if timeout is not None:
                        itest_func = example_decorator(
                            dct['example_name'], x, iter_over, timeout)(itest_func)
                    dct[itest_name] = itest_func
        out = super(ExampleMeta, cls).__new__(cls, name, bases, dct)
        if out.example_name is not None:
            global _test_registry
            _test_registry[out.example_name] = out
        # else:
        #     out = unittest.skipIf(True, "Test uninitialized.")(out)
        return out


@six.add_metaclass(ExampleMeta)
class ExampleTstBase(YggTestBase, tools.YggClass):
    r"""Base class for running examples."""

    example_name = None
    expects_error = False
    env = {}
    iter_over = ['language']
    iter_skip = []
    iter_flaky = []
    iter_list_language = None
    iter_list_comm = tools.get_supported_comm(dont_include_value=True)
    iter_list_datatype = tools.get_supported_type()

    def __init__(self, *args, **kwargs):
        tools.YggClass.__init__(self, self.example_name)
        self.iter_param = {}
        self.uuid = str(uuid.uuid4())
        self.runner = None
        # self.debug_flag = True
        super(ExampleTstBase, self).__init__(*args, **kwargs)

    @property
    def language(self):
        r"""str: Language of the currect test."""
        return self.iter_param.get('language', None)

    @property
    def comm(self):
        r"""str: Comm used by the current test."""
        return self.iter_param.get('comm', _default_comm)

    @property
    def description_prefix(self):
        r"""Prefix message with test name."""
        return self.name

    @property
    def namespace(self):
        r"""str: Namespace for the example."""
        return "%s_%s" % (self.name, self.uuid)

    @property
    def tempdir(self):
        r"""str: Temporary directory."""
        return tempfile.gettempdir()

    @property
    def languages_tested(self):
        r"""list: Languages covered by the example."""
        return get_example_languages(self.name, language=self.language)

    @property
    def yaml(self):
        r"""str: The full path to the yaml file for this example."""
        return get_example_yaml(self.name, self.language)

    @property
    def yamldir(self):
        r"""str: Full path to the directory containing the yaml file."""
        if self.yaml is None:  # pragma: no cover
            return None
        if isinstance(self.yaml, list):
            out = os.path.dirname(self.yaml[0])
        else:
            out = os.path.dirname(self.yaml)
        return out

    # @property
    # def yaml_contents(self):
    #     r"""dict: Contents of yaml file."""
    #     if self.yaml is None:  # pragma: no cover
    #         return None
    #     return tools.parse_yaml(self.yaml)

    @property
    def input_files(self):  # pragma: debug
        r"""list: Input files for the run."""
        return None

    @property
    def expected_output_files(self):  # pragma: debug
        r"""list: Examples of expected output for the run."""
        return self.input_files

    @property
    def output_files(self):
        r"""list: Output files for the run."""
        return None

    @property
    def results(self):
        r"""list: Results that should be found in the output files."""
        if self.expected_output_files is None:  # pragma: debug
            return None
        out = []
        for fname in self.expected_output_files:
            assert(os.path.isfile(fname))
            out.append(self.read_file(fname))
        return out

    def check_results(self):
        r"""This should be overridden with checks for the result."""
        if self.output_files is None:
            return
        res_list = self.results
        out_list = self.output_files
        assert(res_list is not None)
        assert(out_list is not None)
        self.assert_equal(len(res_list), len(out_list))
        for res, fout in zip(res_list, out_list):
            self.check_file_exists(fout)
            if isinstance(res, tuple):
                res[0](fout, *res[1:])
            else:
                self.check_file_size(fout, res)
                self.check_file_contents(fout, res)

    def run_example(self):
        r"""This runs an example in the correct language."""
        assert(self.yaml is not None)
        assert(self.name is not None)
        # Check that language is installed
        for x in self.languages_tested:
            if not tools.is_lang_installed(x):
                raise unittest.SkipTest("%s not installed." % x)
            check_enabled_languages(x)
        # Copy platform specific makefile
        if self.language == 'make':
            makefile = os.path.join(self.yamldir, 'src', 'Makefile')
            if platform._is_win:  # pragma: windows
                makedrv = import_component('model', 'make')
                assert(makedrv.get_tool('compiler').toolname == 'nmake')
                make_ext = '_windows'
            else:
                make_ext = '_linux'
            shutil.copy(makefile + make_ext, makefile)
        # Check that comm is installed
        if self.comm in ['ipc', 'IPCComm']:
            from yggdrasil.communication.IPCComm import (
                ipcrm_queues, ipc_queues)
            qlist = ipc_queues()
            if qlist:  # pragma: debug
                print('Existing queues:', qlist)
                ipcrm_queues()
        # Run
        os.environ.update(self.env)
        if self.iter_param.get('mpi', False):
            try:
                nproc = 2
                args = ['mpirun', '-n', str(nproc), 'yggrun']
                if isinstance(self.yaml, str):
                    args.append(self.yaml)
                else:
                    args += self.yaml
                args += ['--namespace=%s' % self.namespace, '--production-run']
                subprocess.check_call(args)
                assert(not self.expects_error)
            except subprocess.CalledProcessError:
                if not self.expects_error:
                    raise
        else:
            self.runner = runner.get_runner(self.yaml, namespace=self.namespace,
                                            production_run=True)
            self.runner.run()
            if self.expects_error:
                assert(self.runner.error_flag)
            else:
                assert(not self.runner.error_flag)
        try:
            self.check_results()
        except BaseException:  # pragma: debug
            if self.runner is not None:
                self.runner.printStatus()
            raise
        finally:
            self.example_cleanup()
            # Remove copied makefile
            if self.language == 'make':
                makefile = os.path.join(self.yamldir, 'src', 'Makefile')
                if os.path.isfile(makefile):
                    os.remove(makefile)
            self.runner = None

    def example_cleanup(self):
        r"""Cleanup files created during the test."""
        if (self.yaml is not None) and (self.output_files is not None):
            timer_class = tools.YggClass()
            for fout in self.output_files:
                if os.path.isfile(fout):
                    tools.remove_path(fout, timer_class=timer_class, timeout=5)

    def setup_iteration(self, **kwargs):
        r"""Perform setup associated with an iteration."""
        for k, v in kwargs.items():
            k_setup = getattr(self, 'setup_iteration_%s' % k, None)
            if k_setup is not None:
                v = k_setup(v)
            self.iter_param[k] = v

    def teardown_iteration(self, **kwargs):
        r"""Perform teardown associated with an iteration."""
        for k, v in kwargs.items():
            k_teardown = getattr(self, 'teardown_iteration_%s' % k, None)
            if k_teardown is not None:
                k_teardown(v)
            del self.iter_param[k]
        assert(not self.iter_param)
        self.iter_param = {}

    def setup_iteration_mpi(self, mpi=None):
        r"""Perform setup associated with an MPI iteration."""
        if mpi:
            try:
                import mpi4py  # noqa: F401
            except ImportError:
                raise unittest.SkipTest("mpi4py not installed")
        return mpi

    def setup_iteration_language(self, language=None):
        r"""Perform setup associated with a language iteration."""
        if language is not None:
            for x in get_example_languages(self.example_name,
                                           language=language):
                check_enabled_languages(x)
        return language

    def setup_iteration_comm(self, comm=None):
        r"""Perform setup associated with a comm iteration."""
        assert(comm is not None)
        # if not tools.is_comm_installed(comm):
        #     raise unittest.SkipTest("%s library not installed."
        #                             % comm)
        self.set_default_comm(default_comm=comm)
        return comm

    def teardown_iteration_comm(self, comm=None):
        r"""Peform teardown associated with a comm iteration."""
        self.reset_default_comm()

    def run_iteration(self, **kwargs):
        r"""Run a test for the specified parameters."""
        if not tools.check_environ_bool('YGG_ENABLE_EXAMPLE_TESTS'):
            raise unittest.SkipTest("Example tests not enabled.")
        self.setup_iteration(**kwargs)
        try:
            getattr(self, kwargs.get('method', 'run_example'))()
        finally:
            self.teardown_iteration(**kwargs)
