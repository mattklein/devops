# Do this in the local environment
# export PYTHONPATH=~/EclipseWorkspaces/misc/devops
# export DEVOPS_SETTINGS_MODULE=locately.settings

from devops import settings
from locately import locately_configs

# This should be done automatically, every time we start up the shell
locately_configs.default_security_group.create_or_update(settings.ec2_conn)

##################

# This is done infrequently -- when we need to change the contents of the AMI
locately_configs.python_ami.create(settings.ec2_conn, locately_configs.SECURITY_GROUP_FOR_AMI_CREATION)

##################

# This is done when we're performing a push
caliper_ami = locately_configs.caliper_ami
