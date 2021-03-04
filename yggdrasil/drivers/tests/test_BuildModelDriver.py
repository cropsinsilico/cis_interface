import yggdrasil.drivers.tests.test_CompiledModelDriver as parent


class TestBuildModelParam(parent.TestCompiledModelParam):
    r"""Test parameters for BuildModelDriver."""
    pass


class TestBuildModelDriverNoInit(TestBuildModelParam,
                                 parent.TestCompiledModelDriverNoInit):
    """Test runner for BuildModelDriver without creating an instance."""

    test_build = None
    test_get_tool = None
    test_get_dependency_info = None
    test_get_dependency_source = None
    test_get_dependency_object = None
    test_get_dependency_library = None
    test_get_dependency_include_dirs = None
    test_get_dependency_order = None
    test_invalid_function_param = None


class TestBuildModelDriverNoStart(TestBuildModelParam,
                                  parent.TestCompiledModelDriverNoStart):
    r"""Test runner for BuildModelDriver without start."""

    test_compilers = None


class TestBuildModelDriver(TestBuildModelParam,
                           parent.TestCompiledModelDriver):
    r"""Test runner for BuildModelDriver."""
    pass
