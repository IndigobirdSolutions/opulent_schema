from collections import OrderedDict

schemas = OrderedDict()


def add(*keys, schema):
    dict_ = schemas
    for key in keys[:-1]:
        if key not in dict_:
            dict_[key] = OrderedDict()
        dict_ = dict_[key]

    dict_[keys[-1]] = schema
