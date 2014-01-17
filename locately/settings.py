# KEYPAIR_NAME = 'locately'
KEYPAIR_NAME = 'mattaws4'
ALL_AVAILABILITY_ZONES = ['us-east-1a', 'us-east-1b', 'us-east-1c', 'us-east-1d', 'us-east-1e']
# AWS_SSH_KEY_FILENAME = '/Users/mattklein/.ssh/locately.pem'
AWS_SSH_KEY_FILENAME = '/Users/mattklein/EclipseWorkspaces/misc/devops/locately/ssh-keys/mattaws4.pem'
USERNAME = 'ubuntu'
CONFIG_ROOT = '/Users/mattklein/EclipseWorkspaces/misc/devops/locately'
# INSTANCE_TYPE_FOR_AMI_CREATION = 'm1.large'  # We've got some compiling to do, so let's use a large instance
INSTANCE_TYPE_FOR_AMI_CREATION = 't1.micro'

# Exposed by looking at our AMIs, or accessing any of our security groups, then getting its owner_id property
# AWS_OWNER_ID = '090997761381'  # For matt@locately.com
AWS_OWNER_ID = '175039608443'  # For mpklein@gmail.com

from fabric import api as fab_api
fab_api.env.key_filename = AWS_SSH_KEY_FILENAME

# TODO should these be made into a proper object?  named AWSCreds?
# from locately.aws_creds import ec2manager
from locately.aws_creds import mpklein

from boto.ec2 import EC2Connection
# ec2_conn = EC2Connection(ec2manager.ACCESS_KEY_ID, ec2manager.SECRET_ACCESS_KEY)
ec2_conn = EC2Connection(mpklein.ACCESS_KEY_ID, mpklein.SECRET_ACCESS_KEY)

DEVOPS_ENV = 'prod'
