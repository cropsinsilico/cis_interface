import os
from yggdrasil.examples.tests import ExampleTstBase


class TestExampleGS4(ExampleTstBase):
    r"""Test the Getting Started Lesson 4 example."""

    example_name = 'gs_lesson4'
    # iter_over = ['language', 'mpi']
    # iter_list_mpi = ['', 'mpi']

    @property
    def input_files(self):
        r"""Input file."""
        return [os.path.join(self.yamldir, 'Input', 'input.txt')]

    @property
    def output_files(self):
        r"""Output file."""
        return [os.path.join(self.yamldir, 'output.txt')]
