import collections
import datetime
import decimal
import itertools
from typing import Union

import delorean
from opulent_schema import TransformedField, sorted_dict_items

import sqlalchemy as sa
import sqlalchemy.orm
import sqlalchemy.orm.attributes
import sqlalchemy.dialects
import sqlalchemy.dialects.postgresql
import sqlalchemy.sql.sqltypes

sentry = object()


class AlmostStr(type):
    """This metaclass is necessary, so that `voluptuous` will not distinguish `Optional` and `Required` classes defined
    below from plain old strings"""
    def __eq__(self, other):
        return str == other

    def __hash__(self):
        return hash(str)


class Optional(str, metaclass=AlmostStr):
    pass


class Required(str, metaclass=AlmostStr):
    pass


def calculate_reqs(schema):
    if not isinstance(schema, dict):
        return
    if 'properties' in schema:
        new_reqs = collections.OrderedDict.fromkeys(schema.get('required', []))  # we are using this as an OrderedSet,
        # so all values are None and are irrelevant
        for prop_name, prop_schema in sorted_dict_items(schema['properties']):
            if not isinstance(prop_name, Optional):
                new_reqs[prop_name] = None
            calculate_reqs(prop_schema)
        if new_reqs:
            schema['required'] = list(new_reqs.keys())

    for subschema in itertools.chain(
        schema.get('anyOf', []),
        schema.get('allOf', []),
        schema.get('oneOf', []),
        schema.get('items', []) if isinstance(schema.get('items', []), list) else [schema.get('items', {})],
    ):
        calculate_reqs(subschema)


def uuid_validator(*a):
    return {
        'type': 'string',
        'pattern': r'^[0-9,a-f]{8}-[0-9,a-f]{4}-[0-9,a-f]{4}-[0-9,a-f]{4}-[0-9,a-f]{12}$',
    }


def any_time_stamp(value):
    if value == float('inf') or (isinstance(value, str) and value.lower() == 'infinity'):
        return 'infinity'
    if value == float('-inf') or (isinstance(value, str) and value.lower() == '-infinity'):
        return '-infinity'

    try:
        return delorean.epoch(float(value)).shift('UTC')._dt.replace(tzinfo=None)
    except ValueError:
        pass

    return delorean.parse(value, dayfirst=False).shift('UTC')._dt.replace(tzinfo=None)


class AnyTimeStamp(TransformedField):
    def _transform(self, instance):
        return any_time_stamp(instance)


class AnyDate(TransformedField):
    def _transform(self, instance):
        return any_time_stamp(instance).date()


class AnyDecimal(TransformedField):
    def _transform(self, instance):
        return decimal.Decimal(str(instance))


sql_type_validators = {
    sa.dialects.postgresql.base.UUID: uuid_validator,
    sqlalchemy.JSON: lambda col: {},
    sa.sql.sqltypes.Numeric: lambda col: AnyDecimal(type='number'),
    sa.sql.sqltypes.TIME: lambda col: {
        'type': 'string',
        'pattern': r'^[0-2]?\d:[0-5]\d:[0-5]\d(.\d+)?$',
    },
    sa.sql.sqltypes.BOOLEAN: lambda col: {'type': 'boolean'},
    sqlalchemy.sql.sqltypes.Enum: lambda col: {'enum': [el.value for el in col.type.python_type]},
}


def str_validator(col):
    validator = {'type': 'string'}
    if hasattr(col.type, 'length') and col.type.length is not None:
        validator['maxLength'] = col.type.length
    return validator


python_type_validators = {
    int: lambda col: {'type': 'integer'},
    str: str_validator,
    datetime.datetime: lambda col: AnyTimeStamp(type=['string', 'number']),
    datetime.date: lambda col: AnyDate(type=['string', 'number']),
}

sa_columns = Union[sa.Column, sa.orm.attributes.InstrumentedAttribute]


class ContractMaker:

    def __init__(self, sql_type_validators_=None, python_type_validators_=None):
        self.sql_type_validators_ = {**sql_type_validators, **(sql_type_validators_ or {})}
        self.python_type_validators_ = {**python_type_validators, **(python_type_validators_ or {})}

    def make_contract(self, *columns: Union[sa_columns, 'Properties'], type_='object', add_props=None,
                      **top_schema_info):
        properties = collections.OrderedDict()
        for col in columns:
            # if the column is wrapped in OptionalP, then make it optional, otherwise make it required
            key = col.name if getattr(col, 'required', True) else Optional(col.name)
            properties[key] = self.get_validator(col)

        if add_props:
            for key, value in sorted_dict_items(add_props):
                properties[key] = value

        contract = {'type': type_, 'properties': properties}

        calculate_reqs(contract)
        return {**contract, **top_schema_info}

    def _determine_validator(self, column):
        sql_type = column.type
        try:
            for type_ in type(sql_type).__mro__:
                if type_ in self.sql_type_validators_:
                    return self.sql_type_validators_[type_](column)
            for type_ in sql_type.python_type.__mro__:
                if type_ in self.python_type_validators_:
                    return self.python_type_validators_[type_](column)
        except NotImplementedError:
            pass
        raise Exception('Unsupported column type: {}'.format(type(sql_type)))

    def get_validator(self, column: Union[sa_columns, 'Properties']):

        nullable = column.nullable
        if isinstance(column, Properties):
            schema_info = column.schema_info
            column = column.column
        else:
            schema_info = {}

        validator = self._determine_validator(column)

        if nullable:
            if 'type' in validator:
                if isinstance(validator['type'], str):
                    if validator['type'] == 'null':
                        pass
                    else:
                        validator['type'] = ['null', validator['type']]
                else:  # i.e. list
                    if 'null' in validator['type']:
                        pass
                    else:
                        validator['type'] = ['null'] + validator['type']
            else:
                validator = {'anyOf': [{'type': 'null'}, validator]}

        validator.update(schema_info)

        return validator


class Properties:
    required = True

    @property
    def name(self):
        return self.column.name

    def __init__(self, column: sa_columns,
                 title=sentry, description=sentry, default=sentry, nullable=None, **kwargs):
        if nullable is None:
            nullable = column.nullable
        self.nullable = nullable
        self.column = column
        for kw, kw_name in[
            (title, 'title'),
            (description, 'description'),
            (default, 'default'),
        ]:
            if kw is not sentry:
                kwargs[kw_name] = kw
        self.schema_info = kwargs


class RequiredP(Properties):
    """Just an alias"""


class OptionalP(Properties):
    required = False


contract_maker = ContractMaker()
make_contract = contract_maker.make_contract
get_validator = contract_maker.get_validator
