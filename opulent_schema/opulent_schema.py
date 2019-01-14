import collections
import copy
import decimal
import numbers
import re
from typing import Dict, Callable, Container

import voluptuous as vol
from opulent_schema import ext_validators


class IntegralNumber:
    def __call__(self, value):
        try:
            if value == int(value):
                return value
        except TypeError:
            pass
        raise vol.Invalid('Not an integral number')


class Not:
    def __init__(self, schema):
        self.validator = schema
        self.schema = vol.Schema(schema)

    def __call__(self, v):
        try:
            self.schema(v)
        except vol.Invalid:
            return v
        raise vol.Invalid('Value passing while it should not')

    def __repr__(self):
        return 'NOT {}'.format(self.schema)


class Equalizer:
    def __init__(self, expected):
        self.expected = expected

    def __call__(self, v):
        try:
            if self.expected == v:
                return v
        except Exception:
            pass
        raise vol.Invalid('Value not equal to: {}'.format(self.expected))

    def __repr__(self):
        return 'Equalizer({})'.format(self.expected)


class In(vol.In):

    def __call__(self, v):
        try:
            return super().__call__(v)
        except vol.InInvalid:
            raise vol.InInvalid('{} not in {}'.format(v, self.container))


def sorted_dict_items(dict_):
    if isinstance(dict_, collections.OrderedDict):
        return dict_.items()
    return sorted(dict_.items(), key=lambda x: x[0])


def is_type(schema, *types):
    if 'type' not in schema:
        return False
    type_ = schema['type']
    if isinstance(type_, str):
        type_ = {type_}
    else:
        type_ = set(type_)

    return type_ <= set(types)


class OneOf:
    """Based on voluptuous.Any"""

    def __init__(self, *validators):
        self.validators = validators
        self._schemas = [vol.Schema(val) for val in validators]

    def __call__(self, v):
        passed = False
        error = None
        sentry = object()
        result = sentry
        for schema in self._schemas:
            try:
                result = schema(v)
            except vol.Invalid as e:
                if error is None or len(e.path) > len(error.path):
                    error = e
                continue
            if passed:
                raise vol.Invalid('more than one validator passes')
            passed = True
        if result is sentry:
            raise vol.Invalid('no valid value found')
        return result

    def __repr__(self):
        return 'OneOf({})'.format(", ".join(repr(v) for v in self.validators))


class ExtendedExactSequence:
    def __init__(self, validators):
        self.validators = validators
        self._schemas = [vol.Schema(val) for val in validators]

    def __call__(self, v):
        ret = v.copy()
        for ind in range(min(len(self._schemas), len(v))):
            ret[ind] = (self._schemas[ind](v[ind]))
        return ret

    def __repr__(self):
        return 'ExtendedExactSequence({})'.format(self.validators)


class FullPropertiesSchema:
    def __init__(self, go, patterns: Dict[str, dict], additional_schema: dict, basic_props: Container[str]):
        self._patterns = patterns
        self.patterns = [(re.compile(k), vol.Schema(go(v))) for k, v in sorted_dict_items(patterns)]
        self._additional_schema = additional_schema
        self.additional_schema = vol.Schema(go(additional_schema))
        self.basic_props = basic_props

    def __call__(self, to_validate: dict):
        result = {}
        for key, value in to_validate.items():
            matched = key in self.basic_props
            for patt, schema in self.patterns:
                if patt.match(key):
                    value = schema(value)
                    matched = True
            if not matched:
                value = self.additional_schema(value)
            result[key] = value
        return result

    def __repr__(self):
        return 'FullPropertiesSchema(patterns={}, additional_schema={}, basic_props={})'.format(
            self._patterns, self._additional_schema, self.basic_props)


class Contains:
    def __init__(self, *elements):
        self.elements = elements

    def __call__(self, value):
        for element in self.elements:
            if element not in value:
                raise vol.Invalid('"{}" not contained'.format(element))

        return value

    def __repr__(self):
        return 'Contains({})'.format(', '.join([str(el) for el in self.elements]))


class MultipleOf:
    def __init__(self, divider):
        self.divider = decimal.Decimal(str(divider))

    def __call__(self, value):
        try:
            quotient = decimal.Decimal(str(value)) / self.divider
            if quotient == int(quotient):
                return value
        except TypeError:
            pass
        raise vol.Invalid('Not a multiple of {}'.format(self.divider))

    def __repr__(self):
        return 'MultipleOf({})'.format(self.divider)


class AnyPass:
    """
    Validates that at least one element of an iterable value if valid against a fixed schema
    """
    def __init__(self, schema):
        self._schema = schema
        self.schema = vol.Schema(schema)

    def __call__(self, value):
        if not value:
            raise vol.Invalid('Empty iterable')
        try:
            for item in value[:-1]:
                self.schema(item)
                return value
        except vol.Invalid:
            pass
        self.schema(value[-1])
        return value

    def __repr__(self):
        return 'AnyPass({})'.format(self._schema)


class Unique:
    """
    Validates that elements of all different, works with unhashable types
    """
    def __call__(self, value):
        for i in range(len(value) - 1):
            for j in range(i+1, len(value)):
                if value[i] == value[j]:
                    raise vol.Invalid('duplicate value: {}'.format(value[i]))

        return value

    def __repr__(self):
        return 'Unique'


class ListSchema:
    """
    Validates that elements in a list (starting from `start`) are valid against a schema
    """
    def __init__(self, schema, start=0):
        self._schema = schema
        self.schema = vol.Schema(schema)
        self.start = start

    def __call__(self, value):
        return vol.Coerce(lambda x: x[:self.start] + [self.schema(v) for v in x[self.start:]])(value)

    def __repr__(self):
        return 'ListSchema({}, start={})'.format(self._schema, self.start)


class LazySchema:
    def __init__(self, converter, json_schema):
        self.converted = None
        self.converter = converter
        self.json_schema = json_schema

    def __call__(self, *args, **kwargs):
        if not self.converted:
            self.converted = self.converter(self.json_schema, lazy=False)
        return self.converted(*args, **kwargs)


class SchemaConverter:
    any_pass = AnyPass
    unique = Unique
    not_ = Not
    multiple_of = MultipleOf
    contains = Contains
    full_properties_schema = FullPropertiesSchema
    extended_exact_sequence = ExtendedExactSequence
    one_of = OneOf
    list_schema = ListSchema

    extra = vol.ALLOW_EXTRA

    type_mapping = {
        'string': str,
        'integer': IntegralNumber(),
        'number': numbers.Number,
        'boolean': bool,
        'null': None,
        'object': dict,
        'array': list,
    }

    @classmethod
    def check_and_convert(cls, json_schema, lazy=True):
        schema_schema(json_schema)
        return cls.convert(json_schema, lazy)

    @classmethod
    def convert(cls, json_schema, lazy=True):
        if lazy:
            return LazySchema(cls.convert, json_schema)
        return vol.Schema(cls.go(json_schema))

    @classmethod
    def go(cls, schema):
        # check with http://json-schema.org/latest/json-schema-validation.html#rfc.section.6.8
        # to see if python regex is fine here
        if not isinstance(schema, dict):
            return
        validators = []
        if schema.get('type'):
            if isinstance(schema['type'], list) and len(schema['type']) > 1:
                validators.append(vol.Any(*[cls.type_mapping[t] for t in schema['type']]))
            elif isinstance(schema['type'], list):
                validators.append(cls.type_mapping[schema['type'][0]])
            else:  # i.e. isinstance(schema['type'], str)
                validators.append(cls.type_mapping[schema['type']])

        validators.extend(cls.object_validators(schema))
        validators.extend(cls.number_validators(schema))
        validators.extend(cls.string_validators(schema))
        validators.extend(cls.array_validators(schema))

        if 'anyOf' in schema:
            validators.append(vol.Any(*[cls.go(subschema) for subschema in schema['anyOf']]))
        if 'allOf' in schema:
            validators.append(vol.All(*[cls.go(subschema) for subschema in schema['allOf']]))
        if 'oneOf' in schema:
            validators.append(cls.one_of(*[cls.go(subschema) for subschema in schema['oneOf']]))

        if 'const' in schema:
            validators.append(Equalizer(schema['const']))

        if 'enum' in schema:
            validators.append(In(schema['enum']))

        if schema.get('not'):
            validators.append(cls.not_(cls.go(schema['not'])))

        if isinstance(schema, TransformedField):
            validators.append(vol.Coerce(schema.get_transformation(), msg='expected {}'.format(type(schema).__name__)))
        if not validators:
            validators = [object]

        return vol.All(*validators) if len(validators) > 1 else validators[0]

    @classmethod
    def object_validators(cls, schema):
        if not {'properties', 'additionalProperties', 'patternProperties', 'maxProperties', 'minProperties', 'required',
                'dependencies', 'propertyNames'} & schema.keys():
            return []

        validators = []
        validators.extend(cls.get_length(schema.get('minProperties'), schema.get('maxProperties')))

        required = set(schema.get('required', []))

        dict_schema = {}
        for prop_name, prop_schema in schema.get('properties', {}).items():
            if prop_name in required:
                required.remove(prop_name)
                key = vol.Required(prop_name)
            else:
                if 'default' in prop_schema:
                    default = copy.deepcopy(prop_schema['default'])
                else:
                    default = vol.UNDEFINED
                key = vol.Optional(prop_name, default=default)
            dict_schema[key] = cls.go(prop_schema)

        dict_schema.update({vol.Required(k): object for k in required})

        if (schema.get('additionalProperties')) and (schema.get('patternProperties')):  # full package
            validators.append(vol.Schema(dict_schema, extra=vol.ALLOW_EXTRA))
            validators.append(
                cls.full_properties_schema(cls.go, schema['patternProperties'], schema['additionalProperties'],
                                           schema.get('properties', {}).keys()))
        elif schema.get('additionalProperties'):
            dict_schema[str] = cls.go(schema['additionalProperties'])
            validators.append(dict_schema)
        elif schema.get('patternProperties'):
            if cls.extra == vol.PREVENT_EXTRA:
                validators.append(vol.Schema(
                    dict.fromkeys(dict_schema.keys() | {vol.Match(p) for p in schema['patternProperties']}, object),
                    extra=vol.PREVENT_EXTRA
                ))
            if dict_schema:
                validators.append(vol.Schema(dict_schema, extra=vol.ALLOW_EXTRA))
            for prop_pattern, prop_schema in sorted_dict_items(schema['patternProperties']):
                validators.append(vol.Schema({vol.Match(prop_pattern): cls.go(prop_schema)}, extra=vol.ALLOW_EXTRA))
        else:  # just the 'properties'
            if dict_schema:
                validators.append(vol.Schema(dict_schema, extra=cls.extra))

        for dep_key, dep_schema in sorted_dict_items(schema.get('dependencies', {})):
            if isinstance(dep_schema, list):
                validators.append(vol.Any(cls.not_(cls.contains(dep_key)), cls.contains(dep_key, *dep_schema),
                                          msg='Dependency "{}" not met'.format(dep_key)))
            else:  # i.e. isinstance(dep_schema, dict)
                validators.append(vol.Any(cls.not_(cls.contains(dep_key)), cls.go(dep_schema),
                                          msg='Dependency "{}" not met'.format(dep_key)))

        if 'propertyNames' in schema:
            validators.append(
                vol.Schema(vol.Msg({cls.go(schema['propertyNames']): object},
                                   'Property name schema {} not fulfilled'.format(schema['propertyNames']))))

        if not is_type(schema, 'object'):
            return [vol.Any(vol.All(dict, *validators), cls.not_(dict))]
        return validators

    @classmethod
    def number_validators(cls, schema):
        if not {'multipleOf', 'maximum', 'exclusiveMaximum', 'minimum', 'exclusiveMinimum'} & schema.keys():
            return []

        validators = []

        min_ = max([schema.get('minimum'), True], [schema.get('exclusiveMinimum'), False],
                   key=lambda n: [float('-inf'), -n[1]] if n[0] is None else [n[0], -n[1]])
        max_ = min([schema.get('maximum'), True], [schema.get('exclusiveMaximum'), False],
                   key=lambda n: [float('inf'), n[1]] if n[0] is None else n)

        if min_[0] is not None or max_[0] is not None:
            validators.append(vol.Range(min=min_[0], min_included=min_[1], max=max_[0], max_included=max_[1]))

        if 'multipleOf' in schema:
            validators.append(cls.multiple_of(schema['multipleOf']))

        if not is_type(schema, 'integer', 'number'):
            return [vol.Any(vol.All(numbers.Number, *validators), cls.not_(numbers.Number))]
        return validators

    @classmethod
    def string_validators(cls, schema):
        if not {'maxLength', 'minLength', 'pattern', 'format'} & schema.keys():
            return []
        validators = []
        validators.extend(cls.get_length(schema.get('minLength'), schema.get('maxLength')))

        if 'pattern' in schema:
            validators.append(vol.Match(schema['pattern']))
        if 'format' in schema:
            validators.append(cls._get_format_validator(schema['format']))

        if not is_type(schema, 'string'):
            return [vol.Any(vol.All(str, *validators), cls.not_(str))]
        return validators

    @classmethod
    def array_validators(cls, schema):
        if not {'items', 'additionalItems', 'maxItems', 'minItems', 'uniqueItems', 'contains'} & schema.keys():
            return []

        validators = []

        validators.extend(cls.get_length(schema.get('minItems'), schema.get('maxItems')))
        if schema.get('uniqueItems'):
            validators.append(cls.unique())

        if 'contains' in schema:
            validators.append(cls.any_pass(cls.go(schema['contains'])))

        if isinstance(schema.get('items'), dict):
            validators.append([cls.go(schema['items'])])
        elif isinstance(schema.get('items'), list):
            validators.append(cls.extended_exact_sequence([cls.go(it) for it in schema['items']]))
            if schema.get('additionalItems'):
                validators.append(cls.list_schema(cls.go(schema['additionalItems']), len(schema['items'])))

        if not is_type(schema, 'array'):
            return [vol.Any(vol.All(list, *validators), cls.not_(list))]
        return validators

    @classmethod
    def get_length(cls, min_, max_):
        if min_ is not None or max_ is not None:
            return [vol.Length(min=min_, max=max_)]
        return []

    @classmethod
    def _get_format_validator(cls, format):
        return {
            'date-time': vol.Datetime(),
            'date': vol.Date(),
            'time': vol.Datetime(format='%H:%M:%S.%fZ'),
            'email': vol.Email(),
            'hostname': ext_validators.Hostname(),
            'ipv4': ext_validators.IP(4),
            'ipv6': ext_validators.IP(6),
            # regex from: https://tools.ietf.org/html/rfc3986#appendix-B
            'uri': vol.Match('^(([^:/?#]+):)?(//([^/?#]*))?([^?#]*)(\?([^#]*))?(#(.*))?'),
        }.get(format, object)


class ExactSchemaConverter(SchemaConverter):
    """`Exact` means, that dicts in validated objects may only have the keys given in `properties`, `required` and
    `petternProperties`. It works the same with `additionalProperties` as `SchemaConverter` does"""
    extra = vol.PREVENT_EXTRA


class TransformedField(dict):

    schema = {}

    def __init__(self, title=None, description=None, default=None, **kwargs):
        if title is not None:
            kwargs['title'] = title
        if description is not None:
            kwargs['description'] = description
        if default is not None:
            kwargs['default'] = default
        super().__init__(**{**self.schema, **kwargs})

    def _transform(self, instance):
        """The only error this method raises should be `vol.Invalid`"""
        raise NotImplementedError

    def get_transformation(self):
        return self._transform
    
    def copy(self):
        return type(self)(**super().copy())


class InLineField(TransformedField):
    def __init__(self, transformation: Callable, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.transformation = transformation

    def get_transformation(self):
        return self.transformation


def make_schema_schema(extra):
    """
    :param extra: one of: vol.ALLOW_EXTRA, vol.PREVENT_EXTRA, vol.REMOVE_EXTRA
    :return:
    """

    schema_dict = {}
    schema_within_schema = vol.Coerce(lambda x: vol.Schema(schema_dict, extra=extra)(x))

    schema_dict.update({
        vol.Optional('multipleOf'): numbers.Number,
        vol.Optional('maximum'): numbers.Number,
        vol.Optional('exclusiveMaximum'): numbers.Number,
        vol.Optional('minimum'): numbers.Number,
        vol.Optional('exclusiveMinimum'): numbers.Number,
        vol.Optional('maxLength'): numbers.Number,
        vol.Optional('minLength'): numbers.Number,
        vol.Optional('pattern'): str,
        vol.Optional('format'): str,
        vol.Optional('items'): vol.Any([schema_within_schema], schema_within_schema),
        vol.Optional('additionalItems'): schema_within_schema,
        vol.Optional('maxItems'): numbers.Number,
        vol.Optional('minItems'): numbers.Number,
        vol.Optional('uniqueItems'): bool,
        vol.Optional('contains'): schema_within_schema,
        vol.Optional('maxProperties'): numbers.Number,
        vol.Optional('minProperties'): numbers.Number,
        vol.Optional('required'): vol.All([str], vol.Unique()),
        vol.Optional('properties'): {str: schema_within_schema},
        vol.Optional('patternProperties'): {str: schema_within_schema},
        vol.Optional('additionalProperties'): schema_within_schema,
        vol.Optional('dependencies'): {str: vol.Any([str], schema_within_schema)},
        vol.Optional('propertyNames'): schema_within_schema,
        vol.Optional('enum'): vol.All(list, Unique(), vol.Length(min=1)),
        vol.Optional('const'): object,
        vol.Optional('type'):
            vol.Any(vol.In(frozenset(SchemaConverter.type_mapping.keys())),
                    [vol.In(frozenset(SchemaConverter.type_mapping.keys()))]),
        vol.Optional('allOf'): vol.All([schema_within_schema], vol.Length(min=1)),
        vol.Optional('anyOf'): vol.All([schema_within_schema], vol.Length(min=1)),
        vol.Optional('oneOf'): vol.All([schema_within_schema], vol.Length(min=1)),
        vol.Optional('not'): schema_within_schema,
        vol.Optional('title'): str,
        vol.Optional('description'): str,
        vol.Optional('default'): object,
        vol.Optional('examples'): list,
    })
    return vol.Schema(schema_dict, extra=extra)


schema_schema = make_schema_schema(vol.PREVENT_EXTRA)

convert = SchemaConverter.convert
exact_convert = ExactSchemaConverter.convert

check_and_convert = SchemaConverter.check_and_convert
exact_check_and_convert = ExactSchemaConverter.check_and_convert
