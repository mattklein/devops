import importlib
import os
import traceback

"""
Expects to find a module name in the environment variable DEVOPS_SETTINGS_MODULE.

Imports the module named by DEVOPS_SETTINGS_MODULE into a variable named "settings".

Then code can access to these settings as devops.settings.

Pretty much just like Django.
"""

settings_module_name = os.environ.get('DEVOPS_SETTINGS_MODULE')
if not settings_module_name:
    raise Exception("Couldn't obtain DEVOPS_SETTINGS_MODULE from the environment")

try:
    settings = importlib.import_module(settings_module_name)
except ImportError:
    traceback.print_exc()
    raise Exception("Couldn't import module %s\n%s" % (settings_module_name, traceback.format_exc()))

from devops.boto_adapt import OpsRegistry
settings.ops_registry = OpsRegistry(settings.ec2_conn, settings.DEVOPS_ENV)
