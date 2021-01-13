# https://www.python.org/dev/peps/pep-0508/
from pip._vendor.packaging.requirements import Requirement, InvalidRequirement
import os
import re
import uuid
import pprint
import argparse
from setup_test_env import (
    call_conda_command, locate_conda_exe, get_install_opts,
    PYTHON_CMD, CONDA_CMD, _is_win)


def prune(fname_in, fname_out=None, excl_method=None, incl_method=None,
          install_opts=None, additional_packages=[], verbose=False):
    r"""Prune a requirements.txt file to remove/select dependencies that are
    dependent on the current environment.

    Args:
        fname_in (str, list): Full path to one or more requirements files that
            should be read.
        fname_out (str, optional): Full path to requirements file that should be
            created. Defaults to None and is set to <fname_in[0]>_pruned.txt.
        excl_method (str, optional): Installation method (pip or conda) that
            should be ignored. Defaults to None and is ignored.
        incl_method (str, optional): Installation method (pip or conda) that
            should be installed (requirements with without an installation method
            or with a different method will be ignored). Defaults to None and is
            ignored.
        install_opts (dict, optional): Mapping from language/package to bool
            specifying whether or not the language/package should be installed.
            If not provided, get_install_opts is used to create it.
        additional_packages (list, optional): Additional packages that should
            be installed. Defaults to empty list.
        verbose (bool, optional): If True, setup steps are run with verbosity
            turned up. Defaults to False.

    Returns:
        str: Full path to created file.

    """
    verbose = True
    regex_constrain = r'(?:pip)|(?:conda)|(?:[a-zA-Z][a-zA-Z0-9]*)'
    regex_comment = r'\s*\[\s*(?P<vals>%s(?:\s*\,\s*%s)*)\s*\]\s*' % (
        regex_constrain, regex_constrain)
    # regex_elem = r'(?P<val>%s)\s*(?:(?:\,)|(?:\]))' % regex_constrain
    install_opts = get_install_opts(install_opts)
    if not isinstance(fname_in, (list, tuple)):
        fname_in = [fname_in]
    new_lines = []
    orig_lines = []
    for ifname_in in fname_in:
        with open(ifname_in, 'r') as fd:
            old_lines = fd.readlines()
            orig_lines += old_lines
        for line in old_lines:
            line = line.strip()
            if line.startswith('#'):
                continue
            skip_line = False
            req_name = line
            if '#' in line:
                req_name, comment = line.split('#')
                m = re.fullmatch(regex_comment, comment)
                if m:
                    values = [x.strip() for x in m.group('vals').split(',')]
                    if excl_method and (excl_method in values):
                        continue
                    if incl_method and (incl_method not in values):
                        continue
                    for v in values:
                        if v not in ['pip', 'conda']:
                            if v not in install_opts:
                                raise RuntimeError("Unsupported install opt: '%s'" % v)
                            if not install_opts[v]:
                                skip_line = True
                                break
                elif incl_method:
                    skip_line = True
            elif incl_method:
                skip_line = True
            if skip_line:
                continue
            try:
                req = Requirement(req_name.strip())
                if req.marker and (not req.marker.evaluate()):
                    continue
                new_lines.append(req.name + str(req.specifier))
            except InvalidRequirement as e:
                print(e)
                continue
    orig_lines += additional_packages
    new_lines += additional_packages
    # Write file
    if fname_out is None:
        fname_out = ('_pruned%s' % str(uuid.uuid4())).join(os.path.splitext(fname_in[0]))
    with open(fname_out, 'w') as fd:
        fd.write('\n'.join(new_lines))
    if verbose:
        print('INSTALL OPTS:\n%s' % pprint.pformat(install_opts))
        print('ORIGINAL DEP LIST:\n\t%s\nPRUNED DEP LIST:\n\t%s'
              % ('\n\t'.join([x.strip() for x in orig_lines]),
                 '\n\t'.join(new_lines)))
    return fname_out


def install_from_requirements(method, fname_in, conda_env=None,
                              user=False, unique_to_method=False,
                              python_cmd=None, install_opts=None,
                              verbose=False, additional_packages=[],
                              return_cmds=False, append_cmds=None,
                              temp_file=None):
    r"""Install packages via pip or conda from one or more pip-style
    requirements file(s).

    Args:
        method (str): Installation method; either 'pip' or 'conda'.
        fname_in (str, list): Full path to one or more requirements files that
            should be read.
        conda_env (str, optional): Name of conda environment that requirements
            should be installed into. Defaults to None and is ignored.
        user (bool, optional): If True, install in user mode. Defaults to
            False.
        unique_to_method (bool, optional): If True, only those packages that
            can only be installed via the specified method will be installed.
        install_opts (dict, optional): Mapping from language/package to bool
            specifying whether or not the language/package should be installed.
            If not provided, get_install_opts is used to create it.
        python_cmd (str, optional): Python executable that should be used to
            call pip. Defaults to None and will be determined from conda_env if
            provided. Otherwise the current executable will be used.
        verbose (bool, optional): If True, setup steps are run with verbosity
            turned up. Defaults to False.
        additional_packages (list, optional): Additional packages that should
            be installed. Defaults to empty list.
        return_cmds (bool, optional): If True, the necessary commands will be
            returned. Defaults to False.
        append_cmds (list, optional): List that commands should be appended to.
            Defaults to None and is ignored. If provided, the temporary file
            is returned. This keyword will be ignored if return_cmds is True.
        temp_file (str, optional): File where pruned requirements list should
            be stored. Defaults to None and one will be created.

    """
    return_temp = (return_cmds or isinstance(append_cmds, list))
    install_opts = get_install_opts(install_opts)
    if python_cmd is None:
        python_cmd = PYTHON_CMD
    if conda_env:
        python_cmd = locate_conda_exe(conda_env, 'python')
    if method == 'pip':
        excl_method = 'conda'
    elif method == 'conda':
        excl_method = 'pip'
    else:
        raise ValueError("Invalid method: '%s'" % method)
    if unique_to_method:
        incl_method = method
    else:
        incl_method = None
    temp_file = prune(fname_in, fname_out=temp_file,
                      excl_method=excl_method, incl_method=incl_method,
                      install_opts=install_opts, verbose=verbose,
                      additional_packages=additional_packages)
    try:
        if method == 'conda':
            args = [CONDA_CMD, 'install', '-y']
            if verbose:
                args.append('-vvv')
            else:
                args.append('-q')
            if conda_env:
                args += ['--name', conda_env]
            args += ['--file', temp_file]
            if user:
                args.append('--user')
            args.append('--update-all')
        elif method == 'pip':
            args = [python_cmd, '-m', 'pip', 'install']
            if verbose:
                args.append('--verbose')
            args += ['-r', temp_file]
            if user:
                args.append('--user')
        if return_temp:
            if return_cmds:
                cmd_list = []
            else:
                cmd_list = append_cmds
            cmd_list += [' '.join(args)]
            if _is_win:
                cmd_list.append(
                    ('%s -c \'exec(\"import os;if os.path.isfile'
                     '(\\"%s\\"): os.remove(\\"%s\\")\")\'')
                    % (python_cmd, temp_file, temp_file))
            else:
                cmd_list.append(
                    ('%s -c \'import os\nif os.path.isfile'
                     '(\"%s\"): os.remove(\"%s\")\'')
                    % (python_cmd, temp_file, temp_file))
        if return_cmds:
            return cmd_list
        if isinstance(append_cmds, list):
            return temp_file
        print(call_conda_command(args))
    except BaseException:
        if os.path.isfile(temp_file):
            with open(temp_file, 'r') as fd:
                print(fd.read())
        raise
    finally:
        if os.path.isfile(temp_file) and (not return_temp):
            os.remove(temp_file)


if __name__ == "__main__":
    install_opts = get_install_opts()
    parser = argparse.ArgumentParser(
        "Install dependencies via pip or conda from one or more "
        "pip-style requirements files.")
    parser.add_argument('method', choices=['conda', 'pip'],
                        help=("Method that should be used to install the "
                              "dependencies."))
    parser.add_argument('files', nargs='+',
                        help='One or more pip-style requirements files.')
    parser.add_argument('--conda-env', default=None,
                        help=('Conda environment that requirements should be '
                              'installed into.'))
    parser.add_argument('--user', action='store_true',
                        help=('Install in user mode.'))
    parser.add_argument('--unique-to-method', action='store_true',
                        help=('Only install packages that are unique to the specified '
                              'installation method.'))
    parser.add_argument('--verbose', action='store_true',
                        help="Turn up verbosity of output.")
    parser.add_argument('--additional-packages', nargs='+',
                        help="Additional packages that should be installed.")
    for k, v in install_opts.items():
        if v:
            parser.add_argument(
                '--dont-install-%s' % k, action='store_true',
                help=("Don't install %s" % k))
        else:
            parser.add_argument(
                '--install-%s' % k, action='store_true',
                help=("Install %s" % k))
    args = parser.parse_args()
    new_opts = {}
    for k, v in install_opts.items():
        if v and getattr(args, 'dont_install_%s' % k, False):
            new_opts[k] = False
        elif (not v) and getattr(args, 'install_%s' % k, False):
            new_opts[k] = True
    install_opts.update(new_opts)
    install_from_requirements(args.method, args.files, conda_env=args.conda_env,
                              user=args.user, unique_to_method=args.unique_to_method,
                              install_opts=install_opts, verbose=args.verbose,
                              additional_packages=args.additional_packages)
