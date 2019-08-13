import os
import gc
import sys
import glob
import logging
import warnings
import argparse
import contextlib
lang_dir = os.path.dirname(__file__)
logger = logging.getLogger(__name__)
logger.setLevel(level=logging.INFO)


def get_language_directories():
    r"""Get language directories.

    Returns:
        list: Language directories.

    """
    out = []
    lang_dirs = sorted(glob.glob(os.path.join(lang_dir, '*')))
    for x in lang_dirs:
        if not os.path.isdir(x):
            continue
        base = os.path.basename(x)
        if base not in ['__pycache__', 'tests']:
            out.append(base)
    return out


@contextlib.contextmanager
def import_language_install(language, no_import=False):
    r"""Temporarily import a language installation script.

    Args:
        language (str): Name of language that installation script should be
            imported for.
        no_import (bool, optional): If True, yggdrasil will not be imported.
            Defaults to False.

    Yields:
        module: Language installation module.

    """
    if not os.path.isfile(os.path.join(lang_dir, language, 'install.py')):
        if not (no_import or os.path.isdir(os.path.join(lang_dir, language))):
            from yggdrasil.languages import get_language_dir
            yield import_language_install(
                os.path.basename(get_language_dir(language)), no_import=True)
        else:
            yield None
        return
    try:
        sys.path.insert(0, os.path.join(lang_dir, language))
        import install
        yield install
    finally:
        sys.path.pop(0)
        if install is not None:
            del install
        if 'install' in globals():
            del globals()['install']
        if 'install' in sys.modules:
            del sys.modules['install']
        gc.collect()


def update_argparser(parser=None, language=None, no_import=None,
                     from_setup=False):
    r"""Update argument parser with language specific arguments.

    Args:
        parser (argparse.ArgumentParser, optional): Existing argument parser
            that should be updated. Default to None and a new argument parser
            will be created.
        language (str, optional): Language that argument parser should be
            updated with options for. Defaults to None and all language options
            will be added.
        no_import (bool, optional): If True, yggdrasil will not be imported.
            Defaults to None and will be set based on sys.argv.
        from_setup (bool, optional): If True, the function is being called from
            setup.py and the positional arguments should not be parsed and
            unrecognized arguments will be ignored. Defaults to False.

    Returns:
        argparse.ArgumentParser: Argument parser with language specific arguments.

    """
    if (no_import is None) and from_setup:
        no_import = True
    all_languages = [x.lower() for x in get_language_directories()]
    if parser is None:
        parser = argparse.ArgumentParser(
            "Run the installation scripts for one or more languages.")
        parser.add_argument('--no-import', action='store_true',
                            help=('Don\'t import the yggdrasil package in '
                                  'calling the installation script.'))
        if not from_setup:
            parser.add_argument('language', nargs='*',
                                choices=(['all'] + all_languages),
                                type=str.lower,
                                default='all',
                                help='One or more languages to install.')
    if ('-h' in sys.argv) or ('--help' in sys.argv) or from_setup:
        if no_import is None:
            no_import = False
        if language is None:
            language = get_language_directories()
    else:
        args = parser.parse_known_args()[0]
        if no_import is None:
            no_import = args.no_import
        if language is None:
            if args.language and ('all' not in args.language):
                language = args.language
            else:
                language = all_languages
    if not isinstance(language, (list, tuple)):
        language = [language]
    for ilang in language:
        with import_language_install(ilang, no_import=no_import) as install:
            if hasattr(install, 'update_argparser'):
                parser = install.update_argparser(parser)
    return parser


def install_language(language, results=None, no_import=False, args=None):
    r"""Call install for a specific language.

    Args:
        language (str): Name of language that should be checked.
        results (dict, optional): Dictionary where result (whether or not the
            language is installed) should be logged. Defaults to None and is
            initialized to an empty dict.
        no_import (bool, optional): If True, yggdrasil will not be imported.
            Defaults to False.
        args (argparse.Namespace, optional): Arguments parsed from the
            command line. Default to None and is created.

    """
    if args is None:
        args = update_argparser(no_import=no_import).parse_args()
    if no_import is None:
        no_import = args.no_import
    if results is None:
        results = {}
    with import_language_install(language, no_import=no_import) as install:
        if install is None:
            logger.info("Nothing to be done for %s" % language)
            name_in_pragmas = language.lower()
            results[name_in_pragmas] = True
            return
        else:
            name_in_pragmas = getattr(install, 'name_in_pragmas', language.lower())
            out = install.install(args=args)
            results[name_in_pragmas] = out
    # if not os.path.isfile(os.path.join(lang_dir, language, 'install.py')):
    #     if not (no_import or os.path.isdir(os.path.join(lang_dir, language))):
    #         from yggdrasil.languages import get_language_dir
    #         return install_language(os.path.basename(get_language_dir(language)),
    #                                 results=results, no_import=True)
    #     logger.info("Nothing to be done for %s" % language)
    #     name_in_pragmas = language.lower()
    #     results[name_in_pragmas] = True
    #     return
    # try:
    #     sys.path.insert(0, os.path.join(lang_dir, language))
    #     import install
    #     name_in_pragmas = getattr(install, 'name_in_pragmas', language.lower())
    #     out = install.install()
    #     results[name_in_pragmas] = out
    # finally:
    #     sys.path.pop(0)
    #     del install
    #     del name_in_pragmas
    #     if 'install' in globals():
    #         del globals()['install']
    #     if 'install' in sys.modules:
    #         del sys.modules['install']
    #     gc.collect()
    if not out:
        warnings.warn(("Could not complete installation for {lang}. "
                       "{lang} support will be disabled.").format(lang=language))
    else:
        logger.info("Language %s installed." % language)


def install_all_languages(from_setup=False, **kwargs):
    r"""Call install.py for all languages that have one and return a dictionary
    mapping from language name to the installation state (True if install was
    successful, False otherwise).

    Args:
        from_setup (bool, optional): If True, the function is being called from
            setup.py and the positional arguments should not be parsed and
            unrecognized arguments will be ignored. Defaults to False.
        **kwargs: Additional keyword arguments are passed to each call to
            install_language.

    Returns:
        dict: Mapping from language name to boolean describing installation
            success.

    """
    if not kwargs.get('args', None):
        kwargs['args'], _ = update_argparser(
            from_setup=True,
            no_import=kwargs.get('no_import', None)).parse_known_args()
    installed_languages = {}
    for ilang in get_language_directories():
        install_language(ilang, installed_languages, **kwargs)
    return installed_languages


if __name__ == "__main__":
    install_all_languages()