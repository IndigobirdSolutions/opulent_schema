import json
import os
import os.path
import sys

from opulent_schema import collector

if len(sys.argv) < 3:
    sys.exit('usage: python -m opulent_schema DUMP_DIR MODULE_TO_IMPORT MODULE_TO_IMPORT ...')

dir_name = sys.argv[1]
modules = sys.argv[2:]

if not os.path.exists(dir_name):
    os.makedirs(dir_name)

for module_ in modules:
    __import__(module_)

for schema_name, schema in collector.schemas.items():
    with open(os.path.join(dir_name, schema_name), 'w') as file:
        json.dump(schema, file)
