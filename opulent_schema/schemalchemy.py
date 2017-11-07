import datetime
import decimal
import itertools
from typing import Union, Tuple

import delorean
from opulent_schema import InLineField

import sqlalchemy as sa
import sqlalchemy.orm
import sqlalchemy.orm.attributes
import sqlalchemy.dialects
import sqlalchemy.dialects.postgresql
import sqlalchemy.sql.sqltypes

sentry = object()


class Optional(str):
    pass


class Required(str):
    pass


def calculate_reqs(schema):
    if not isinstance(schema, dict):
        return
    if (schema.get('type') == 'object') and ('properties' in schema):
        new_reqs = set()
        for prop_name, prop_schema in schema['properties'].items():
            if not isinstance(prop_name, Optional):
                new_reqs.add(prop_name)
            calculate_reqs(prop_schema)
        if new_reqs:
            schema['required'] = list(new_reqs | set(schema.get('required', [])))

    for subschema in itertools.chain(
        schema.get('anyOf', []),
        schema.get('allOf', []),
        schema.get('oneOf', []),
        schema.get('items', []) if isinstance(schema.get('items', []), list) else [schema.get('items', {})],
    ):
        calculate_reqs(subschema)


sql_type_validators = {
    sa.dialects.postgresql.base.UUID: lambda: {
        'type': 'string',
        'pattern': r'^[0-9,a-f]{8}-[0-9,a-f]{4}-[0-9,a-f]{4}-[0-9,a-f]{4}-[0-9,a-f]{12}$',
    },
    sa.dialects.postgresql.json.JSON: lambda: {},
    sa.sql.sqltypes.Numeric: lambda: InLineField(any_decimal, type='number'),
    sa.sql.sqltypes.TIME: lambda: {
        'type': 'string',
        'pattern': r'^[0-2]?\d:[0-5]\d:[0-5]\d(.\d+)?$',
    },
    sa.sql.sqltypes.BOOLEAN: lambda: {'type': 'boolean'},
}

python_type_validators = {
    int: lambda: {'type': 'integer'},
    str: lambda: {'type': 'string'},
    datetime.datetime: lambda: InLineField(any_time_stamp, type=['string', 'number']),
    datetime.date: lambda: InLineField(any_date, type=['string', 'number']),
}


def any_decimal(value):
    return decimal.Decimal(str(value))


def any_time_stamp(value):
    if value == float('inf') or value == 'infinity':
        return 'infinity'
    if value == float('-inf') or value == '-infinity':
        return '-infinity'

    try:
        return delorean.epoch(float(value)).naive()
    except ValueError:
        pass

    return delorean.parse(value, dayfirst=False).naive()


def any_date(value):
    return any_time_stamp(value).date()


sa_columns = Union[sa.Column, sa.orm.attributes.InstrumentedAttribute]


class ContractMaker:

    def __init__(self, sql_type_validators_=None, python_type_validators_=None):
        self.sql_type_validators_ = {**sql_type_validators, **(sql_type_validators_ or {})}
        self.python_type_validators_ = {**python_type_validators, **(python_type_validators_ or {})}

    def make_contract(self, *columns: Union[sa_columns, 'Properties'], type_='object', **top_schema_info):
        contract = {'type': type_, 'properties': {}}
        for col in columns:
            # if the column is wrapped in OptionalP, then make it optional, otherwise make it required
            key = col.name if getattr(col, 'required', True) else Optional(col.name)
            contract['properties'][key] = self.get_validator(col)

        calculate_reqs(contract)
        return {**contract, **top_schema_info}

    def get_validator(self, column: Union[sa_columns, 'Properties']):

        nullable = column.nullable
        if isinstance(column, Properties):
            schema_info = column.schema_info
            column = column.column
        else:
            schema_info = {}
        sql_type = column.type
        try:
            if type(sql_type) in self.sql_type_validators_:
                validator = self.sql_type_validators_[type(sql_type)]()
            elif sql_type.python_type in self.python_type_validators_:
                validator = self.python_type_validators_[sql_type.python_type]()
            else:
                raise Exception('Unsupported column type: {}'.format(type(sql_type)))
        except NotImplementedError:
            raise Exception('Unsupported column type: {}'.format(type(sql_type)))

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

        if hasattr(sql_type, 'length') and sql_type.length is not None:
            validator['maxLength'] = sql_type.length

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