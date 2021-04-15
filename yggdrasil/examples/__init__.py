"""Tools for accessing examples from python."""
import os
import glob
import logging
from yggdrasil import tools, languages, serialize, constants


# TODO: This can be generated from the drivers
ext_map = dict(constants.LANG2EXT, executable='',
               make='.cpp', cmake='.cpp', function='',
               osr='.xml', sbml='.xml')
for lang in tools.get_supported_lang():
    if lang.lower() not in ext_map:
        ext_map[lang.lower()] = languages.get_language_ext(lang)
_example_dir = os.path.dirname(__file__)


def register_example(example_dir):
    r"""Register an example based on the contents of the director.

    Args:
        example_dir (str): Full path to a directory potentially containing an
            example.

    Returns:
        tuple (list, dict, dict): A list of available languages, a dictionary
            mapping from language to YAML specification files for the example,
            and a dictionary mapping from language to source files for the
            example.

    """
    # Check that the source directory and test exist
    example_base = os.path.basename(example_dir)
    srcdir = os.path.join(example_dir, 'src')
    testfile = os.path.join(_example_dir, 'tests',
                            'test_%s.py' % example_base)
    if not os.path.isfile(testfile):  # pragma: no cover
        # TODO: Automate test creation
        if (((not tools.is_subprocess())
             and (example_base not in ['sbml1', 'sbml2', 'sbml3']))):
            logging.error("Missing test file: %s" % testfile)
    if not os.path.isdir(srcdir):  # pragma: no cover
        if not tools.is_subprocess():
            logging.error("Missing source directory: %s" % srcdir)
        return {}
    # Determine which languages are present in the example
    lang_base = []
    lang_avail = []
    lang_search = None
    if example_base in ['rpcFib', 'maxMsg']:
        lang_search = example_base + 'Cli_%s.yml'
        lang_avail += ['all', 'all_nomatlab']
    elif example_base.startswith('rpc_'):
        lang_search = 'client_%s.yml'
    elif example_base == 'root_to_shoot':
        lang_avail += ['all', 'all_nomatlab', 'c', 'python']
    elif example_base == 'fakeplant':
        lang_avail += ['all', 'all_nomatlab', 'c', 'cpp', 'matlab', 'python']
    elif example_base in ['types', 'transforms']:
        lang_avail += tools.get_supported_lang()
        for k in ['cmake', 'make', 'lpy', 'executable']:
            lang_avail.remove(k)
    elif example_base.startswith('sbml'):
        lang_avail = ['sbml']
    elif example_base.startswith('osr'):
        lang_search = example_base + '_%s.yml'
        lang_base += ['osr']
    else:
        lang_search = example_base + '_%s.yml'
    if lang_search is not None:
        for match in glob.glob(os.path.join(example_dir, lang_search % '*')):
            lang = serialize.process_message(os.path.basename(match), lang_search)[0]
            if lang == 'valgrind':
                continue
            lang_avail.append(lang.lower())
    lang_avail = tuple(sorted(lang_avail))
    lang_base = tuple(sorted(lang_base))
    # Get YAML and source files for each language
    out_yml = {}
    out_src = {}
    src_is_abs = False
    for lang in lang_avail:
        yml_names = []
        src_names = []
        if example_base == 'rpcFib':
            if lang == 'all':
                lang_set = ('python', 'matlab', 'c')
            elif lang == 'all_nomatlab':
                lang_set = ('python', 'cpp', 'c')
            else:
                lang_set = (lang, lang, lang)
            yml_names = ['%sCli_%s.yml' % (example_base, lang_set[0]),
                         '%sCliPar_%s.yml' % (example_base, lang_set[1]),
                         '%sSrv_%s.yml' % (example_base, lang_set[2])]
            src_names = ['%sCli%s' % (example_base, ext_map[lang_set[0]]),
                         '%sCliPar%s' % (example_base, ext_map[lang_set[1]]),
                         '%sSrv%s' % (example_base, ext_map[lang_set[2]])]
        elif example_base == 'maxMsg':
            if lang == 'all':
                lang_set = ('python', 'matlab')
            elif lang == 'all_nomatlab':
                lang_set = ('python', 'c')
            else:
                lang_set = (lang, lang)
            yml_names = ['%sCli_%s.yml' % (example_base, lang_set[0]),
                         '%sSrv_%s.yml' % (example_base, lang_set[1])]
            src_names = ['%sCli%s' % (example_base, ext_map[lang_set[0]]),
                         '%sSrv%s' % (example_base, ext_map[lang_set[1]])]
        elif example_base.startswith('rpc_'):
            # TODO: Create server examples in other languages
            yml_names = ['server_%s.yml' % lang,
                         'client_%s.yml' % lang]
            src_names = ['server%s' % ext_map[lang],
                         'client%s' % ext_map[lang]]
        elif example_base == 'root_to_shoot':
            if lang.startswith('all'):
                yml_names = ['root.yml', 'shoot.yml', 'root_to_shoot.yml']
                src_names = ['root.c', 'shoot.py']
            elif lang == 'python':
                yml_names = ['shoot.yml', 'shoot_files.yml']
                src_names = ['shoot.py']
            elif lang == 'c':
                yml_names = ['root.yml', 'root_files.yml']
                src_names = ['root.c']
        elif example_base == 'fakeplant':
            if lang.startswith('all'):
                yml_names = ['canopy.yml', 'light.yml', 'photosynthesis.yml',
                             'fakeplant.yml']
                src_names = ['canopy.cpp', 'light.c', 'photosynthesis.py']
                if lang == 'all_nomatlab':
                    yml_names.append('growth_python.yml')
                    src_names.append('growth.py')
                else:
                    yml_names.append('growth.yml')
                    src_names.append('growth.m')
            elif lang == 'python':
                yml_names = ['photosynthesis.yml']
                src_names = ['photosynthesis.py']
            elif lang == 'c':
                yml_names = ['light.yml', 'light_files.yml']
                src_names = ['light.c']
            elif lang == 'cpp':
                yml_names = ['canopy.yml', 'canopy_files.yml']
                src_names = ['canopy.cpp']
            elif lang == 'matlab':
                yml_names = ['growth.yml', 'growth_files.yml']
                src_names = ['growth.m']
        elif example_base in ['types', 'transforms']:
            yml_names = ['%s.yml' % example_base]
            src_names = ['src.py', 'dst.py']
        elif example_base.startswith('sbml'):
            yml_names = ['%s.yml' % example_base]
            src_names = ['%s.xml' % example_base]
        else:
            src_is_abs = True
            yml_names = ['%s_%s.yml' % (example_base, lang)]
            if lang.startswith('all'):
                src_names = []
                for lsrc in lang_avail:
                    if lsrc.startswith('all'):
                        continue
                    elif (lang == 'all_nomatlab') and (lsrc == 'matlab'):
                        continue
                    src_names += sorted(
                        glob.glob(os.path.join(srcdir,
                                               '*' + ext_map[lsrc])))
            else:
                src_names = sorted(
                    glob.glob(os.path.join(
                        srcdir, '*' + ext_map.get(lang, ''))))
            for ilang_base in lang_base:
                src_names += sorted(
                    glob.glob(os.path.join(
                        srcdir, '*' + ext_map.get(ilang_base, ''))))
        out_yml[lang] = [os.path.join(example_dir, y) for y in yml_names]
        if src_is_abs:
            out_src[lang] = src_names
        else:
            out_src[lang] = [os.path.join(srcdir, s) for s in src_names]
        if len(out_yml[lang]) == 1:
            out_yml[lang] = out_yml[lang][0]
        if len(out_src[lang]) == 1:
            out_src[lang] = out_src[lang][0]
    return lang_base, lang_avail, out_yml, out_src


def discover_examples(parent_dir=None):
    r"""Discover examples under the provided parent directory.

    Args:
        parent_dir (str, optional): Parent directory containing example
            directories. Defaults to the directory containing this function if
            not provided.

    Returns:

    Raises:

    """
    out = {'base_lang': {}, 'lang': {}, 'yml': {}, 'src': {}}
    if parent_dir is None:
        parent_dir = _example_dir
    for match in sorted(glob.glob(os.path.join(parent_dir, '*'))):
        if match.endswith(('tests', '_')) or (not os.path.isdir(match)):
            continue
        match_base = os.path.basename(match)
        iout = register_example(match)
        if iout:
            for i, k in enumerate(['base_lang', 'lang', 'yml', 'src']):
                out[k][match_base] = iout[i]
    return out['base_lang'], out['lang'], out['yml'], out['src']


base_langs, avail_langs, yamls, source = discover_examples()


def get_example_yaml(name, language):
    r"""Get yaml file(s) associated with an example in a certain language.

    Args:
        name (str): Name of the example.
        language (str): Language for example version that should be returned.

    Returns:
        str, list: One or more yaml file(s) associated with the example.

    """
    if name not in yamls:
        raise KeyError("Could not locate yaml for example: '%s'" % name)
    if language in yamls[name]:
        return yamls[name][language]
    elif language.lower() in yamls[name]:
        return yamls[name][language.lower()]
    raise KeyError("Could not locate yaml for example '%s' in language '%s'"
                   % (name, language))


def get_example_source(name, language):
    r"""Get source file(s) associated with an example in a certain language.

    Args:
        name (str): Name of the example.
        language (str): Language for example version that should be returned.

    Returns:
        str, list: One or more source file(s) associated with the example.

    """
    if name not in source:
        raise KeyError("Could not locate source for example: '%s'" % name)
    if language in source[name]:
        return source[name][language]
    elif language.lower() in source[name]:
        return source[name][language.lower()]
    raise KeyError("Could not locate source for example '%s' in language '%s'"
                   % (name, language))


def get_example_languages(name, language=None):
    r"""Get the set of languages that the example is available in.

    Args:
        name (str): Name of the example.
        language (str, optional): If provided, the returned languages will be
            those tested by the version of the example in the specified
            language. Defaults to None and the languages the example is
            available in will be returned.

    Returns:
        list: Languages that the example is available in.

    """
    if name not in avail_langs:
        raise KeyError("Could not locate languages for example: '%s'" % name)
    if language is None:
        out = avail_langs[name]
    elif language in ['all', 'all_nomatlab']:
        out = tuple(
            [x for x in avail_langs[name]
             if not (x.startswith('all')
                     or ((language == 'all_nomatlab') and (x == 'matlab')))]
            + list(base_langs[name]))
    else:
        out = tuple([language] + list(base_langs[name]))
    return out


def display_example(name, language, number_lines=False):
    r"""Display the yaml and source code for an example with syntax
    highlighting.

    Args:
        name (str): Name of the example.
        language (str): Language that example should be displayed in.
        number_lines (bool, optional): If True, line numbers will be added
            to the displayed examples. Defaults to False.

    """
    ex_yml = get_example_yaml(name, language)
    ex_src = get_example_source(name, language)
    tools.display_source(ex_yml, number_lines=number_lines)
    tools.display_source(ex_src, number_lines=number_lines)
    

__all__ = ['yamls', 'source']
