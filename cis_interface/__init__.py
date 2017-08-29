r"""This package provides a framework for integrating models across languages
such that they can be run simultaneously, passing input back and forth."""

import os
import backwards
import config
import tools
import interface
import drivers
import dataio
import tests
from interface import PsiRun, PsiInterface


# Set paths so that c headers are located
# TODO: Only the CIS_INCLUDE environment variable should be used
cis_base = os.path.dirname(__file__)
cis_include = os.path.join(cis_base, 'interface')
os.environ['CIS_BASE'] = cis_base
os.environ['CIS_INCLUDE'] = cis_include
path = os.environ.get('PATH', cis_include)
cpath = os.environ.get('CPATH', cis_include)
if cis_include not in path:
    os.environ['PATH'] = cis_include + ':' + path
if cis_include not in cpath:
    os.environ['CPATH'] = cis_include + ':' + cpath


__all__ = ['backwards', 'config', 'PsiRun', 'PsiInterface',
           'tools', 'interface', 'driver', 'dataio', 'tests']
           
