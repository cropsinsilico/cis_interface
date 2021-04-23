import os
import sys
import importlib
from yggdrasil import tools
from yggdrasil.drivers.InterpretedModelDriver import InterpretedModelDriver


class PythonModelDriver(InterpretedModelDriver):
    r"""Class for running Python models."""

    _schema_subtype_description = ('Model is written in Python.')
    language = 'python'
    language_ext = '.py'
    default_interpreter = sys.executable
    interface_library = 'yggdrasil.interface.YggInterface'
    # supported_comms = ['ipc', 'zmq', 'rmq']
    supported_comm_options = {
        'ipc': {'platforms': ['MacOS', 'Linux'],
                'libraries': ['sysv_ipc']},
        'zmq': {'libraries': ['zmq']},
        'rmq': {'libraries': ['pika']},
        'mpi': {'libraries': ['mpi4py']}}
    type_map = {
        'int': 'numpy.intX',
        'float': 'numpy.floatX',
        'string': 'str',
        'array': 'list',
        'object': 'dict',
        'boolean': 'bool',
        'null': 'None',
        'uint': 'numpy.uintX',
        'complex': 'numpy.complexX',
        'bytes': 'bytes',
        'unicode': 'str',
        '1darray': 'numpy.ndarray',
        'ndarray': 'numpy.ndarray',
        'ply': 'PlyDict',
        'obj': 'ObjDict',
        'schema': 'dict'}
    function_param = {
        'import_nofile': 'import {function}',
        'import': 'from {filename} import {function}',
        'istype': 'isinstance({variable}, {type})',
        'len': 'len({variable})',
        'index': '{variable}[{index}]',
        'interface': 'import {interface_library} as ygg',
        'input': '{channel} = ygg.YggInput(\'{channel_name}\')',
        'output': '{channel} = ygg.YggOutput(\'{channel_name}\')',
        'python_interface': '{channel} = ygg.{python_interface}(\'{channel_name}\')',
        'python_interface_format': ('{channel} = ygg.{python_interface}'
                                    '(\'{channel_name}\', \'{format_str}\')'),
        'recv_function': '{channel}.recv',
        'send_function': '{channel}.send',
        'multiple_outputs': '[{outputs}]',
        'comment': '#',
        'true': 'True',
        'false': 'False',
        'not': 'not',
        'and': 'and',
        'indent': 4 * ' ',
        'quote': '\"',
        'print_generic': ('from yggdrasil.tools import print_encoded; '
                          'print_encoded({object})'),
        'print': 'print(\"{message}\")',
        'fprintf': 'print(\"{message}\" % ({variables}))',
        'error': 'raise Exception("{error_msg}")',
        'block_end': '',
        'if_begin': 'if ({cond}):',
        'if_elif': 'elif ({cond}):',
        'if_else': 'else:',
        'for_begin': 'for {iter_var} in range({iter_begin}, {iter_end}):',
        'while_begin': 'while ({cond}):',
        'break': 'break',
        'try_begin': 'try:',
        'try_error_type': 'BaseException',
        'try_except': 'except {error_type} as {error_var}:',
        'assign': '{name} = {value}',
        'exec_begin': 'def main():',
        'exec_suffix': ('if __name__ == "__main__":\n'
                        '    main()'),
        'function_def_begin': 'def {function_name}({input_var}):',
        'return': 'return {output_var}',
        'function_def_regex': (
            r'\n?( *)def +{function_name}'
            r' *\((?P<inputs>(?:.|\n)*?)\)? *:'
            r'(?P<body>(?:\1(?:    )+(?!return).*\n)|(?: *\n))*'
            r'(?:\1(?:    )+'
            r'return *(?P<outputs>.*)?)?'),
        'inputs_def_regex': r'\s*(?P<name>.+?)\s*(?:,|$)',
        'outputs_def_regex': r'\s*(?P<name>.+?)\s*(?:,|$)'}

    @staticmethod
    def finalize_registration(cls):
        r"""Operations that should be performed after a class has been fully
        initialized and registered."""
        cls.supported_comms = tools.get_supported_comm()
        InterpretedModelDriver.finalize_registration(cls)
        
    def set_env(self, **kwargs):
        r"""Get environment variables that should be set for the model process.

        Args:
            **kwargs: Additional keyword arguments are passed to the parent class's
                method.

        Returns:
            dict: Environment variables for the model process.

        """
        out = super(PythonModelDriver, self).set_env(**kwargs)
        if self.with_valgrind:
            out['PYTHONMALLOC'] = 'malloc'
        return out
        
    @classmethod
    def is_language_installed(self):
        r"""Determine if this model driver is installed on the current
        machine.

        Returns:
            bool: Truth of if this model driver can be run on the current
                machine.

        """
        # This is being run so python exists
        return True

    @classmethod
    def is_library_installed(cls, lib, **kwargs):
        r"""Determine if a dependency is installed.

        Args:
            lib (str): Name of the library that should be checked.
            **kwargs: Additional keyword arguments are ignored.

        Returns:
            bool: True if the library is installed, False otherwise.

        """
        try:
            importlib.import_module(lib)
        except ImportError:
            return False
        return True

    @classmethod
    def format_function_param(cls, key, default=None, **kwargs):
        r"""Return the formatted version of the specified key.

        Args:
            key (str): Key in cls.function_param mapping that should be
                formatted.
            default (str, optional): Format that should be returned if key
                is not in cls.function_param. Defaults to None.
            **kwargs: Additional keyword arguments are used in formatting the
                request function parameter.

        Returns:
            str: Formatted string.

        Raises:
            NotImplementedError: If key is not in cls.function_param and default
                is not set.

        """
        if key == 'import':
            fname = kwargs.get('filename', None)
            if fname is not None:
                kwargs['filename'] = os.path.splitext(os.path.basename(fname))[0]
        kwargs['default'] = default
        return super(PythonModelDriver, cls).format_function_param(key, **kwargs)
