import platform as sys_platform
from yggdrasil import tools, platform
from yggdrasil.drivers.ModelDriver import ModelDriver


# Version flags for windows appear to cause hang so just use
# platform module for now
# if platform._is_win:  # pragma: windows
#     _os_version_flags = ['winver']
# else:
#     _os_version_flags = ['uname', '-r']


class ExecutableModelDriver(ModelDriver):
    r"""Class for running executable based models."""

    language = 'executable'
    # version_flags = _os_version_flags
    _schema_subtype_description = ('Model is an executable.')
    full_language = False
    executable_type = 'other'
    no_executable = True
    comms_implicit = True

    @staticmethod
    def before_registration(cls):
        r"""Operations that should be performed to modify class attributes prior
        to registration including things like platform dependent properties and
        checking environment variables for default settings.
        """
        if ((platform._is_win
             and (not getattr(cls, 'language_ext', None)))):  # pragma: windows
            cls.language_ext = '.exe'
        ModelDriver.before_registration(cls)
        
    @classmethod
    def language_version(cls, version_flags=None, **kwargs):
        r"""Determine the version of this language.

        Args:
            **kwargs: Keyword arguments are passed to cls.run_executable.

        Returns:
            str: Version of compiler/interpreter for this language.

        """
        return sys_platform.platform()
        
    @classmethod
    def executable_command(cls, args, unused_kwargs=None, **kwargs):
        r"""Compose a command for running a program using the exectuable for
        this language (compiler/interpreter) with the provided arguments.

        Args:
            args (list): The program that returned command should run and any
                arguments that should be provided to it.
            unused_kwargs (dict, optional): Existing dictionary that unused
                keyword arguments should be added to. Defaults to None and is
                ignored.
            **kwargs: Additional keyword arguments are ignored.

        Returns:
            list: Arguments composing the command required to run the program
                from the command line using the executable for this language.

        """
        if isinstance(unused_kwargs, dict):
            unused_kwargs.update(kwargs)
        return args
        
    @classmethod
    def is_language_installed(cls):
        r"""Determine if the interpreter/compiler for the associated programming
        language is installed.

        Returns:
            bool: True if the language interpreter/compiler is installed.

        """
        return True

    @classmethod
    def is_configured(cls):
        r"""Determine if the appropriate configuration has been performed (e.g.
        installation of supporting libraries etc.)

        Returns:
            bool: True if the language has been configured.

        """
        return True

    @classmethod
    def is_comm_installed(self, commtype=None, **kwargs):
        r"""Determine if a comm is installed for the associated programming
        language.

        Returns:
            bool: True if a comm is installed for this language.

        """
        if commtype is None:
            return True  # executables presumed to include comms
        return (commtype in tools.get_supported_comm())
