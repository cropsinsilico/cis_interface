from yggdrasil import languages, constants, platform
from yggdrasil.tests import assert_raises


def test_get_language_dir():
    r"""Test the get_language_dir method."""
    assert_raises(ValueError, languages.get_language_dir, 'invalid')
    test_lang = constants.LANGUAGES_WITH_ALIASES['all']
    test_skip = ['make', 'cmake', 'executable', 'timesync', 'osr', 'mpi']
    for lang in test_lang:
        if lang in test_skip:
            continue
        languages.get_language_dir(lang)


def test_get_language_ext():
    r"""Test the get_language_ext method."""
    test_lang = constants.LANGUAGES_WITH_ALIASES['all']
    for lang in test_lang:
        if ((((lang == 'executable') and (not platform._is_win))
             or (lang in ['function', 'mpi']))):
            assert_raises(ValueError, languages.get_language_ext, lang)
            languages.get_language_ext(lang, default='')
        else:
            languages.get_language_ext(lang)
