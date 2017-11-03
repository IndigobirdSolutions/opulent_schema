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

* `exact_convert` - same as `convert`, but the returned callable will raise validation errors if dictionaries (json objects) in the validated instance contain keys not declared in `properties` or `required`, but only if `additionalProperties` is not defined
* `check_and_convert` and `exact_check_and_convert` - first schecks the provided jsonschema with `schema_schema` and then returns the same validators as `convert` and `exact_convert`, respectively.

## patterns
opulent_schema interprets strings provided in `pattern` and `patternProperties` as python regexes, which is not entirely correct. We will see how to solve this problem in the future

## additional transformations
opulent_schema extends jsonschema by giving the user the ability to add additional, arbitrary validations and transformations. This is done by using subclasses of `TransformedFiled` (for example `InLineField`) in the input jsonschema. `TransformedField` is an abstract subsclass of `dict` with one method that needs to be defined: `_transform`. If any part of the input jsonschema is a `TransformedField`, after validating the instance the `_transform` method is called, with it as an argument, possibly raising an exception and returning a new instance value to use. An example would be timestamps stored in json as integers. In python code, one typically wants to deal with `dateitme.datetime` objects. Converting ints to `dateitme.datetime` after every validation would cause a lot repeated code. Here's how you can avoid that with `InLineField`:
```python
convert({
    'type': 'object',
    'properties': {
        'timestamp': InLineField(datetime.datetime.fromtimestamp, **{'type': 'integer'}),
    },
})({
    'timestamp': 4
})
```
will return
```python 
datetime.datetime(1970, 1, 1, 0, 0, 4)
```
