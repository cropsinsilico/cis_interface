import os
import sys
import argparse
import uuid
import pprint
import shutil
import subprocess
import warnings
import difflib
from datetime import datetime
PYVER = ('%s.%s' % sys.version_info[:2])
PY2 = (sys.version_info[0] == 2)
_is_osx = (sys.platform == 'darwin')
_is_linux = ('linux' in sys.platform)
_is_win = (sys.platform in ['win32', 'cygwin'])
_is_unix = (_is_osx or _is_linux)
_on_gha = bool(os.environ.get('GITHUB_ACTIONS', False))
_on_travis = bool(os.environ.get('TRAVIS_OS_NAME', False))
_on_appveyor = bool(os.environ.get('APPVEYOR_BUILD_FOLDER', False))
_on_ci = (_on_gha or _on_travis or _on_appveyor)
_utils_dir = os.path.dirname(os.path.abspath(__file__))
_pkg_dir = os.path.dirname(_utils_dir)
BUILDDOCS = (os.environ.get('BUILDDOCS', '0') == '1')
CONDA_ENV = os.environ.get('CONDA_DEFAULT_ENV', None)
CONDA_PREFIX = os.environ.get('CONDA_PREFIX', None)
CONDA_INDEX = None
CONDA_ROOT = None
try:
    CONDA_CMD_WHICH = shutil.which('conda')
except AttributeError:
    if _is_win:
        CONDA_CMD_WHICH = None
    else:
        try:
            CONDA_CMD_WHICH = subprocess.check_output(
                ['which', 'conda']).strip().decode('utf-8')
        except subprocess.CalledProcessError:
            CONDA_CMD_WHICH = None
if (not CONDA_PREFIX):
    if CONDA_CMD_WHICH:
        CONDA_PREFIX = os.path.dirname(os.path.dirname(CONDA_CMD_WHICH))
    elif _on_gha and os.environ.get('CONDA', None):
        CONDA_PREFIX = os.environ['CONDA']
    if CONDA_PREFIX and (not CONDA_ENV):
        CONDA_ENV = 'base'
if ((isinstance(CONDA_PREFIX, str)
     and os.path.dirname(CONDA_PREFIX).endswith('envs'))):
    CONDA_PREFIX = os.path.dirname(os.path.dirname(CONDA_PREFIX))
if CONDA_PREFIX:
    CONDA_INDEX = os.path.join(CONDA_PREFIX, "conda-bld")
    if not os.path.isdir(CONDA_INDEX):
        if _on_gha and _is_win and CONDA_PREFIX.endswith('Library'):
            CONDA_INDEX = os.path.join(os.path.dirname(CONDA_PREFIX),
                                       "conda-bld")
if CONDA_CMD_WHICH:
    if _is_win:
        CONDA_CMD = 'call conda'
    else:
        CONDA_CMD = 'conda'
    CONDA_ROOT = os.path.dirname(os.path.dirname(CONDA_CMD_WHICH))
elif os.environ.get('CONDA', None):
    if _is_win:
        CONDA_CMD = 'call %s' % os.path.join(os.environ['CONDA'],
                                             'condabin', 'conda.bat')
    else:
        CONDA_CMD = os.path.join(os.environ['CONDA'], 'bin', 'conda')
    CONDA_ROOT = os.environ['CONDA']
else:
    CONDA_CMD = None
PYTHON_CMD = sys.executable
SUMMARY_CMDS = ["%s --version" % PYTHON_CMD,
                "%s -m pip list" % PYTHON_CMD]
if CONDA_ENV:
    SUMMARY_CMDS += ["echo 'CONDA_PREFIX=%s'" % CONDA_PREFIX,
                     "%s info" % CONDA_CMD,
                     "%s list" % CONDA_CMD,
                     "%s config --show-sources" % CONDA_CMD]


def call_conda_command(args, **kwargs):
    r"""Function for calling conda commands as the conda script is not
    available on subprocesses for windows unless invoked via the shell.

    Args:
        args (list): Command arguments.
        **kwargs: Additional keyword arguments are passed to subprocess.check_output.

    Returns:
        str: The output from the command.

    """
    if _is_win:
        args = ' '.join(args)
        kwargs['shell'] = True  # Conda commands must be run on the shell
    return subprocess.check_output(args, **kwargs).decode("utf-8")


def call_script(lines, force_bash=False):
    r"""Write lines to a script and call it.

    Args:
        lines (list): Lines that should be written to the script.
        force_bash (bool, optional): If True, bash will be used, even
            on windows. Defaults to False.

    """
    if not lines:
        return
    if _is_win and (not force_bash):  # pragma: windows
        script_ext = '.bat'
        error_check = 'if %errorlevel% neq 0 exit /b %errorlevel%'
        for i in range(len(lines), 0, -1):
            lines.insert(i, error_check)
    else:
        script_ext = '.sh'
        if lines[0] != '#!/bin/bash':
            lines.insert(0, '#!/bin/bash')
        error_check = 'set -e'
        if error_check not in lines:
            lines.insert(1, error_check)
    fname = 'ci_script_%s%s' % (str(uuid.uuid4()), script_ext)
    try:
        pprint.pprint(lines)
        with open(fname, 'w') as fd:
            fd.write('\n'.join(lines))
            
        call_kws = {}
        if _is_win:  # pragma: windows
            call_cmd = [fname]
        else:
            call_cmd = ['./%s' % fname]
            os.chmod(fname, 0o755)
        subprocess.check_call(call_cmd, **call_kws)
    finally:
        if os.path.isfile(fname):
            os.remove(fname)


def conda_env_exists(name):
    r"""Determine if a conda environment already exists.

    Args:
        name (str): Name of the environment to check.

    Returns:
        bool: True the the environment exits, False otherwise.

    """
    args = [CONDA_CMD, 'info', '--envs']
    out = call_conda_command(args)
    envs = []
    for x in out.splitlines():
        if x.startswith('#') or (not x):
            continue
        envs.append(x.split()[0])
    return (name in envs)


def locate_conda_exe(conda_env, name):
    r"""Determine the full path to an executable in a specific conda environment.

    Args:
        conda_env (str): Name of conda environment that executable should be
            returned for.
        name (str): Name of the executable to locate.

    Returns:
        str: Full path to the executable.

    """
    assert(CONDA_ROOT)
    conda_prefix = os.path.join(CONDA_ROOT, 'envs')
    if (sys.platform in ['win32', 'cygwin']):
        if not name.endswith('.exe'):
            name += '.exe'
        if name.startswith('python'):
            out = os.path.join(conda_prefix, conda_env, name)
        else:
            out = os.path.join(conda_prefix, conda_env,
                               'Scripts', name)
    else:
        out = os.path.join(conda_prefix, conda_env, 'bin', name)
    try:
        assert(os.path.isfile(out))
    except AssertionError:
        out = os.path.expanduser(os.path.join('~', '.conda', 'envs', name))
        if not os.path.isfile(out):
            raise
    return out


def get_install_opts(old=None):
    r"""Get optional language/package installation options from CI
    environment variables.

    Args:
        old (dict, optional): If provided, the returned mapping will include
            the values from this dictionary, but will also be updated with any
            that are missing.

    Returns:
        dict: Mapping between languages/packages and whether or not they
            should be installed.

    """
    if _on_ci:
        new = {
            'c': (os.environ.get('INSTALLC', '0') == '1'),
            'lpy': (os.environ.get('INSTALLLPY', '0') == '1'),
            'R': (os.environ.get('INSTALLR', '0') == '1'),
            'fortran': (os.environ.get('INSTALLFORTRAN', '0') == '1'),
            'zmq': (os.environ.get('INSTALLZMQ', '0') == '1'),
            'sbml': (os.environ.get('INSTALLSBML', '0') == '1'),
            'astropy': (os.environ.get('INSTALLAPY', '0') == '1'),
            'rmq': (os.environ.get('INSTALLRMQ', '0') == '1'),
            'trimesh': (os.environ.get('INSTALLTRIMESH', '0') == '1'),
            'pygments': (os.environ.get('INSTALLPYGMENTS', '0') == '1'),
            'omp': (os.environ.get('INSTALLOMP', '0') == '1'),
            'mpi': (os.environ.get('INSTALLMPI', '0') == '1'),
        }
        if not _is_win:
            new['c'] = True  # c compiler usually installed by default
    else:
        new = {
            'c': True,
            'lpy': False,
            'R': True,
            'fortran': True,
            'zmq': True,
            'sbml': False,
            'astropy': False,
            'rmq': False,
            'trimesh': True,
            'pygments': True,
            'omp': False,
            'mpi': False,
        }
    if _is_win:
        new['os'] = 'win'
    elif _is_osx:
        new['os'] = 'osx'
    elif _is_linux:
        new['os'] = 'linux'
    if old is None:
        out = {}
    else:
        out = old.copy()
    for k, v in new.items():
        out.setdefault(k, v)
    if not out['c']:
        out.update(fortran=False, zmq=False)
    return out


def add_install_opts_args(parser):
    r"""Add arguments to a parser for installation options.

    Args:
        parser (argparse.ArgumentParser): Parser to add arguments to.

    """
    for k, v in install_opts.items():
        if k in ['os']:
            continue
        if v:
            parser.add_argument(
                '--dont-install-%s' % k, action='store_true',
                help=("Don't install %s" % k))
        else:
            parser.add_argument(
                '--install-%s' % k, action='store_true',
                help=("Install %s" % k))


def create_env(method, python, name=None, packages=None, init=_on_ci):
    r"""Setup a test environment on a CI resource.

    Args:
        method (str): Method that should be used to create an environment.
            Supported values currently include 'conda' & 'virtualenv'.
        python (str): Version of Python that should be tested.
        name (str, optional): Name that should be used for the environment.
            Defaults to None and will be craeted based on the method and
            Python version.
        packages (list, optional): Packages that should be installed in the new
            environment. Defaults to None and is ignored.
        init (bool, optional): If True, the environment management program is
            first configured as if it is one CI so that, some interactive
            aspects will be disabled. Default is set based on the presence of
            CI environment variables (it currently checks for Github Actions,
            Travis CI, and Appveyor)

    Raises:
        ValueError: If method is not 'conda' or 'pip'.

    """
    cmds = ["echo Creating test environment using %s..." % method]
    major, minor = [int(x) for x in python.split('.')]
    if name is None:
        name = '%s%s' % (method, python.replace('.', ''))
    if packages is None:
        packages = []
    if 'requests' not in packages:
        # Not strictly required, but useful for determine the versions of
        # dependencies required by packages during testing
        packages.append('requests')
    if method == 'conda':
        if conda_env_exists(name):
            print("Conda env with name '%s' already exists." % name)
            return
        if init:
            cmds += [
                # Configure conda
                "%s config --set always_yes yes --set changeps1 no" % CONDA_CMD,
                "%s config --set channel_priority strict" % CONDA_CMD,
                "%s config --add channels conda-forge" % CONDA_CMD,
                "%s update -q conda" % CONDA_CMD,
                # "%s config --set allow_conda_downgrades true" % CONDA_CMD,
                # "%s install -n root conda=4.9" % CONDA_CMD,
            ]
        cmds += [
            "%s create -q -n %s python=%s %s" % (CONDA_CMD, name, python,
                                                 ' '.join(packages))
        ]
    elif method == 'virtualenv':
        python_cmd = PYTHON_CMD
        if (sys.version_info[0] != major) or (sys.version_info[1] != minor):
            if _is_osx:
                try:
                    call_script(['python%d --version' % major])
                except BaseException:
                    cmds.append('brew install python%d' % major)
                try:
                    python_cmd = shutil.which('python%d' % major)
                except AttributeError:
                    python_cmd = 'python%d' % major
            else:  # pragma: debug
                raise RuntimeError(("The version of Python (%d.%d) does not match the "
                                    "desired version (%s) and virtualenv cannot create "
                                    "an environment with a different version of Python.")
                                   % (sys.version_info[0], sys.version_info[1], python))
        cmds += [
            "%s -m pip install --upgrade pip virtualenv" % python_cmd,
            "virtualenv -p %s %s" % (python_cmd, name)
        ]
        if packages:
            cmds.append("%s -m pip install %s" % (python_cmd, ' '.join(packages)))
    else:  # pragma: debug
        raise ValueError("Unsupport environment management method: '%s'"
                         % method)
    call_script(cmds)


def build_pkg(method, python=None, return_commands=False,
              verbose=False):
    r"""Build the package on a CI resource.

    Args:
        method (str): Method that should be used to build the package.
            Valid values include 'conda' and 'pip'.
        python (str, optional): Version of Python that package should be
            built for. Defaults to None if not provided and the current
            version of Python will be used.
        return_commands (bool, optional): If True, the commands necessary to
            build the package are returned instead of running them. Defaults
            to False.
        verbose (bool, optional): If True, setup steps are run with verbosity
            turned up. Defaults to False.

    """
    if python is None:
        python = PYVER
    cmds = []
    # Upgrade pip and setuptools and wheel to get clean install
    upgrade_pkgs = ['wheel', 'setuptools']
    if not _is_win:
        upgrade_pkgs.insert(0, 'pip')
    # cmds += ["%s -m pip install --upgrade %s" % (PYTHON_CMD, ' '.join(upgrade_pkgs))]
    if method == 'conda':
        if verbose:
            build_flags = ''
        else:
            build_flags = '-q'
        # Must always build in base to avoid errors (and don't change the
        # version of Python used in the environment)
        # https://github.com/conda/conda/issues/9124
        # https://github.com/conda/conda/issues/7758#issuecomment-660328841
        assert(CONDA_ENV == 'base')
        assert(CONDA_INDEX)
        if _on_gha:
            cmds += [
                "%s config --add channels conda-forge" % CONDA_CMD,
                "%s update -q conda" % CONDA_CMD,
            ]
        if _is_win and _on_gha:
            # The tests issue a command that is too long for the
            # windows command prompt which is used to build the conda
            # package on Github Actions
            build_flags += ' --no-test'
        cmds += [
            "%s clean --all" % CONDA_CMD,  # Might invalidate cache
            # "%s deactivate" % CONDA_CMD,
            "%s update --all" % CONDA_CMD,
            "%s install -q -n base conda-build conda-verify" % CONDA_CMD,
            "%s build %s --python %s %s" % (
                CONDA_CMD, 'recipe', python, build_flags),
            "%s index %s" % (CONDA_CMD, CONDA_INDEX),
            # "%s activate %s" % (CONDA_CMD, CONDA_ENV),
        ]
    elif method == 'pip':
        if verbose:
            build_flags = ''
        else:
            build_flags = '--quiet'
        # Install from source dist
        cmds += ["%s -m pip install --upgrade %s" % (PYTHON_CMD, ' '.join(upgrade_pkgs))]
        cmds += ["%s setup.py %s sdist" % (PYTHON_CMD, build_flags)]
    else:  # pragma: debug
        raise ValueError("Method must be 'conda' or 'pip', not '%s'"
                         % method)
    if return_commands:
        return cmds
    cmds = SUMMARY_CMDS + cmds + SUMMARY_CMDS
    call_script(cmds)
    if method == 'conda':
        assert(CONDA_INDEX and os.path.isdir(CONDA_INDEX))


def create_env_yaml(filename='environment.yml', name='env', channels=None,
                    install_opts=None, target_os=None, python_version=None,
                    **kwargs):
    r"""Create an environment.yml file.

    Args:
        filename (str, optional): Path where the generate file should be
            saved. Defaults to 'environment.yml'.
        name (str, optional): Name of environment that should be
            created by the file. Defaults to 'env'.
        channels (list, optional): Conda channels that should be used in the
            environment file. Defaults to []. 'conda-forge' will be added
            if it is not already present.
        install_opts (dict, optional): Mapping from language/package to bool
            specifying whether or not the language/package should be installed.
            If not provided, get_install_opts is used to create it.
        target_os (str, optional): Operating system that the generated file
            should target. Defaults to the current OS.
        python_version (str, optional): Python version that environment
            should target. Defaults to the current Python version if not
            provided.
        **kwargs: Additional keyword arguments are passed to itemize_deps.

    """
    import yaml
    import platform
    from install_from_requirements import prune
    if channels is None:
        channels = []
    if 'conda-forge' not in channels:
        channels.append('conda-forge')
    if python_version is None:
        python_version = ".".join(platform.python_version_tuple()[:2])
    environment = {'python_version': python_version}
    if target_os is not None:
        if target_os == 'linux':
            environment["os_name"] = 'Linux'
        elif target_os == 'osx':
            environment["os_name"] = 'Darwin'
        elif target_os == 'win':
            environment["os_name"] = 'Windows'
    install_opts = get_install_opts(install_opts)
    pkgs = itemize_deps('conda', install_opts=install_opts, **kwargs)
    deps = prune(pkgs['requirements'] + pkgs['requirements_conda'],
                 install_opts=install_opts, excl_method='pip',
                 additional_packages=pkgs['conda'],
                 skip_packages=pkgs['skip'],
                 return_list=True, environment=environment,
                 verbose=True)
    deps.insert(0, 'python=' + python_version)
    data = {'name': name,
            'channels': channels,
            'dependencies': deps}
    with open(filename, 'w') as fd:
        yaml.dump(data, fd, Dumper=yaml.SafeDumper)
    return filename


def itemize_deps(method, for_development=False,
                 skip_test_deps=False, include_dev_deps=False, include_doc_deps=False,
                 windows_package_manager='vcpkg', install_opts=None,
                 fallback_to_conda=None):
    r"""Get lists of dependencies.
    
    Args:
        method (str): Method that should be used to install the package dependencies.
            Valid values include 'conda' and 'pip'.
        for_development (bool, optional): If True, dependencies are installed that would
            be missed when installing in development mode. Defaults to False.
        skip_test_deps (bool, optional): If True, dependencies required for running
            tests will not be installed. Defaults to False.
        include_dev_deps (bool, optional): If True, dependencies used during development
            will be installed. Defaults to False.
        include_doc_deps (bool, optional): If True, dependencies used during generating
            documentation will be installed. Defaults to False.
        windows_package_manager (str, optional): Name of the package
            manager that should be used on windows. Defaults to 'vcpkg'.
        install_opts (dict, optional): Mapping from language/package to bool
            specifying whether or not the language/package should be installed.
            If not provided, get_install_opts is used to create it.
        fallback_to_conda (bool, optional): If True, conda will be used to install
            non-python dependencies and Python dependencies that cannot be installed
            via pip. Defaults to False.

    Returns:
        dict: Dependencies grouped by the package manager that should be
            used.

    """
    from install_from_requirements import get_pip_dependency_version
    out = {'conda': [], 'pip': [], 'os': [], 'skip': [],
           'apt': [], 'brew': [], 'choco': [], 'vcpkg': [],
           'requirements': ['requirements_optional.txt'],
           'requirements_conda': [], 'requirements_pip': []}
    if fallback_to_conda is None:
        fallback_to_conda = ((method == 'conda')
                             or ((install_opts['os'] == 'win')
                                 and _on_appveyor)
                             or install_opts['lpy'])
    print('ITEMIZE_DEPS', fallback_to_conda)
    if method == 'conda':
        out['default'] = out['conda']
    elif method == 'pip':
        out['default'] = out['pip']
    else:  # pragma: debug
        raise ValueError("Method must be 'conda' or 'pip', not '%s'"
                         % method)
    # In the case of a development environment install requirements that
    # would be missed when installing in development mode
    if for_development:
        if method == 'conda':
            out['requirements'] += ['requirements.txt',
                                    'requirements_condaonly.txt']
        elif method == 'pip':
            # requirements.txt not needed because dev install will
            # pick up and install those deps
            out['requirements'] += ['requirements_piponly.txt']
        out['default'].append('ipython')
        include_dev_deps = True
    if not skip_test_deps:
        out['requirements'].append('requirements_testing.txt')
    if include_dev_deps:
        out['requirements'].append('requirements_development.txt')
    if (method == 'pip') and fallback_to_conda:
        out['requirements_conda'] += ['requirements_condaonly.txt']
    elif (method == 'conda'):
        out['requirements_pip'] += ['requirements.txt',
                                    'requirements_piponly.txt']
    # Required for non-strict channel priority
    # https://github.com/conda-forge/conda-forge.github.io/pull/670
    # https://conda.io/projects/conda/en/latest/user-guide/concepts/ ...
    #    packages.html?highlight=openblas#installing-numpy-with-blas-variants
    # if fallback_to_conda:
    #     conda_pkgs.append("\"blas=*=openblas\"")
    # Installing via pip causes import error on Windows and
    # a conflict when installing LPy
    out['conda'] += ['scipy', os.environ.get('NUMPY', 'numpy')]
    for k in ['matplotlib', 'jsonschema']:
        if os.environ.get(k.upper(), k) != k:
            out['default'].append(os.environ[k.upper()])
    if install_opts['os'] == 'linux':
        out['os'] += ["strace", "valgrind"]
    elif install_opts['os'] == 'osx':
        out['os'] += ["valgrind"]
    if install_opts['omp'] and (not fallback_to_conda):
        if install_opts['os'] == 'linux':
            out['os'].append('libomp-dev')
        elif install_opts['os'] == 'osx':
            out['os'] += ['libomp', 'llvm']
        elif install_opts['os'] == 'win':
            pass
    if install_opts['mpi'] and (not fallback_to_conda):
        if install_opts['os'] == 'linux':
            out['os'] += ['openmpi-bin', 'libopenmpi-dev']
        elif install_opts['os'] == 'osx':
            out['os'].append('open-mpi')
        elif install_opts['os'] == 'win':
            pass
    if install_opts['fortran'] and (not fallback_to_conda):
        # Fortran is not installed via conda on linux/macos
        if install_opts['os'] == 'linux':
            out['os'].append("gfortran")
        elif install_opts['os'] == 'osx':
            out['os'].append("gcc")
            out['os'].append("gfortran")
        elif install_opts['os'] == 'win' and (not fallback_to_conda):
            out['choco'] += ["mingw"]
            # out['vcpkg'].append("vcpkg-gfortran")
    if install_opts['R'] and (not fallback_to_conda):
        # TODO: Test split installation where r-base is installed from
        # conda and the R dependencies are installed from CRAN?
        if install_opts['os'] == 'linux':
            if not shutil.which('R'):
                out['os'] += ["r-base", "r-base-dev"]
            out['os'] += ["libudunits2-dev"]
        elif install_opts['os'] == 'osx':
            if not shutil.which('R'):
                out['os'] += ["r"]
            out['os'] += ["udunits"]
        elif install_opts['os'] == 'win':
            if not shutil.which('R'):
                out['choco'] += [
                    "r.project --params \"\'/AddToPath\'\"",
                    "rtools"]
        else:
            raise NotImplementedError("Could not determine "
                                      "R installation method.")
    if install_opts['zmq'] and (not fallback_to_conda):
        if install_opts['os'] == 'linux':
            out['os'] += ["libczmq-dev", "libzmq3-dev"]
        elif install_opts['os'] == 'osx':
            out['os'] += ["czmq", "zmq"]
        elif install_opts['os'] == 'win':
            out['vcpkg'] += ["czmq", "zeromq"]
        else:
            raise NotImplementedError("Could not determine "
                                      "ZeroMQ installation method.")
    if include_doc_deps or BUILDDOCS:
        out['requirements'].append('requirements_documentation.txt')
        if not fallback_to_conda:
            out['os'].append("doxygen")
    if install_opts['sbml'] and fallback_to_conda:
        # Until the sbml package is updated to allow numpy != 1.19.3,
        # sbml will need to be installed separately without deps in order
        # to work in a conda env
        numpy_ver = 'numpy==1.19.3'
        try:
            new_numpy_ver = get_pip_dependency_version(
                'libroadrunner', 'numpy')
            if new_numpy_ver != numpy_ver:
                warnings.warn(
                    "libroadrunner has updated it's numpy requirement. "
                    "Assuming the new requirement is not strict (%s), "
                    "this code can be removed and libroadrunner can be "
                    "installed normally (numpy should be installed with "
                    "conda if a conda environment is being used to avoid "
                    "inconsistencies)." % new_numpy_ver)
            numpy_ver = new_numpy_ver
        except (ImportError, ModuleNotFoundError):
            pass
        out['conda'].insert(0, numpy_ver.replace('==', '>='))
        out['skip'].append('libroadrunner')
    if install_opts['astropy'] and fallback_to_conda and _on_travis:
        out['conda'].insert(0, 'astropy>=4.1')
    if ((install_opts['fortran'] and fallback_to_conda
         and (_on_travis or (_on_gha and (install_opts['os'] == 'osx'))))):
        out['conda'].append('fortran-compiler')
    if not fallback_to_conda:
        out['default'] += out['conda']
    # Determine package manager based on OS
    if install_opts['os'] == 'linux':
        out['apt'] += out['os']
    elif install_opts['os'] == 'osx':
        out['brew'] += out['os']
    elif install_opts['os'] == 'win':
        if windows_package_manager == 'choco':
            out['choco'] += out['os']
        elif windows_package_manager == 'vcpkg':
            out['vcpkg'] += out['os']
        else:
            raise NotImplementedError("Invalid package manager: '%s'"
                                      % windows_package_manager)
    out.pop('os')
    return out


def install_deps(method, return_commands=False, verbose=False,
                 install_opts=None, conda_env=None,
                 always_yes=False, only_python=False, fallback_to_conda=None, **kwargs):
    r"""Install the package dependencies.
    
    Args:
        method (str): Method that should be used to install the package dependencies.
            Valid values include 'conda' and 'pip'.
        return_commands (bool, optional): If True, the commands necessary to
            install the dependencies are returned instead of running them. Defaults
            to False.
        verbose (bool, optional): If True, setup steps are run with verbosity
            turned up. Defaults to False.
        install_opts (dict, optional): Mapping from language/package to bool
            specifying whether or not the language/package should be installed.
            If not provided, get_install_opts is used to create it.
        conda_env (str, optional): Name of the conda environment that packages
            should be installed in. Defaults to None and is ignored.
        always_yes (bool, optional): If True, conda commands are called with -y flag
            so that user interaction is not required. Defaults to False.
        only_python (bool, optional): If True, only Python packages will be installed.
            Defaults to False.
        fallback_to_conda (bool, optional): If True, conda will be used to install
            non-python dependencies and Python dependencies that cannot be installed
            via pip. Defaults to False.
        **kwargs: Additional keyword arguments are passed to itemize_deps.

    """
    from install_from_requirements import install_from_requirements
    install_opts = get_install_opts(install_opts)
    python_cmd = PYTHON_CMD
    conda_flags = ''
    if conda_env:
        python_cmd = locate_conda_exe(conda_env, 'python')
        conda_flags += ' --name %s' % conda_env
    if always_yes:
        conda_flags += ' -y'
    # Determine if conda should be used for base dependencies
    if fallback_to_conda is None:
        fallback_to_conda = ((method == 'conda')
                             or (_is_win and _on_appveyor)
                             or install_opts['lpy'])
    print('INSTALL_DEPS', method, fallback_to_conda)
    # Get list of packages
    pkgs = itemize_deps(method, fallback_to_conda=fallback_to_conda,
                        install_opts=install_opts, **kwargs)
    pprint.pprint(pkgs)
    # Uninstall default numpy and matplotlib to allow installation
    # of specific versions
    cmds = ["%s -m pip uninstall -y numpy matplotlib" % python_cmd]
    # Refresh channel
    # https://github.com/conda/conda/issues/8051
    if fallback_to_conda and _on_gha:
        cmds += [
            "%s config --set channel_priority strict" % CONDA_CMD,
            # "%s install -n root conda=4.9" % CONDA_CMD,
            # "%s config --set allow_conda_downgrades true" % CONDA_CMD,
            "%s config --remove channels conda-forge" % CONDA_CMD,
            "%s config --add channels conda-forge" % CONDA_CMD,
        ]
    if fallback_to_conda:
        cmds.append("%s update --all" % CONDA_CMD)
    if install_opts['R'] and (not fallback_to_conda):
        # TODO: Test split installation where r-base is installed from
        # conda and the R dependencies are installed from CRAN?
        if _is_linux:
            cmds += [
                ("sudo add-apt-repository 'deb https://cloud"
                 ".r-project.org/bin/linux/ubuntu xenial-cran35/'"),
                ("sudo apt-key adv --keyserver keyserver.ubuntu.com "
                 "--recv-keys E298A3A825C0D65DFD57CBB651716619E084DAB9")]
    # if install_opts['zmq'] and (not fallback_to_conda):
    #     cmds.append("echo Installing ZeroMQ...")
    #     if _is_linux:
    #         cmds.append("./ci/install-czmq-linux.sh")
    #     elif _is_osx:
    #         cmds.append("bash ci/install-czmq-osx.sh")
    #     # elif _is_win:
    #     #     cmds += ["call ci\\install-czmq-windows.bat",
    #     #              "echo \"%PATH%\""]
    #     else:
    #         raise NotImplementedError("Could not determine "
    #                                   "ZeroMQ installation method.")
    if _on_gha and _is_linux and fallback_to_conda:
        conda_prefix = '$CONDA_PREFIX'
        if conda_env:
            conda_prefix = os.path.join(CONDA_ROOT, 'envs', conda_env)
        # Do both to ensure that the path is set for the installation
        # and in following steps
        cmds += [
            "export LD_LIBRARY_PATH=%s/lib:$LD_LIBRARY_PATH" % conda_prefix,
            "echo -n \"LD_LIBRARY_PATH=\" >> $GITHUB_ENV",
            "echo %s/lib:$LD_LIBRARY_PATH >> $GITHUB_ENV" % conda_prefix
        ]
    # Install dependencies using package manager(s)
    if not only_python:
        if pkgs['apt']:
            cmds += ["sudo apt update"]
            cmds += ["sudo apt-get install %s" % ' '.join(pkgs['apt'])]
        if pkgs['brew']:
            if 'gcc' in pkgs['brew']:
                cmds += ["brew reinstall gcc"]
                pkgs['brew'].remove('gcc')
            if 'valgrind' in pkgs['brew']:
                # There seems to be a bug with this installation on GHA
                # cmds += ["brew tap LouisBrunner/valgrind",
                #          "brew install --HEAD LouisBrunner/valgrind/valgrind"]
                pkgs['brew'].remove('valgrind')
            pkgs_from_src = []
            if _on_travis:
                for k in ['zmq', 'czmq', 'zeromq']:
                    if k in pkgs['brew']:
                        pkgs_from_src.append(k)
                        pkgs['brew'].remove(k)
            if pkgs_from_src:
                cmds += ["brew install --build-from-source %s" % ' '.join(pkgs_from_src)]
            if pkgs['brew']:
                cmds += ["brew install %s" % ' '.join(pkgs['brew'])]
        if pkgs['choco']:
            # cmds += ["choco install %s" % ' '.join(pkgs['choco'])]
            for x in pkgs['choco']:
                cmds.append("choco install %s --force" % x)
        if pkgs['vcpkg']:
            cmds += ["%s install %s --triplet x64-windows"
                     % ('vcpkg.exe', ' '.join(pkgs['vcpkg']))]
    # Install via requirements
    req_kwargs = dict(conda_env=conda_env, python_cmd=python_cmd,
                      install_opts=install_opts, append_cmds=cmds,
                      skip_packages=pkgs['skip'], verbose=verbose,
                      verbose_prune=True)
    install_from_requirements(method, pkgs['requirements'],
                              additional_packages=pkgs['default'],
                              **req_kwargs)
    pkgs.pop(method, None)  # Remove so that they are not installed twice
    if fallback_to_conda:
        install_from_requirements('conda', pkgs['requirements_conda'],
                                  additional_packages=pkgs.get('conda', []),
                                  unique_to_method=True, **req_kwargs)
    install_from_requirements('pip', pkgs['requirements_pip'],
                              additional_packages=pkgs.get('pip', []),
                              unique_to_method=True, **req_kwargs)
    if 'libroadrunner' in pkgs['skip']:
        pip_flags = '--no-dependencies'
        if verbose:
            pip_flags += ' --verbose'
        cmds.append('%s -m pip install %s libroadrunner'
                    % (python_cmd, pip_flags))
    if install_opts['lpy']:
        if verbose:
            install_flags = '-vvv'
        else:
            install_flags = '-q'
        install_flags += conda_flags
        if fallback_to_conda:
            cmds += ["%s install %s openalea.lpy boost=1.66.0 -c openalea"
                     % (CONDA_CMD, install_flags)]
        else:  # pragma: debug
            raise RuntimeError("Could not detect conda environment. "
                               "Cannot proceed with a conda deployment "
                               "(required for LPy).")
    if return_commands:
        return cmds
    cmds = SUMMARY_CMDS + cmds + SUMMARY_CMDS
    call_script(cmds)


def install_pkg(method, python=None, without_build=False,
                without_deps=False, verbose=False,
                skip_test_deps=False, include_dev_deps=False, include_doc_deps=False,
                windows_package_manager='vcpkg', install_opts=None, conda_env=None,
                always_yes=False, only_python=False, fallback_to_conda=None):
    r"""Build and install the package and its dependencies on a CI
    resource.

    Args:
        method (str): Method that should be used to build and install
            the package. Valid values include 'conda' and 'pip'.
        python (str, optional): Version of Python that package should be
            built for. Defaults to None if not provided and the current
            version of Python will be used. This will be ignored if
            without_build is True.
        without_build (bool, optional): If True, the package will not be
            built prior to install. Defaults to False.
        without_deps (bool, optional): If True the package dependencies will
            no be installed prior to installing the package. Defaults to
            False.
        verbose (bool, optional): If True, setup steps are run with verbosity
            turned up. Defaults to False.
        skip_test_deps (bool, optional): If True, dependencies required for running
            tests will not be installed. Defaults to False.
        include_dev_deps (bool, optional): If True, dependencies used during development
            will be installed. Defaults to False.
        include_doc_deps (bool, optional): If True, dependencies used during generating
            documentation will be installed. Defaults to False.
        windows_package_manager (str, optional): Name of the package
            manager that should be used on windows. Defaults to 'vcpkg'.
        install_opts (dict, optional): Mapping from language/package to bool
            specifying whether or not the language/package should be installed.
            If not provided, get_install_opts is used to create it.
        conda_env (str, optional): Name of the conda environment that packages
            should be installed in. Defaults to None and is ignored.
        always_yes (bool, optional): If True, conda commands are called with -y flag
            so that user interaction is not required. Defaults to False.
        only_python (bool, optional): If True, only Python packages will be installed.
            Defaults to False.
        fallback_to_conda (bool, optional): If True, conda will be used to install
            non-python dependencies and Python dependencies that cannot be installed
            via pip. Defaults to False.

    Raises:
        ValueError: If method is not 'conda' or 'pip'.

    """
    install_opts = get_install_opts(install_opts)
    python_cmd = PYTHON_CMD
    conda_flags = ''
    if conda_env:
        python_cmd = locate_conda_exe(conda_env, 'python')
        conda_flags += ' --name %s' % conda_env
    if always_yes:
        conda_flags += ' -y'
    cmds = []
    if method.endswith('-dev'):
        method_base = method.split('-dev')[0]
        for_development = True
        without_build = True
    else:
        method_base = method
        for_development = False
    if not without_build:
        cmds += build_pkg(method_base, python=python,
                          return_commands=True, verbose=verbose)
        cmds += SUMMARY_CMDS
    if not without_deps:
        cmds += install_deps(method_base, return_commands=True, verbose=verbose,
                             for_development=for_development,
                             skip_test_deps=skip_test_deps,
                             include_dev_deps=include_dev_deps,
                             include_doc_deps=include_doc_deps,
                             install_opts=install_opts,
                             windows_package_manager=windows_package_manager,
                             conda_env=conda_env, always_yes=always_yes,
                             only_python=only_python,
                             fallback_to_conda=fallback_to_conda)
        cmds += SUMMARY_CMDS
    # Install yggdrasil
    if method == 'conda':
        assert(CONDA_INDEX and os.path.isdir(CONDA_INDEX))
        # Install from conda build
        # Assumes that the target environment is active
        if verbose:
            install_flags = '-vvv'
        else:
            install_flags = '-q'
        install_flags += conda_flags
        if _is_win:
            index_channel = CONDA_INDEX
        else:
            index_channel = "file:/%s" % CONDA_INDEX
        cmds += [
            # Related issues if this stops working again
            # https://github.com/conda/conda/issues/466#issuecomment-378050252
            "%s install %s --update-deps -c %s yggdrasil" % (
                CONDA_CMD, install_flags, index_channel)
            # Required for non-strict channel priority
            # https://github.com/conda-forge/conda-forge.github.io/pull/670
            # https://conda.io/projects/conda/en/latest/user-guide/concepts/ ...
            #    packages.html?highlight=openblas#installing-numpy-with-blas-variants
            # "%s install %s --update-deps -c %s yggdrasil \"blas=*=openblas\"" % (
            #     CONDA_CMD, install_flags, index_channel)
        ]
    elif method == 'pip':
        if verbose:
            install_flags = '--verbose'
        else:
            install_flags = ''
        if _is_win:  # pragma: windows
            cmds += [
                "for %%a in (\"dist\\*.tar.gz\") do set YGGSDIST=%%a",
                "echo %YGGSDIST%"
            ]
            sdist = "%YGGSDIST%"
        else:
            sdist = "dist/*.tar.gz"
        cmds += [
            "%s -m pip install %s %s" % (python_cmd, install_flags, sdist),
            "%s create_coveragerc.py" % python_cmd
        ]
    elif method.endswith('-dev'):
        # Call setup.py in separate process from the package directory
        # cmds += ["%s setup.py develop" % python_cmd]
        pass
    else:  # pragma: debug
        raise ValueError("Invalid method: '%s'" % method)
    # Print summary of what was installed
    cmds = SUMMARY_CMDS + cmds + SUMMARY_CMDS
    call_script(cmds)
    if method.endswith('-dev'):
        print(call_conda_command([python_cmd, '-m', 'pip', 'install',
                                  '--editable', '.'],
                                 cwd=_pkg_dir))
    # Follow up if on Unix as R installation may require sudo
    if install_opts['R'] and _is_unix:
        # cmds.append('ygginstall r --sudoR')
        subprocess.check_call(["ygginstall", "r", "--sudoR"])
    if method == 'conda':
        src_dir = os.path.join(os.getcwd(),
                               os.path.dirname(os.path.dirname(__file__)))
        subprocess.check_call([python_cmd, "create_coveragerc.py"], cwd=src_dir)


def verify_pkg(install_opts=None):
    r"""Verify that the package was installed correctly.

    Args:
        install_opts (dict, optional): Mapping from language/package to bool
            specifying whether or not the language/package should be installed.
            If not provided, get_install_opts is used to create it.

    """
    install_opts = get_install_opts(install_opts)
    if _is_win and (not install_opts['zmq']):
        install_opts['c'] = False
        install_opts['fortran'] = False
    elif (not install_opts['fortran']) and shutil.which('gfortran'):
        install_opts['fortran'] = True
    if (not install_opts['R']) and shutil.which('Rscript'):
        if not (_on_gha and (_is_linux or _is_win)):
            # The installation on GHA-ubuntu machines requires sudo
            # and so installation will not be complete unless it is
            # enabled explicitly. This does not seem to be True on
            # GHA-macos builds and R is not installed by default on
            # Travis/Appveyor.
            install_opts['R'] = True
    if (not install_opts['c']) and shutil.which('gcc') and (not _is_win):
        install_opts['c'] = True
    src_dir = os.path.join(os.getcwd(),
                           os.path.dirname(os.path.dirname(__file__)))
    src_version = subprocess.check_output(
        ["python", "-c",
         "'import versioneer; print(versioneer.get_version())'"],
        cwd=src_dir)
    bld_version = subprocess.check_output(
        ["python", "-c",
         "'import yggdrasil; print(yggdrasil.__version__)'"],
        cwd=os.path.dirname(src_dir))
    if src_version != bld_version:
        raise RuntimeError("Installed version does not match the version of "
                           "this source code.\n"
                           "\tSource version: %s\n\tBuild  version: %s"
                           % (src_version, bld_version))
    if install_opts['R']:
        assert(shutil.which("R"))
        assert(shutil.which("Rscript"))
    subprocess.check_call(["flake8", "yggdrasil"], cwd=src_dir)
    if not os.path.isfile(".coveragerc"):
        raise RuntimeError(".coveragerc file dosn't exist.")
    with open(".coveragerc", "r") as fd:
        print(fd.read())
    subprocess.check_call(["ygginfo", "--verbose"], cwd=src_dir)
    if install_opts['c']:
        subprocess.check_call(["yggccflags"], cwd=src_dir)
        subprocess.check_call(["yggldflags"], cwd=src_dir)
    # Verify that languages are installed
    sys.stdout.flush()
    from yggdrasil.tools import is_lang_installed, is_comm_installed
    errors = []
    for name in ['c', 'R', 'fortran', 'sbml', 'lpy']:
        flag = install_opts[name]
        if flag and (not is_lang_installed(name)):
            errors.append("Language '%s' should be installed, but is not."
                          % name)
        elif (not flag) and is_lang_installed(name):
            errors.append("Language '%s' should NOT be installed, but is."
                          % name)
    for name in ['zmq', 'rmq']:
        flag = install_opts[name]
        if name == 'rmq':
            language = 'python'  # rmq dosn't work for C
        else:
            language = None
        if flag and (not is_comm_installed(name, language=language)):
            errors.append("Comm '%s' should be installed, but is not." % name)
        elif (not flag) and is_comm_installed(name, language=language):
            errors.append("Comm '%s' should NOT be installed, but is." % name)
    if errors:
        raise AssertionError("One or more languages was not installed as "
                             "expected\n\t%s" % "\n\t".join(errors))
    if _is_win:  # pragma: windows
        if os.environ.get('HOMEDRIVE', None):
            assert(os.path.expanduser('~').startswith(os.environ['HOMEDRIVE']))
        else:
            assert(os.path.expanduser('~').lower().startswith('c:'))


def log_environment(new_filename='new_environment_log.txt',
                    old_filename='old_environment_log.txt'):
    r"""Create a record of the Python package versions.

    Args:
        new_filename (str, optional): Name of the file where the
            environment information should be stored. Defaults to
            'new_environment_log.txt'.
        old_filename (str, optional): Name of the file where previous
            environment information is stored for diff. Defaults to
            'old_environment_log.txt'.

    """
    if os.path.isfile(new_filename):
        if os.path.isfile(old_filename):
            raise RuntimeError("Package list already exists: '%s'"
                               % new_filename)
        else:
            shutil.move(new_filename, old_filename)
    now = datetime.now()
    cmds = ["echo \"%s\" >> %s" % (now.strftime("%Y/%m/%d %H:%M:%S"),
                                   new_filename),
            "%s --version >> %s" % (PYTHON_CMD, new_filename),
            "%s -m pip list >> %s" % (PYTHON_CMD, new_filename)]
    if shutil.which('conda'):
        cmds.append("%s list >> %s" % (CONDA_CMD, new_filename))
    call_script(cmds)
    assert(os.path.isfile(new_filename))
    if os.path.isfile(old_filename):
        with open(new_filename, 'r') as fd:
            new_contents = fd.read()
        with open(old_filename, 'r') as fd:
            old_contents = fd.read()
        diff = difflib.ndiff(old_contents.splitlines(),
                             new_contents.splitlines())
        print('\n'.join(diff))


if __name__ == "__main__":
    install_opts = get_install_opts()
    parser = argparse.ArgumentParser(
        "Perform setup operations to test package build and "
        "installation on continuous integration services.")
    subparsers = parser.add_subparsers(
        dest='operation',
        help="CI setup operation that should be performed.")
    # Environment creation
    parser_env = subparsers.add_parser(
        'env', help="Setup an environment for testing.")
    parser_env.add_argument(
        'method', choices=['conda', 'virtualenv'],
        help=("Method that should be used to create "
              "the test environment."))
    parser_env.add_argument(
        'python',
        help="Version of python that should be tested.")
    parser_env.add_argument(
        '--env-name', default=None,
        help="Name that should be used for the environment.")
    # Build package
    parser_bld = subparsers.add_parser(
        'build', help="Build the package.")
    parser_bld.add_argument(
        'method', choices=['conda', 'pip'],
        help=("Method that should be used to build the package."))
    parser_bld.add_argument(
        '--python', default=None,
        help="Version of python that package should be built for.")
    parser_bld.add_argument(
        '--verbose', action='store_true',
        help="Turn up verbosity of output.")
    # Install dependencies
    parser_dep = subparsers.add_parser(
        'deps', help="Install the package dependencies.")
    parser_dep.add_argument(
        'method', choices=['conda', 'pip'],
        help=("Method that should be used to install the package dependencies."))
    parser_dep.add_argument(
        '--verbose', action='store_true',
        help="Turn up verbosity of output.")
    parser_dep.add_argument(
        '--for-development', action='store_true',
        help=("Install dependencies used during development and "
              "that would be missed when installing in development mode. "
              "Implies --include-dev-deps"))
    parser_dep.add_argument(
        '--skip-test-deps', action='store_true',
        help="Don't install dependencies used for testing.")
    parser_dep.add_argument(
        '--include-dev-deps', action='store_true',
        help="Install dependencies used during development.")
    parser_dep.add_argument(
        '--include-doc-deps', action='store_true',
        help="Install dependencies used during doc generation.")
    parser_dep.add_argument(
        '--windows-package-manager', default='vcpkg',
        help="Package manager that should be used on Windows.",
        choices=['vcpkg', 'choco'])
    parser_dep.add_argument(
        '--conda-env', default=None,
        help="Conda environment that dependencies should be installed in.")
    parser_dep.add_argument(
        '--always-yes', action='store_true',
        help="Pass -y to conda commands to avoid user interaction.")
    parser_dep.add_argument(
        '--only-python', '--python-only', action='store_true',
        help="Only install python dependencies.")
    add_install_opts_args(parser_dep)
    # Install package
    parser_pkg = subparsers.add_parser(
        'install', help="Install the package.")
    parser_pkg.add_argument(
        'method', choices=['conda', 'pip', 'conda-dev', 'pip-dev'],
        help=("Method that should be used to install the package."))
    parser_pkg.add_argument(
        '--python', default=None,
        help="Version of python that package should be built/installed for.")
    parser_pkg.add_argument(
        '--without-build', action='store_true',
        help=("Perform installation steps without building first. (Assumes "
              "the package has already been built)."))
    parser_pkg.add_argument(
        '--without-deps', action='store_true',
        help=("Perform installation steps without installing dependencies first. "
              "(Assumes they have already been installed)."))
    parser_pkg.add_argument(
        '--verbose', action='store_true',
        help="Turn up verbosity of output.")
    parser_pkg.add_argument(
        '--skip-test-deps', action='store_true',
        help="Don't install dependencies used for testing.")
    parser_pkg.add_argument(
        '--include-dev-deps', action='store_true',
        help="Install dependencies used during development.")
    parser_pkg.add_argument(
        '--include-doc-deps', action='store_true',
        help="Install dependencies used during doc generation.")
    parser_pkg.add_argument(
        '--windows-package-manager', default='vcpkg',
        help="Package manager that should be used on Windows.",
        choices=['vcpkg', 'choco'])
    parser_pkg.add_argument(
        '--conda-env', default=None,
        help="Conda environment that the package should be installed in.")
    parser_pkg.add_argument(
        '--always-yes', action='store_true',
        help="Pass -y to conda commands to avoid user interaction.")
    parser_pkg.add_argument(
        '--only-python', '--python-only', action='store_true',
        help="Only install python dependencies.")
    add_install_opts_args(parser_pkg)
    # Installation verification
    parser_ver = subparsers.add_parser(
        'verify', help="Verify that the package was installed correctly.")
    add_install_opts_args(parser_ver)
    # Environment logging
    parser_log = subparsers.add_parser(
        'log', help="Create a log of the Python environment.")
    parser_log.add_argument(
        '--new-filename', default='new_environment_log.txt',
        help="File where the new environment log should be saved.")
    parser_log.add_argument(
        '--old-filename', default='old_environment_log.txt',
        help=("File containing previous environment log that the new "
              "log should be diffed against."))
    # Create environment.yml
    parser_yml = subparsers.add_parser(
        'env-yaml', help="Create an environment.yml file.")
    parser_yml.add_argument(
        '--filename', default='environment.yml',
        help="File where the environment yaml should be saved.")
    parser_yml.add_argument(
        '--name', '-n', default='ygg',
        help="Name of environment.")
    parser_yml.add_argument(
        '--channels', '--channel', '-c', nargs='*',
        help="Name of conda channels that should be used.")
    parser_yml.add_argument(
        '--for-development', action='store_true',
        help=("Install dependencies used during development and "
              "that would be missed when installing in development mode. "
              "Implies --include-dev-deps"))
    parser_yml.add_argument(
        '--skip-test-deps', action='store_true',
        help="Don't install dependencies used for testing.")
    parser_yml.add_argument(
        '--include-dev-deps', action='store_true',
        help="Install dependencies used during development.")
    parser_yml.add_argument(
        '--include-doc-deps', action='store_true',
        help="Install dependencies used during doc generation.")
    parser_yml.add_argument(
        '--target-os', choices=['win', 'osx', 'linux'],
        help=("Operating system that environment should target if "
              "different from the current OS."))
    parser_yml.add_argument(
        '--python-version', '--python', type=str,
        help="Python version that environment should use.")
    add_install_opts_args(parser_yml)
    # Call methods
    args = parser.parse_args()
    if args.operation in ['deps', 'install', 'verify', 'env-yaml']:
        new_opts = {}
        for k, v in install_opts.items():
            if v and getattr(args, 'dont_install_%s' % k, False):
                new_opts[k] = False
            elif (not v) and getattr(args, 'install_%s' % k, False):
                new_opts[k] = True
        install_opts.update(new_opts)
    if args.operation in ['env', 'setup']:
        create_env(args.method, args.python, name=args.env_name)
    elif args.operation == 'build':
        build_pkg(args.method, python=args.python,
                  verbose=args.verbose)
    elif args.operation == 'deps':
        install_deps(args.method, verbose=args.verbose,
                     skip_test_deps=args.skip_test_deps,
                     include_dev_deps=args.include_dev_deps,
                     include_doc_deps=args.include_doc_deps,
                     for_development=args.for_development,
                     windows_package_manager=args.windows_package_manager,
                     install_opts=install_opts,
                     conda_env=args.conda_env, always_yes=args.always_yes,
                     only_python=args.only_python)
    elif args.operation == 'install':
        install_pkg(args.method, python=args.python,
                    without_build=args.without_build,
                    without_deps=args.without_deps,
                    verbose=args.verbose,
                    skip_test_deps=args.skip_test_deps,
                    include_dev_deps=args.include_dev_deps,
                    include_doc_deps=args.include_doc_deps,
                    windows_package_manager=args.windows_package_manager,
                    install_opts=install_opts,
                    conda_env=args.conda_env, always_yes=args.always_yes,
                    only_python=args.only_python)
    elif args.operation == 'verify':
        verify_pkg(install_opts=install_opts)
    elif args.operation == 'log':
        log_environment(new_filename=args.new_filename,
                        old_filename=args.old_filename)
    elif args.operation == 'env-yaml':
        install_opts['os'] = args.target_os
        create_env_yaml(filename=args.filename, name=args.name,
                        channels=args.channels, target_os=args.target_os,
                        python_version=args.python_version,
                        for_development=args.for_development,
                        skip_test_deps=args.skip_test_deps,
                        include_dev_deps=args.include_dev_deps,
                        include_doc_deps=args.include_doc_deps,
                        install_opts=install_opts)
