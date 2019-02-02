from cis_interface.tests import assert_equal, assert_raises
from cis_interface.metaschema import datatypes
from cis_interface.metaschema.tests import _valid_objects
from cis_interface.metaschema.datatypes.ScalarMetaschemaType import (
    ScalarMetaschemaType)


def test_get_type_class():
    r"""Test get_type_class."""
    for v in _valid_objects.keys():
        datatypes.get_type_class(v)
    assert_raises(ValueError, datatypes.get_type_class, 'invalid')


def test_register_type_errors():
    r"""Test errors in register_type for duplicate."""
    assert_raises(ValueError, datatypes.register_type, ScalarMetaschemaType)
    # fake_prop = type('FakeType', (ScalarMetaschemaType, ),
    #                  {'name': 'number'})
    # assert_raises(ValueError, datatypes.register_type, fake_prop)
    fake_prop = type('FakeType', (ScalarMetaschemaType, ),
                     {'name': 'new', 'properties': ['invalid']})
    assert_raises(ValueError, datatypes.register_type, fake_prop)


def test_add_type_from_schema_errors():
    r"""Test errors in add_type_from_schema."""
    assert_raises(ValueError, datatypes.add_type_from_schema, 'invalid_file')


def test_get_type_from_def():
    r"""Test get_type_from_def."""
    datatypes.get_type_from_def('float')
    datatypes.get_type_from_def({'type': 'float'})
    datatypes.get_type_from_def({'a': 'float', 'b': 'int'})
    datatypes.get_type_from_def(['float', 'int'])
    assert_raises(TypeError, datatypes.get_type_from_def, None)


def test_guess_type_from_msg():
    r"""Test guess_type_from_msg."""
    assert_raises(ValueError, datatypes.guess_type_from_msg,
                  b'fake message')


def test_guess_type_from_obj():
    r"""Test guess_type_from_obj."""
    invalid_objects = [object, object()]
    for t, x in _valid_objects.items():
        assert_equal(datatypes.guess_type_from_obj(x).name, t)
    for x in invalid_objects:
        assert_raises(datatypes.MetaschemaTypeError, datatypes.guess_type_from_obj, x)


def test_encode_decode():
    r"""Test encode/decode for valid objects."""
    for x in _valid_objects.values():
        y = datatypes.encode(x)
        z = datatypes.decode(y)
        assert_equal(z, x)
        datatypes.encode_data(x)


def test_encode_decode_readable():
    r"""Test encode_data_reable/decode for valid objects."""
    for x in _valid_objects.values():
        datatypes.encode_data_readable(x)
        

def test_compare_schema():
    r"""Test for compare_schema."""
    valid = [
        ({'type': 'int'}, {'type': 'int'}),
        ({'type': 'int'}, {'type': 'scalar', 'subtype': 'int'}),
        ({'type': 'scalar', 'subtype': 'int'}, {'type': 'int'}),
        ({'type': 'int', 'unnamed': 0}, {'type': 'int', 'unnamed': 1}),
        ({'type': 'int', 'unnamed': 0}, {'type': 'int'}),
        ({'type': 'object', 'definitions': {'a': {'type': 'int'}},
          'properties': {'x': {'$ref': '#/definitions/a'}}},
         {'type': 'object', 'definitions': {'b': {'type': 'int'}},
          'properties': {'x': {'$ref': '#/definitions/b'}}}),
        ({'type': 'object', 'properties': {'x': {'type': 'float'}}},
         {'type': 'object', 'properties': {'x': {'type': 'float'},
                                           'y': {'type': 'float'}},
          'required': ['x']})]
    invalid = [
        ({'type': 'int'}, {}), ({}, {'type': 'int'}),
        ({'type': 'int'}, {'type': 'int', 'precision': 4}),
        ({'type': 'object', 'definitions': {'a': {'type': 'float'}},
          'properties': {'x': {'$ref': '#/definitions/a'}}},
         {'type': 'object', 'definitions': {'b': {'type': 'int'}},
          'properties': {'x': {'$ref': '#/definitions/b'}}})]
    for x in valid:
        errors = list(datatypes.compare_schema(*x))
        assert(not errors)
    for x in invalid:
        errors = list(datatypes.compare_schema(*x))
        assert(errors)
