from collections import OrderedDict

schemas = OrderedDict()


def add(name, schema):
    schemas[name] = schema
