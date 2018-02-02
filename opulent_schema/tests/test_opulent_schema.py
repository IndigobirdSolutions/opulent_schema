import contextlib
import numbers
import unittest
from unittest import mock

import voluptuous as vol

import opulent_schema


all_schema_keys = {
    'multipleOf',
    'maximum',
    'exclusiveMaximum',
    'minimum',
    'exclusiveMinimum',
    'maxLength',
    'minLength',
    'pattern',
    'items',
    'additionalItems',
    'maxItems',
    'minItems',
    'uniqueItems',
    'contains',
    'maxProperties',
    'minProperties',
    'required',
    'properties',
    'patternProperties',
    'additionalProperties',
    'dependencies',
    'propertyNames',
    'enum',
    'const',
    'type',
    'allOf',
    'anyOf',
    'oneOf',
    'not',
    'title',
    'description',
    'default',
    'examples',
}


def example_schema(schema=None, leave_out=()):
    new_schema = dict.fromkeys(all_schema_keys - set(leave_out), None)
    if schema:
        new_schema.update(schema)
    return new_schema


def comparator(attr_names):
    def _eq_method(first, second):
        if type(first) != type(second):
            return False
        sentry1 = object()
        sentry2 = object()
        for attr in attr_names:
            if getattr(first, attr, sentry1) != getattr(second, attr, sentry2):
                return False

        return True
    return _eq_method


def patch_comparing_meths(func):
    def _test_method(*args, **kwargs):
        with contextlib.ExitStack() as stack:
            for cls, attrs in [
                (vol.Any, ['validators']),
                (vol.All, ['validators']),
                (vol.Length, ['min', 'max']),
                (vol.Range, ['min', 'max', 'min_included', 'max_included']),
                (vol.Match, ['pattern']),
                (vol.Optional, ['schema', 'default']),
                (vol.Required, ['schema']),
                (vol.Schema, ['schema', 'required', 'extra']),
                (vol.Coerce, ['type']),
                (vol.In, ['container']),
                (vol.Msg, ['schema', 'msg']),
                (opulent_schema.ExtendedExactSequence, ['validators']),
                (opulent_schema.Not, ['validator']),
                (opulent_schema.OneOf, ['validators']),
                (opulent_schema.MultipleOf, ['divider']),
                (opulent_schema.Unique, []),
                (opulent_schema.AnyPass, ['_schema']),
                (opulent_schema.ListSchema, ['_schema', 'start']),
                (opulent_schema.Contains, ['elements']),
                (opulent_schema.Equalizer, ['expected']),
                (opulent_schema.FullPropertiesSchema, ['_patterns', '_additional_schema', 'basic_props']),
            ]:
                stack.enter_context(mock.patch.object(cls, '__eq__', new=comparator(attrs)))
            stack.enter_context(mock.patch.object(vol.Required, '__hash__', new=lambda self: hash(self.schema)))
            stack.enter_context(mock.patch.object(vol.Optional, '__hash__', new=lambda self: hash(self.schema)))
            stack.enter_context(mock.patch.object(vol.Match, '__hash__', new=lambda self: hash(self.pattern)))
            stack.enter_context(mock.patch.object(vol.All, '__hash__', new=lambda self: hash(repr(self))))
            return func(*args, **kwargs)
    return _test_method


class Test(unittest.TestCase):
    maxDiff = None

    def test_schema_schema(self):
        opulent_schema.schema_schema({
            'type': 'object',
            'properties': {
                'a': {
                    'type': 'object',
                    'patternProperties': {
                        '_\w*': {'type': 'string'}
                    },
                    'additionalProperties': {'type': 'integer'}
                }
            }
        })

    def test_schema_schema_fail(self):
        with self.assertRaises(vol.Invalid) as exception_info:
            opulent_schema.schema_schema({
                'type': 'object',
                'properties': {
                    'a': {
                        'type': 'object',
                        'patternProperties': {
                            '_\w*': {'typo': 'string'}  # there's a TYPO here... get it? :)
                        },
                        'additionalProperties': {'type': 'integer'}
                    }
                }
            })
        self.assertEqual(
            str(exception_info.exception),
            "extra keys not allowed @ data['properties']['a']['patternProperties']['_\\\w*']['typo']"
        )

    def test_get_length_no_nothing(self):
        res = opulent_schema.SchemaConverter.get_length(None, None)
        self.assertEqual([], res)

    @patch_comparing_meths
    def test_get_length_min(self):
        res = opulent_schema.SchemaConverter.get_length(-7, None)
        self.assertEqual([vol.Length(min=-7)], res)

    @patch_comparing_meths
    def test_get_length_max(self):
        res = opulent_schema.SchemaConverter.get_length(None, 17)
        self.assertEqual([vol.Length(max=17)], res)

    @patch_comparing_meths
    def test_get_length_both(self):
        res = opulent_schema.SchemaConverter.get_length(-7, 17)
        self.assertEqual([vol.Length(min=-7, max=17)], res)

    def test_string_validators_empty(self):
        res = opulent_schema.SchemaConverter.string_validators(
            example_schema(leave_out=['maxLength', 'minLength', 'pattern']))

        self.assertEqual([], res)

    @patch_comparing_meths
    def test_string_validators_no_type(self):
        res = opulent_schema.SchemaConverter.string_validators(
            example_schema({'minLength': 5, 'pattern': 'abc'}, leave_out=['type', 'maxLength']))

        self.assertEqual(
            [vol.Any(vol.All(str, vol.Length(min=5), vol.Match('abc')), opulent_schema.Not(str))], res)

    @patch_comparing_meths
    def test_string_validators_with_type(self):
        res = opulent_schema.SchemaConverter.string_validators(
            example_schema({'minLength': 5, 'pattern': 'abc', 'type': 'string'}, leave_out=['maxLength']))

        self.assertEqual([vol.Length(min=5), vol.Match('abc')], res)

    def test_number_validators_empty(self):
        res = opulent_schema.SchemaConverter.number_validators(
            example_schema(leave_out=['multipleOf', 'maximum', 'exclusiveMaximum', 'minimum', 'exclusiveMinimum']))

        self.assertEqual([], res)

    @patch_comparing_meths
    def test_number_validators_with_type(self):
        res = opulent_schema.SchemaConverter.number_validators(
            example_schema(
                {'maximum': 5, 'minimum': 3, 'type': 'integer'},
                leave_out=['multipleOf']))

        self.assertEqual([vol.Range(min=3, min_included=True, max=5, max_included=True)], res)

    @patch_comparing_meths
    def test_number_validators_with_type2(self):
        res = opulent_schema.SchemaConverter.number_validators(
            example_schema(
                {'exclusiveMaximum': 5, 'exclusiveMinimum': 3, 'type': 'integer'},
                leave_out=['multipleOf']))

        self.assertEqual([vol.Range(min=3, min_included=False, max=5, max_included=False)], res)

    @patch_comparing_meths
    def test_number_validators_both_ends_incl_with_type(self):
        res = opulent_schema.SchemaConverter.number_validators(
            example_schema(
                {'maximum': 5, 'exclusiveMaximum': 6, 'minimum': 3, 'exclusiveMinimum': 2, 'type': 'integer'},
                leave_out=['multipleOf']))

        self.assertEqual([vol.Range(min=3, min_included=True, max=5, max_included=True)], res)

    @patch_comparing_meths
    def test_number_validators_both_ends_excl_with_type(self):
        res = opulent_schema.SchemaConverter.number_validators(
            example_schema(
                {'maximum': 7, 'exclusiveMaximum': 6, 'minimum': 1, 'exclusiveMinimum': 2, 'type': 'number'},
                leave_out=['multipleOf']))

        self.assertEqual([vol.Range(min=2, min_included=False, max=6, max_included=False)], res)

    @patch_comparing_meths
    def test_number_validators_both_ends_with_type(self):
        res = opulent_schema.SchemaConverter.number_validators(
            example_schema({'maximum': 5, 'exclusiveMaximum': 5, 'minimum': 3, 'exclusiveMinimum': 3,
                            'type': 'integer'}, leave_out=['multipleOf']))

        self.assertEqual([vol.Range(min=3, min_included=False, max=5, max_included=False)], res)

    @patch_comparing_meths
    def test_number_validators_everything(self):
        res = opulent_schema.SchemaConverter.number_validators(
            example_schema(
                {'maximum': 5, 'exclusiveMaximum': 6, 'minimum': 2, 'exclusiveMinimum': 3, 'multipleOf': 1.01},
                leave_out=['type']))

        self.assertEqual(
            [
                vol.Any(
                    vol.All(
                        numbers.Number,
                        vol.Range(min=3, min_included=False, max=5, max_included=True),
                        opulent_schema.MultipleOf(1.01)
                    ),
                    opulent_schema.Not(numbers.Number),
                )
            ],
            res)

    def test_array_validators_empty(self):
        res = opulent_schema.SchemaConverter.array_validators(
            example_schema(leave_out=['items', 'additionalItems', 'maxItems', 'minItems', 'uniqueItems', 'contains']))

        self.assertEqual([], res)

    @patch_comparing_meths
    @mock.patch.object(opulent_schema.SchemaConverter, 'go', side_effect=lambda x: x)
    def test_array_validators_items_dict(self, go: mock.Mock):
        res = opulent_schema.SchemaConverter.array_validators(example_schema(
            {
                'items': {'i am': 'a dict'},
                'maxItems': 6,
                'minItems': 2,
                'uniqueItems': True,
                'contains': 'i am a "contains" attribute',
                'type': 'array',
                'additionalItems': 'should be ignored'
            }))

        self.assertEqual([
            vol.Length(min=2, max=6),
            opulent_schema.Unique(),
            opulent_schema.AnyPass('i am a "contains" attribute'),
            [{'i am': 'a dict'}],
        ], res)
        self.assertEqual([
            mock.call('i am a "contains" attribute'),
            mock.call({'i am': 'a dict'}),
        ], go.call_args_list)

    @patch_comparing_meths
    @mock.patch.object(opulent_schema.SchemaConverter, 'go', side_effect=lambda x: x)
    def test_array_validators_items_list_no_additional(self, go: mock.Mock):
        res = opulent_schema.SchemaConverter.array_validators(example_schema(
            {
                'items': [{'i am': 'a dict'}, {'and i am': 'another dict'}],
                'maxItems': 6,
                'uniqueItems': False,
                'type': ['array'],
            }, leave_out=['additionalItems', 'contains']))

        self.assertEqual([
            vol.Length(min=None, max=6),
            opulent_schema.ExtendedExactSequence([{'i am': 'a dict'}, {'and i am': 'another dict'}]),
        ], res)
        self.assertEqual([
            mock.call({'i am': 'a dict'}),
            mock.call({'and i am': 'another dict'}),
        ], go.call_args_list)

    @patch_comparing_meths
    @mock.patch.object(opulent_schema.SchemaConverter, 'go', side_effect=lambda x: x)
    def test_array_validators_items_list_with_additional(self, go: mock.Mock):
        res = opulent_schema.SchemaConverter.array_validators(example_schema(
            {
                'items': [{'i am': 'a dict'}, {'and i am': 'another dict'}],
                'minItems': 6,
                'additionalItems': {'some': 'schema'},
                'type': ['array'],
            }, leave_out=['contains']))

        self.assertEqual([
            vol.Length(min=6, max=None),
            opulent_schema.ExtendedExactSequence([{'i am': 'a dict'}, {'and i am': 'another dict'}]),
            opulent_schema.ListSchema({'some': 'schema'}, 2),
        ], res)
        self.assertEqual([
            mock.call({'i am': 'a dict'}),
            mock.call({'and i am': 'another dict'}),
            mock.call({'some': 'schema'}),
        ], go.call_args_list)

    @patch_comparing_meths
    @mock.patch.object(opulent_schema.SchemaConverter, 'go', side_effect=lambda x: x)
    def test_array_validators_no_type(self, go: mock.Mock):
        res = opulent_schema.SchemaConverter.array_validators(example_schema(
            {
                'items': [{'i am': 'a dict'}, {'and i am': 'another dict'}],
                'additionalItems': {'some': 'schema'},
            }, leave_out=['contains', 'type']))

        self.assertListEqual([
            vol.Any(
                vol.All(list,
                        opulent_schema.ExtendedExactSequence([{'i am': 'a dict'}, {'and i am': 'another dict'}]),
                        opulent_schema.ListSchema({'some': 'schema'}, 2),
                        ),
                opulent_schema.Not(list),
            )
        ], res)

    def test_object_validators_empty(self):
        res = opulent_schema.SchemaConverter.object_validators(
            example_schema(leave_out=['properties', 'additionalProperties', 'patternProperties', 'maxProperties',
                                      'minProperties', 'required', 'dependencies', 'propertyNames']))

        self.assertEqual([], res)

    @mock.patch.object(opulent_schema.SchemaConverter, 'go', side_effect=lambda x: x)
    @mock.patch('voluptuous.schema_builder.default_factory', side_effect=lambda x: x)
    @patch_comparing_meths
    def test_object_validators_no_additional_no_pattern(self, df, go):
        def expected_result(extra):
            return [
                vol.Length(min=3, max=8),
                vol.Schema({
                    vol.Required('b'): {'key': 2},
                    vol.Required('d'): object,
                    vol.Optional('a', default=-17): {'key': 1, 'default': -17},
                    vol.Optional('c'): {'key': 3},
                }, extra=extra),
                vol.Any(opulent_schema.Not(opulent_schema.Contains('dep1')),
                        opulent_schema.Contains('dep1', 'req_dep_key_1', 'req_dep_key_2', 'req_dep_key_3')),
                vol.Any(opulent_schema.Not(opulent_schema.Contains('dep2')),
                        opulent_schema.Contains('dep2', 'req_dep_key_4', 'req_dep_key_5', 'req_dep_key_6')),
                vol.Any(opulent_schema.Not(opulent_schema.Contains('dep3')), {'dict?': "yup, it's a dict"}),
                vol.Any(opulent_schema.Not(opulent_schema.Contains('dep4')), {'again?': "indeed"}),
                vol.Schema(vol.Msg({vol.All(vol.Match('a'), vol.Length(min=4)): object},
                                   'Property name schema {} not fulfilled'.format(
                                       vol.All(vol.Match('a'), vol.Length(min=4))))),
            ]

        input_schema = example_schema({
            'minProperties': 3,
            'maxProperties': 8,
            'properties': {
                'a': {'key': 1, 'default': -17},
                'b': {'key': 2},
                'c': {'key': 3},
            },
            'required': ['b', 'd'],
            'dependencies': {
                'dep1': ['req_dep_key_1', 'req_dep_key_2', 'req_dep_key_3'],
                'dep2': ['req_dep_key_4', 'req_dep_key_5', 'req_dep_key_6'],
                'dep3': {'dict?': "yup, it's a dict"},
                'dep4': {'again?': "indeed"},
            },
            'propertyNames': vol.All(vol.Match('a'), vol.Length(min=4)),  # this is not a jsonschema, it's more like
            #  something the `go` method would return, it's just easier to write the test like this
            'type': 'object'
        })
        res = opulent_schema.SchemaConverter.object_validators(input_schema)
        self.assertListEqual(expected_result(vol.ALLOW_EXTRA), res)

        res = opulent_schema.ExactSchemaConverter.object_validators(input_schema)
        self.assertListEqual(expected_result(vol.PREVENT_EXTRA), res)

    @mock.patch.object(opulent_schema.SchemaConverter, 'go', side_effect=lambda x: x)
    @mock.patch('voluptuous.schema_builder.default_factory', side_effect=lambda x: x)
    @patch_comparing_meths
    def test_object_validators_additional_no_pattern(self, df, go):
        expected_result = [
            {
                vol.Required('b'): {'key': 2},
                vol.Required('d'): object,
                vol.Optional('a', default=-17): {'key': 1, 'default': -17},
                vol.Optional('c'): {'key': 3},
                str: {'schema': 'of additionalProperties'}
            },
        ]

        input_schema = example_schema({
            'properties': {
                'a': {'key': 1, 'default': -17},
                'b': {'key': 2},
                'c': {'key': 3},
            },
            'additionalProperties': {'schema': 'of additionalProperties'},
            'required': ['b', 'd'],
            'type': ['object']
        }, leave_out=['dependencies', 'propertyNames'])

        res1 = opulent_schema.SchemaConverter.object_validators(input_schema)
        res2 = opulent_schema.ExactSchemaConverter.object_validators(input_schema)
        try:
            self.assertListEqual(expected_result, res1)
            self.assertListEqual(expected_result, res2)
        except AttributeError as ex:
            if str(ex) != "type object 'str' has no attribute 'schema'":
                raise
            self.assertTrue(False, msg='The test failed and so did the method to print the diff. Come here and debug it'
                                       ' yourself')

    @mock.patch.object(opulent_schema.SchemaConverter, 'go', side_effect=lambda x: x)
    @mock.patch('voluptuous.schema_builder.default_factory', side_effect=lambda x: x)
    @patch_comparing_meths
    def test_object_validators_pattern_no_additional(self, df, go):
        def expected_result(extra):
            validators = []
            if extra == vol.PREVENT_EXTRA:
                validators = [vol.Schema({
                    vol.Required('b'): object,
                    vol.Required('d'): object,
                    vol.Optional('a', default=-17): object,
                    vol.Optional('c'): object,
                    vol.Match('re1'): object,
                    vol.Match('re2'): object,
                    vol.Match('re3'): object,

                }, extra=vol.PREVENT_EXTRA)]
            return validators + [
                vol.Schema({
                    vol.Required('b'): {'key': 2},
                    vol.Required('d'): object,
                    vol.Optional('a', default=-17): {'key': 1, 'default': -17},
                    vol.Optional('c'): {'key': 3},
                }, extra=vol.ALLOW_EXTRA),
                vol.Schema({vol.Match('re1'): 'some schema'}, extra=vol.ALLOW_EXTRA),
                vol.Schema({vol.Match('re2'): 'some other schema'}, extra=vol.ALLOW_EXTRA),
                vol.Schema({vol.Match('re3'): 'yet another schema'}, extra=vol.ALLOW_EXTRA),
            ]
        input_schema = example_schema({
            'properties': {
                'a': {'key': 1, 'default': -17},
                'b': {'key': 2},
                'c': {'key': 3},
            },
            'patternProperties': {
                're1': 'some schema',
                're2': 'some other schema',
                're3': 'yet another schema',
            },
            'required': ['b', 'd'],
            'type': ['object']
        }, leave_out=['dependencies', 'propertyNames'])

        res = opulent_schema.SchemaConverter.object_validators(input_schema)
        self.assertListEqual(expected_result(vol.ALLOW_EXTRA), res)

        res = opulent_schema.ExactSchemaConverter.object_validators(input_schema)
        self.assertListEqual(expected_result(vol.PREVENT_EXTRA), res)

    @mock.patch.object(opulent_schema.SchemaConverter, 'go', side_effect=lambda x: x)
    @mock.patch('voluptuous.schema_builder.default_factory', side_effect=lambda x: x)
    @patch_comparing_meths
    def test_object_validators_full_package(self, df, go):
        input_schema = example_schema({
                'properties': {
                    'a': {'key': 1, 'default': -17},
                    'b': {'key': 2},
                    'c': {'key': 3},
                },
                'patternProperties': {
                    're1': 'some schema',
                    're2': 'some other schema',
                    're3': 'yet another schema',
                },
                'additionalProperties': {'schema': 'of additionalProperties'},
                'required': ['b', 'd'],
                'type': ['object']
            }, leave_out=['dependencies', 'propertyNames'])
        expected_result = [
            vol.Schema({
                vol.Required('b'): {'key': 2},
                vol.Required('d'): object,
                vol.Optional('a', default=-17): {'key': 1, 'default': -17},
                vol.Optional('c'): {'key': 3},
            }, extra=vol.ALLOW_EXTRA),
            opulent_schema.FullPropertiesSchema(
                go,
                {
                    're1': 'some schema',
                    're2': 'some other schema',
                    're3': 'yet another schema',
                },
                {'schema': 'of additionalProperties'},
                {'a', 'b', 'c'}
            ),
        ]

        res = opulent_schema.SchemaConverter.object_validators(input_schema)
        self.assertListEqual(expected_result, res)

        res = opulent_schema.ExactSchemaConverter.object_validators(input_schema)
        self.assertListEqual(expected_result, res)

    @mock.patch.object(opulent_schema.SchemaConverter, 'go', side_effect=lambda x: x)
    @mock.patch('voluptuous.schema_builder.default_factory', side_effect=lambda x: x)
    @patch_comparing_meths
    def test_object_validators_no_type1(self, df, go):
        res = opulent_schema.SchemaConverter.object_validators(
            example_schema({
                'minProperties': 3,
                'properties': {
                    'a': {'key': 1, 'default': -17},
                    'b': {'key': 2},
                    'c': {'key': 3},
                },
                'required': ['b', 'd'],
            }, leave_out=['dependencies', 'type', 'propertyNames']))
        self.assertListEqual([vol.Any(
            vol.All(
                dict,
                vol.Length(min=3, max=None),
                vol.Schema({
                    vol.Required('b'): {'key': 2},
                    vol.Required('d'): object,
                    vol.Optional('a', default=-17): {'key': 1, 'default': -17},
                    vol.Optional('c'): {'key': 3},
                }, extra=vol.ALLOW_EXTRA),
            ),
            opulent_schema.Not(dict),
        )], res)

    @mock.patch.object(opulent_schema.SchemaConverter, 'go', side_effect=lambda x: x)
    @mock.patch('voluptuous.schema_builder.default_factory', side_effect=lambda x: x)
    @patch_comparing_meths
    def test_object_validators_no_type2(self, df, go):
        res = opulent_schema.SchemaConverter.object_validators(
            example_schema({
                'minProperties': 3,
                'properties': {
                    'a': {'key': 1, 'default': -17},
                    'b': {'key': 2},
                    'c': {'key': 3},
                },
                'required': ['b', 'd'],
                'type': ['object', 'string'],
            }, leave_out=['dependencies', 'propertyNames']))
        self.assertListEqual([
            vol.Any(
                vol.All(
                    dict,
                    vol.Length(min=3, max=None),
                    vol.Schema({
                        vol.Required('b'): {'key': 2},
                        vol.Required('d'): object,
                        vol.Optional('a', default=-17): {'key': 1, 'default': -17},
                        vol.Optional('c'): {'key': 3},
                    }, extra=vol.ALLOW_EXTRA),
                ),
                opulent_schema.Not(dict),
            )
        ], res)

    def test_Not_pass(self):
        self.assertEqual({'a': 1}, vol.Schema(opulent_schema.Not({'a': float}))({'a': 1}))

    def test_Not_fail(self):
        with self.assertRaises(vol.Invalid):
            vol.Schema(opulent_schema.Not({'a': int}))({'a': 1})

    def test_OneOf_pass(self):
        self.assertEqual({'a': 1},
                         vol.Schema(opulent_schema.OneOf({'a': vol.Coerce(int)}, {'a': vol.Coerce(list)}))({'a': 1.5}))

    def test_OneOf_fail1(self):
        with self.assertRaises(vol.Invalid):
            vol.Schema(opulent_schema.OneOf({'a': dict}, {'a': list}))({'a': 1})

    def test_OneOf_fail2(self):
        with self.assertRaises(vol.Invalid):
            vol.Schema(opulent_schema.OneOf({'a': int}, {'a': int}))({'a': 1})

    def test_ExtendedExactSequence1(self):
        self.assertEqual(
            [1, 'a'],
            opulent_schema.ExtendedExactSequence([vol.Coerce(int), str])([1.5, 'a'])
        )

    def test_ExtendedExactSequence2(self):
        self.assertEqual(
            [1, 'a', 6, 7],
            opulent_schema.ExtendedExactSequence([vol.Coerce(int), str])([1.5, 'a', 6, 7])
        )

    def test_ExtendedExactSequence3(self):
        self.assertEqual(
            [1],
            opulent_schema.ExtendedExactSequence([vol.Coerce(int), str])([1.5])
        )

    def test_Contains_pass(self):
        self.assertEqual(
            [1, 2, 3],
            vol.Schema(opulent_schema.Contains(2))([1, 2, 3])
        )

    def test_Contains_fail(self):
        with self.assertRaises(vol.Invalid):
            vol.Schema(opulent_schema.Contains(4))([1, 2, 3])

    def test_MultipleOf_pass(self):
        self.assertEqual(
            7.035,
            vol.Schema(opulent_schema.MultipleOf(1.005))(7.035)
        )

    def test_MultipleOf_fail(self):
        with self.assertRaises(vol.Invalid):
            vol.Schema(opulent_schema.MultipleOf(1.005))(7.03500001)

    def test_AnyPass_pass1(self):
        self.assertEqual(
            ['a', 'b', 4],
            vol.Schema(opulent_schema.AnyPass(int))(['a', 'b', 4])
        )

    def test_AnyPass_pass2(self):
        self.assertEqual(
            [4, 'a', 'b', 4],
            vol.Schema(opulent_schema.AnyPass(int))([4, 'a', 'b', 4])
        )

    def test_AnyPass_pass3(self):
        self.assertEqual(
            [4],
            vol.Schema(opulent_schema.AnyPass(int))([4])
        )

    def test_AnyPass_fail(self):
        with self.assertRaises(vol.Invalid):
            vol.Schema(opulent_schema.AnyPass(int))(['a', 'b'])

    def test_Unique_pass1(self):
        self.assertEqual(
            [{'a': 1}, {'a': 2}],
            vol.Schema(opulent_schema.Unique())([{'a': 1}, {'a': 2}])
        )

    def test_Unique_pass2(self):
        self.assertEqual(
            [{'a': 1}],
            vol.Schema(opulent_schema.Unique())([{'a': 1}])
        )

    def test_Unique_fail(self):
        with self.assertRaises(vol.Invalid):
            vol.Schema(opulent_schema.Unique())([{'a': 1}, {'a': 1}])

    def test_ListSchema_pass1(self):
        self.assertEqual(
            ['a', 'b', 'c', 1, 2],
            vol.Schema(opulent_schema.ListSchema(vol.Coerce(int), 3))(['a', 'b', 'c', 1.5, 2.5])
        )

    def test_ListSchema_pass2(self):
        self.assertEqual(
            ['a', 'b', 'c', 1.5, 2.5],
            vol.Schema(opulent_schema.ListSchema(vol.Coerce(int), 5))(['a', 'b', 'c', 1.5, 2.5])
        )

    def test_ListSchema_fail(self):
        with self.assertRaises(vol.Invalid):
            vol.Schema(opulent_schema.ListSchema(vol.Coerce(int), 2))(['a', 'b', 'c', 1.5, 2.5])

    def test_FullPropertiesSchema(self):
        self.assertEqual(
            {
                'a': '1a',
                'b': '2b',
                'ab': '3ba',
                'c': '4x',
                'ap1': '5a',
                'p2': '6'
            },
            vol.Schema(opulent_schema.FullPropertiesSchema(
                lambda x: x,
                {
                    '\w?b': vol.Coerce(lambda x: x + 'b'),
                    'a': vol.Coerce(lambda x: x + 'a'),
                },
                vol.Coerce(lambda x: x + 'x'),
                {'ap1', 'p2'},
            ))({
                'a': '1',
                'b': '2',
                'ab': '3',
                'c': '4',
                'ap1': '5',
                'p2': '6'
            })
        )

    def test_IntegralNumber_pass1(self):
        self.assertEqual(
            1,
            vol.Schema(opulent_schema.IntegralNumber())(1)
        )

    def test_IntegralNumber_pass2(self):
        self.assertEqual(
            1.0,
            vol.Schema(opulent_schema.IntegralNumber())(1.0)
        )

    def test_IntegralNumber_fail(self):
        with self.assertRaises(vol.Invalid):
            vol.Schema(opulent_schema.IntegralNumber())(1.001)

    def test_Equalizer_pass(self):
        self.assertEqual(
            [1, 2, {'a': 5}],
            vol.Schema(opulent_schema.Equalizer([1, 2, {'a': 5}]))([1, 2, {'a': 5}]),
        )

    def test_Equalizer_fail(self):
        with self.assertRaises(vol.Invalid) as exception:
            vol.Schema(opulent_schema.Equalizer([1, 2, {'a': 5}]))([1, 2, {'a': 5, 'b': 1}])

        self.assertEqual(str(exception.exception), "Value not equal to: [1, 2, {'a': 5}]")

    def test_go_just_the_type1(self):
        res = opulent_schema.SchemaConverter.go({
            'type': 'object',
        })
        self.assertEqual(res, dict)

    def test_go_just_the_type2(self):
        res = opulent_schema.SchemaConverter.go({
            'type': ['object'],
        })
        self.assertEqual(res, dict)

    @patch_comparing_meths
    def test_go_just_the_type3(self):
        res = opulent_schema.SchemaConverter.go({
            'type': ['object', 'string'],
        })
        self.assertEqual(res, vol.Any(dict, str))

    @mock.patch.object(opulent_schema.SchemaConverter, 'object_validators',
                       side_effect=[['object_validators']] + [[]]*100)
    @mock.patch.object(opulent_schema.SchemaConverter, 'number_validators',
                       side_effect=[['number_validators']] + [[]]*100)
    @mock.patch.object(opulent_schema.SchemaConverter, 'string_validators',
                       side_effect=[['string_validators']] + [[]]*100)
    @mock.patch.object(opulent_schema.SchemaConverter, 'array_validators',
                       side_effect=[['array_validators']] + [[]]*100)
    @patch_comparing_meths
    def test_go_idunno(self, array_validators, string_validators, number_validators, object_validators):

        class ExampleTranfromedField(opulent_schema.TransformedField):
            def _transform(self, instance):
                pass
        in_jsonschema = ExampleTranfromedField(**{
            'anyOf': [{'type': 'integer'}, {'type': 'number'}],
            'allOf': [{'type': 'string'}, {'type': 'object'}],
            'oneOf': [{'type': 'array'}, {'type': 'object'}],
            'const': 17,
            'enum': [5, None, {'a': 17}],
            'not': {'type': 'object'},
        })
        res = opulent_schema.SchemaConverter.go(in_jsonschema)
        self.assertEqual(vol.All(
            'object_validators',
            'number_validators',
            'string_validators',
            'array_validators',
            vol.Any(opulent_schema.type_mapping['integer'], numbers.Number),
            vol.All(str, dict),
            opulent_schema.OneOf(list, dict),
            opulent_schema.Equalizer(17),
            vol.In([5, None, {'a': 17}]),
            opulent_schema.Not(dict),
            vol.Coerce(in_jsonschema._transform),
        ), res)

    # integration tests:

    testing_schema = {
        'type': 'object',
        'properties': {
            'one': {
                'type': 'string',
                'minLength': 5,
            },
            'two': {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'properties': {
                        'a': {'type': 'integer'},
                        'b': {
                            'anyOf': [
                                {'type': 'integer'},
                                {'type': 'string', 'pattern': 'abc'},
                            ]
                        },
                    },
                    'required': ['a', 'b'],
                }
            },
            'three': {
                'allOf': [
                    {'type': 'integer', 'multipleOf': 2},
                    {'type': 'number', 'minimum': 10},
                ],
                'default': 'default'
            },
        },
        'required': ['one', 'two']
    }

    def test1(self):

        self.assertEqual(opulent_schema.exact_check_and_convert(self.testing_schema)({
            'one': '12345',
            'two': [{'a': 7, 'b': 1}, {'a': 7, 'b': 'abc2'}],
            'three': 12,
        }), {
            'one': '12345',
            'two': [{'a': 7, 'b': 1}, {'a': 7, 'b': 'abc2'}],
            'three': 12,
        })

    def test2(self):

        self.assertEqual(opulent_schema.exact_check_and_convert(self.testing_schema)({
            'one': '12345',
            'two': [{'a': 7, 'b': 1}, {'a': 7, 'b': 'abc2'}],
        }), {
            'one': '12345',
            'two': [{'a': 7, 'b': 1}, {'a': 7, 'b': 'abc2'}],
            'three': 'default',
        })

    def test3(self):
        with self.assertRaises(vol.Invalid) as exception:
            opulent_schema.exact_check_and_convert(self.testing_schema)({
                'one': '12345',
                'two': [{'a': 7, 'b': 1}, {'a': 7, 'b': 'abc2'}],
                'extra': 'extra',
            })
        self.assertEqual(str(exception.exception), "extra keys not allowed @ data['extra']")

    def test4(self):

        self.assertEqual(opulent_schema.check_and_convert(self.testing_schema)({
            'one': '12345',
            'two': [{'a': 7, 'b': 1}, {'a': 7, 'b': 'abc2'}],
            'extra': 'extra',
        }), {
            'one': '12345',
            'two': [{'a': 7, 'b': 1}, {'a': 7, 'b': 'abc2'}],
            'three': 'default',
            'extra': 'extra',
        })

    def test5(self):
        with self.assertRaises(vol.Invalid) as exception:
            opulent_schema.exact_check_and_convert(self.testing_schema)({
                'one': '12345',
                'two': [{'a': 7, 'b': 1}, {'a': 7, 'b': 'not right'}],
            })
        self.assertEqual(str(exception.exception), "not a valid value for dictionary value @ data['two'][1]['b']")

    everything = {
        'multipleOf': 1,
        'maximum': 100,
        'exclusiveMaximum': 100,
        'minimum': 1,
        'exclusiveMinimum': 1,
        'maxLength': 100,
        'minLength': 1,
        'pattern': 'abc',
        'items': {'type': 'string'},
        'additionalItems': {'type': 'string'},
        'maxItems': 100,
        'minItems': 1,
        'uniqueItems': True,
        'contains': {'type': 'string'},
        'maxProperties': 100,
        'minProperties': 1,
        'required': ['a', 'b'],
        'properties': {'a': {'type': 'integer'}, 'b': {'type': 'integer'}},
        'patternProperties': {'a': {'type': 'integer'}},
        'additionalProperties': {'type': ['integer', 'string']},
        'dependencies': {'a': ['a', 'b'], 'c': {'type': 'object', 'additionalProperties': {'type': 'number'}}},
        'propertyNames': {'type': 'string', 'minLength': 1},
        'enum': [1, 2, {'a': 5}],
        'const': [1, 2, {'a': 5}],
        'type': ['integer', 'string'],
        'allOf': [{'type': 'string'}, {'minLength': 5}],
        'anyOf': [{'type': 'string'}, {'type': 'integer'}],
        'oneOf': [{'type': 'string'}, {'type': 'integer'}],
        'not': {'type': 'string', 'pattern': 'def'},
        'title': 'title',
        'description': 'description',
        'default': 'default',
        'examples': ['examples'],
    }

    @classmethod
    def _everything_except(cls, *except_):
        new_everything = cls.everything.copy()
        for key in except_:
            new_everything.pop(key)
        return new_everything

    def test_everything_1(self):
        self.assertEqual(
            opulent_schema.check_and_convert(self._everything_except(
                'enum', 'allOf', 'oneOf', 'anyOf', 'type', 'contains', 'items', 'additionalItems'))([1, 2, {'a': 5}]),
            [1, 2, {'a': 5}]
        )

    def test_everything_2(self):
        with self.assertRaises(vol.Invalid):
            opulent_schema.check_and_convert(self._everything_except(
                'enum', 'allOf', 'oneOf', 'anyOf', 'type', 'contains', 'items', 'additionalItems'))([1, 2, {'a': 6}])

    def test_everything_3(self):
        self.assertEqual(
            opulent_schema.check_and_convert(self._everything_except(
                'const', 'allOf', 'oneOf', 'anyOf', 'type', 'contains', 'items', 'additionalItems'))(2),
            2
        )

    def test_everything_4(self):
        with self.assertRaises(vol.Invalid):
            opulent_schema.check_and_convert(self._everything_except(
                'const', 'allOf', 'oneOf', 'anyOf', 'type', 'contains', 'items', 'additionalItems'))(3)

    def test_everything_5(self):
        self.assertEqual(
            opulent_schema.check_and_convert(self._everything_except('enum', 'const'))('abcdef'),
            'abcdef'
        )

    def test_everything_6(self):
        with self.assertRaises(vol.Invalid):
            opulent_schema.check_and_convert(self._everything_except(
                'allOf', 'oneOf', 'anyOf', 'enum', 'const', 'pattern'))('defabc'),

    def test_everything_7(self):
        self.assertEqual(
            opulent_schema.check_and_convert(self._everything_except(
                'allOf', 'oneOf', 'anyOf', 'enum', 'const', 'type'))({'a': 1, 'b': 2, 'c': 3}),
            {'a': 1, 'b': 2, 'c': 3}
        )

    def test_everything_8(self):
        self.assertEqual(
            opulent_schema.check_and_convert(self._everything_except(
                'allOf', 'oneOf', 'anyOf', 'enum', 'const', 'type'))({'a': 1, 'b': 2}),
            {'a': 1, 'b': 2}
        )

    def test_everything_9(self):
        with self.assertRaises(vol.Invalid):
            opulent_schema.check_and_convert(self._everything_except(
                'allOf', 'oneOf', 'anyOf', 'enum', 'const', 'type'))({'a': 1, 'b': 2, 'c': 3, 'd': 'd'})

    def test_everything_10(self):
        self.assertEqual(
            opulent_schema.check_and_convert(self._everything_except(
                'allOf', 'oneOf', 'anyOf', 'enum', 'const', 'type'))(['a', 'b']),
            ['a', 'b']
        )

    def test_everything_11(self):
        schema = self._everything_except('allOf', 'oneOf', 'anyOf', 'enum', 'const', 'type')
        schema['items'] = [{'type': 'string'}]
        self.assertEqual(
            opulent_schema.check_and_convert(self._everything_except(
                'allOf', 'oneOf', 'anyOf', 'enum', 'const', 'type'))(['a', 'b']),
            ['a', 'b']
        )

    def test_everything_12(self):
        with self.assertRaises(vol.Invalid):
            opulent_schema.check_and_convert(self._everything_except(
                'allOf', 'oneOf', 'anyOf', 'enum', 'const', 'type'))(['a', 1])

    format_testing_schema = {
        'type': 'object',
        'properties': {
            'datetime': {
                'type': 'string',
                'format': 'date-time',
            },
            'date': {
                'type': 'string',
                'format': 'date',
            },
            'time': {
                'type': 'string',
                'format': 'time',
            },
            'email': {
                'type': 'string',
                'format': 'email',
            },
            'hostname': {
                'type': 'string',
                'format': 'hostname',
            },
            'ipv4': {
                'type': 'string',
                'format': 'ipv4',
            },
            'ipv6': {
                'type': 'string',
                'format': 'ipv6',
            },
            'uri': {
                'type': 'string',
                'format': 'uri',
            }
        }
    }

    def test_format_datetime(self):
        self.assertEqual(
            opulent_schema.exact_check_and_convert(self.format_testing_schema)({
                'datetime': '2012-01-02T12:12:32.99Z'
            }),
            {
                'datetime': '2012-01-02T12:12:32.99Z'
            }
        )

    def test_format_date(self):
        self.assertEqual(
            opulent_schema.exact_check_and_convert(self.format_testing_schema)({
                'date': '2012-01-02'
            }),
            {
                'date': '2012-01-02'
            }
        )

    def test_format_time(self):
        self.assertEqual(
            opulent_schema.exact_check_and_convert(self.format_testing_schema)({
                'time': '12:12:32.99Z'
            }),
            {
                'time': '12:12:32.99Z'
            }
        )

    def test_format_email(self):
        self.assertEqual(
            opulent_schema.exact_check_and_convert(self.format_testing_schema)({
                'email': 'test@example.com'
            }),
            {
                'email': 'test@example.com'
            }
        )

    def test_format_email_wrong(self):
        with self.assertRaises(vol.Invalid):
            opulent_schema.exact_check_and_convert(self.format_testing_schema)({
                'email': 'testaxample.com'
            })

    def test_format_hostname(self):
        self.assertEqual(
            opulent_schema.exact_check_and_convert(self.format_testing_schema)({
                'hostname': 'example.com'
            }),
            {
                'hostname': 'example.com'
            }
        )

    def test_format_hostname_wrong(self):
        with self.assertRaises(vol.Invalid):
            opulent_schema.exact_check_and_convert(self.format_testing_schema)({
                'hostname': 'testaxamp/asd'
            })

    def test_format_ipv4(self):
        self.assertEqual(
            opulent_schema.exact_check_and_convert(self.format_testing_schema)({
                'ipv4': '1.2.3.4'
            }),
            {
                'ipv4': '1.2.3.4'
            }
        )

    def test_format_ipv4_wrong(self):
        with self.assertRaises(vol.Invalid):
            opulent_schema.exact_check_and_convert(self.format_testing_schema)({
                'hostname': '257.0.0.21'
            })

    def test_format_ipv6(self):
        self.assertEqual(
            opulent_schema.exact_check_and_convert(self.format_testing_schema)({
                'ipv6': '2001:db8:a0b:12f0::1'
            }),
            {
                'ipv6': '2001:db8:a0b:12f0::1'
            }
        )

    def test_format_ipv6_wrong(self):
        with self.assertRaises(vol.Invalid):
            opulent_schema.exact_check_and_convert(self.format_testing_schema)({
                'ipv6': 'xxx'
            })

    def test_format_uri(self):
        self.assertEqual(
            opulent_schema.exact_check_and_convert(self.format_testing_schema)({
                'uri': 'ftp://ftp.wikipedia.org'
            }),
            {
                'uri': 'ftp://ftp.wikipedia.org'
            }
        )
