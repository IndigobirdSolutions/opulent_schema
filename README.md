# opulent_schema
opulent_schema is a tool to convert jsonschema to voluptuous (https://github.com/alecthomas/voluptuous) validators. In a sense, it is a jsonschema implementation in python, with a few extensions.
## name
In some dictionaries, "opulent" is a synonym of "voluptuous", hence the name.
## usage
opulent_schema exposes 5 callables that should be sufficient for most everyday applications:
* `schema_schema` - checks if an object (python json-compatible object) is a valid jsonschema, raises en error if it is not. By default an error is raised if the supplied object contains keys not appearing in jsonschema definition. This may not always be desired, but can be helpful in finding typos. If you want less strict validation, generate a new schema: `make_schema_schema(voluptuous.ALLOW_EXTRA)`.

example:
```python
schema_schema({
    'type': 'object',
    'properties': {
        'some_key': {'type': ['string', 'number']}
    },
})
```

* `convert` - takes a jsonschema as only argument and returns a callable that validates instances. Validating an instance may change it (because of defaults), therefore this callable returns the validated (and possibly changed) instance.

example:
```python
convert({
    'type': 'object',
    'properties': {
        'some_key': {'type': ['string', 'number']},
        'key_with_a_default': {'default': 17, 'type': 'number'},
    },
    'required': ['some_key'],
})({
    'some_key': -5,
})
```
returns
```python
{
    'some_key': -5,
    'key_with_a_default': 17
}
```
should the validation fail, an error will be raised
