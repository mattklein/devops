import os

from devops import settings
from devops.base import ExternalAMI, AMI, SecurityGroup, SecurityGroupRule
from devops.deployment import CodeDeployment, SvnCodeRepository
from devops.instance_config import CommandStrs, RemoteCopyFile, SshKey, SshKeyPlacement


ubuntu_inital_packages = CommandStrs(
    desc='Initial Ubuntu aptitude packages',
    commands=['sudo apt-get update',
              'sudo apt-get upgrade --yes',
              'sudo apt-get install sendmail --yes',
              'sudo apt-get install heirloom-mailx --yes',
              'sudo apt-get install emacs --yes',
              'sudo apt-get install collectd --yes',
              'sudo apt-get install gdal-bin --yes',
              'sudo apt-get install libpq-dev --yes',
              'sudo apt-get install sysstat --yes',
              'sudo apt-get install subversion --yes'])

create_deploy_dir = CommandStrs(
    desc='Create /deploy directory',
    commands=['sudo rm -rf /deploy',
              'sudo mkdir /deploy',
              'sudo chown ubuntu:ubuntu /deploy'])

python_27 = CommandStrs(
    desc='Python 2.7',
    # commands=['sudo apt-get install python 2.7 --yes',
    #           'sudo apt-get install python2.7-dev --yes'])
    commands=['sudo apt-get install python2.7-dev --yes'])

opsdev_ssh_key = SshKey(filename='opsdev_dsa',
    local_dir=os.path.join(settings.CONFIG_ROOT, 'ssh-keys'))

restricted_ssh_key = SshKey(filename='restricted_rsa.pub',
    local_dir=os.path.join(settings.CONFIG_ROOT, 'ssh-keys'))

postgres_ssh_key = SshKey(filename='postgres_rsa.pub',
    local_dir=os.path.join(settings.CONFIG_ROOT, 'ssh-keys'))

opsdev_ssh_key_placement = SshKeyPlacement(
    desc='Placement of opsdev SSH key',
    ssh_key=opsdev_ssh_key,
    remote_dir='/deploy/ssh-keys')

restricted_ssh_key_placement = SshKeyPlacement(
    desc='Placement of restricted SSH key',
    ssh_key=restricted_ssh_key,
    remote_dir='/home/restricted/.ssh/authorized_keys')

postgres_ssh_key_placement = SshKeyPlacement(
    desc='Placement of postgres SSH key',
    ssh_key=postgres_ssh_key,
    remote_dir='/home/postgres/.ssh/authorized_keys')

svn_repo = SvnCodeRepository(
    root_url='svn+ssh://ops@dev.locately.com/ebs/svn/two',
    ssh_key_placement=opsdev_ssh_key_placement)

ubuntu_non_apt_packages = CodeDeployment(
    desc='Ubuntu NON-aptitude packages (deployment)',
    repo=svn_repo,
    dirname='ubuntu-config',
    repo_containing_folder='aws',
    target_containing_folder='/home/ubuntu',
    activate_immediately=True)

post_deploy_non_apt_packages = CommandStrs(
    desc='Ubuntu NON-aptitude packages (installation)',
    commands=['find /home/ubuntu/ubuntu-config/packages -name \'*.tar.gz\' -execdir tar xvpf {} \';\'',
              'cd /home/ubuntu/ubuntu-config/packages/setuptools-0.6c11; sudo python ./setup.py install',
              'sudo easy_install virtualenv'])

scipy_dependencies = CommandStrs(
    desc='Dependencies for SciPy',
    commands=['sudo apt-get install libblas-dev libatlas-base-dev gfortran g++ --yes'])

apache_wsgi_installation = \
    CommandStrs(desc='Install Apache',
        commands=['sudo apt-get install apache2 --yes',
                  'sudo apt-get install apache2-dev --yes']) + \
    CommandStrs(desc='Building WSGI against Python 2.7',
        commands=['cd /home/ubuntu/ubuntu-config/packages/mod_wsgi-3.3; ' +
                      './configure --with-apxs=/usr/bin/apxs2 --with-python=/usr/bin/python2.7',
                  'cd /home/ubuntu/ubuntu-config/packages/mod_wsgi-3.3; ' +
                      'make; sudo make install'])

add_wheezy_to_apt_sources = CommandStrs(
    desc='Add Wheezy to apt sources',
    # As of 9/26/2012, we can only get PostGIS 9.1 in Wheezy (not Squeeze, the current stable release)
    # Wheezy is the current Ubuntu "test" release; has been frozen as of 6/30/2012
    # We could get PostgreSQL 9.1 in squeeze-backports, but not PostGIS 9.1
    # So here, we add Wheezy to the Debian sources
    commands=['echo "deb http://ftp.debian.org/debian wheezy main" | sudo tee /etc/apt/sources.list.d/wheezy.list',
              'echo "deb http://security.debian.org wheezy/updates main" | sudo tee /etc/apt/sources.list.d/wheezy-sec.list',
              # These two get around the "GPG error NO_PUBKEY" error for the wheezy site
              'gpg --keyserver pgpkeys.mit.edu --recv-key AED4B06F473041FA',
              'gpg -a --export AED4B06F473041FA | sudo apt-key add -',
              'sudo apt-get update'])

remove_wheezy_from_apt_sources = CommandStrs(
    desc='Remove Wheezy from apt sources',
    # Just so that we don't unknowningly install a package from Wheezy (we only want it for PostgreSQL 9.1)
    commands=['sudo rm /etc/apt/sources.list.d/wheezy.list',
              'sudo rm /etc/apt/sources.list.d/wheezy-sec.list',
              'sudo apt-get update'])

# We add wheezy because we need at least 1.3.4 of pgbouncer (to work with PostgreSQL 9.1)
# install_pgbouncer = \
#     add_wheezy_to_apt_sources + \
#     CommandStrs(desc='Install pgbouncer',
#         commands=['sudo apt-get install pgbouncer --yes']) + \
#     remove_wheezy_from_apt_sources

install_pgbouncer = \
    CommandStrs(desc='Install pgbouncer',
        commands=['sudo apt-get install pgbouncer --yes'])

create_virtualenv = CommandStrs(
    desc='Create Python virtualenv',
    commands=['mkdir /deploy/pythonenvs; cd /home/ubuntu/ubuntu-config/pythonenvs; ' +
                  './create-virtualenv.sh /deploy/pythonenvs/siphonenv'])

# For the time being, this has to be done WITH wheezy having been added to apt_sources
# If we didn't need wheezy, this could have been done above with the rest of the packages
install_postgresql_client = \
    add_wheezy_to_apt_sources + \
    CommandStrs(desc='PostgreSQL client',
        commands=['sudo apt-get install postgresql-client-9.1 --yes']) + \
    remove_wheezy_from_apt_sources

remove_ubuntu_non_apt_packages = CommandStrs(
    desc='Removing ubuntu-config directory',
    commands=['sudo rm -rf /home/ubuntu/ubuntu-config'])

create_restricted_user = CommandStrs(
    desc='Create a restricted user',
    # We create a user with username "restricted" in the "ubuntu" group.  This user should NOT
    # have sudo access to root.  It should have access to the "ubuntu" group so that it can,
    # e.g., access files owned/created by the "ubuntu" user.
    commands=['sudo useradd restricted -g ubuntu --create-home',
              'sudo mkdir /home/restricted/.ssh',
              'sudo chmod 775 /home/restricted/.ssh',
              'sudo chown restricted:ubuntu /home/restricted/.ssh'])

complete_ssh_setup_for_restricted_user = CommandStrs(
    desc='Complete SSH setup for restricted user',
    commands=['sudo chmod 755 /home/restricted/.ssh',
              'sudo chown restricted:ubuntu /home/restricted/.ssh/authorized_keys',
              'sudo chmod 600 /home/restricted/.ssh/authorized_keys'])

create_home_dir_for_postgres = CommandStrs(
    desc='Create home directory for postgres',
    commands=['sudo mkdir /home/postgres',
              'sudo chown postgres:postgres /home/postgres',
              # In order to perform "usermod", no processes can be running that are owned by postgres
              'sudo service pgbouncer stop',
              'sudo service postgresql stop',
              'sudo usermod -d /home/postgres postgres',
              'sudo service postgresql start',
              'sudo service pgbouncer start',
              'sudo mkdir /home/postgres/.ssh',
              'sudo chmod 777 /home/postgres/.ssh'])

complete_ssh_setup_for_postgres = CommandStrs(
    desc='Complete SSH setup for postgres user',
    commands=['sudo chown postgres:postgres /home/postgres/.ssh/authorized_keys',
              'sudo chmod 600 /home/postgres/.ssh/authorized_keys',
              'sudo chmod 700 /home/postgres/.ssh',
              'sudo chown postgres:postgres /home/postgres/.ssh'])

aws_deploy_dir = CodeDeployment(
    desc='aws/deploy directory',
    repo=svn_repo,
    dirname='deploy',
    repo_containing_folder='aws',
    target_containing_folder='/deploy',
    activate_immediately=True)

# TODO note that this also copies pysrc/aws-keys, which we do NOT
# want to do; move this outside of the /deploy directory (we'll copy
# the desired keys one-by-one later)
aws_pysrc_dir = CodeDeployment(
    desc='aws/pysrc directory',
    repo=svn_repo,
    dirname='pysrc',
    repo_containing_folder='aws',
    target_containing_folder='/deploy',
    activate_immediately=True)

copy_sysctl_conf_db = RemoteCopyFile(
    desc='Copy sysctl.conf (DB version) into place',
    source_filepath='/deploy/conf/os/sysctl_conf_db',
    dest_filepath='/etc/sysctl.conf',
    use_sudo=True,
    only_if_existing_file_identical_to='/deploy/conf/os/sysctl_conf_BASE')

copy_sysctl_conf_other = RemoteCopyFile(
    desc='Copy sysctl.conf (other version) into place',
    source_filepath='/deploy/conf/os/sysctl_conf_other',
    dest_filepath='/etc/sysctl.conf',
    use_sudo=True,
    only_if_existing_file_identical_to='/deploy/conf/os/sysctl_conf_BASE')

activate_sysctl_conf = CommandStrs(
    desc='Activate sysctl.conf',
    commands=['sudo /sbin/sysctl -p /etc/sysctl.conf'])

########

default_security_group = SecurityGroup(
    name='default',
    description='default group',
    rules=[SecurityGroupRule('tcp', 22, 22, '0.0.0.0/0')])

my_security_group = SecurityGroup(
    name='mine',
    description='mine',
    rules=[SecurityGroupRule('tcp', 22, 22, '0.0.0.0/0'),
           SecurityGroupRule('tcp', 23, 23, '0.0.0.0/0'),
           SecurityGroupRule('tcp', 22, 22, src_group_name='mine'),
           SecurityGroupRule('tcp', 26, 26, src_group_name='mine')])

# second_security_group = SecurityGroup(
#     name='second',
#     description='second',
#     rules=[SecurityGroupRule(src_group_name='mine')])

canonical_ubuntu_ami = ExternalAMI(
    # Ubuntu 11.04, 64 bit, 2012-07-23 release
    # ami_id='ami-699f3600')
    # Ubuntu 12.04, 64 bit, 2013-12-05 release
    ami_id='ami-0568456c')

SECURITY_GROUP_FOR_AMI_CREATION = default_security_group

python_ami = AMI(
    name='Python',
    vers='0.1',
    env=settings.DEVOPS_ENV,
    parent_ami=canonical_ubuntu_ami,
    config_units=[ubuntu_inital_packages,
                  create_deploy_dir,
                  python_27,
                  opsdev_ssh_key_placement,
                  ubuntu_non_apt_packages,
                  post_deploy_non_apt_packages,
                  scipy_dependencies,
                  apache_wsgi_installation,
                  install_pgbouncer,
                  create_virtualenv,
                  install_postgresql_client,
                  remove_ubuntu_non_apt_packages])

########

caliper_ami = AMI(
    name='caliper',
    vers='0.1',
    env=settings.DEVOPS_ENV,
    parent_ami=settings.ops_registry.get_ami('Python'),
    config_units=[aws_deploy_dir,
                  aws_pysrc_dir,
                  create_restricted_user,
                  restricted_ssh_key_placement,
                  complete_ssh_setup_for_restricted_user,
                  create_home_dir_for_postgres,
                  postgres_ssh_key_placement,
                  complete_ssh_setup_for_postgres,
                  copy_sysctl_conf_other,
                  activate_sysctl_conf,
                  # TODO take things up here -- configuring dbhost
                  # How do we get the registry of hosts?
                  ])

# TODO!
# we need to set this, in part, dynamically!  based on the ops-registry
"""
caliper = Instance(
    instance_type='caliper',
    instance_name='caliper-1',
    config_vers='0.1',
    release=,
    application='locately',
    env=settings.DEVOPS_ENV,
    ami_id=,
    ec2_instance_type=,
    zone=,
    security_groups=,
    config_units=,
    ebs_optimized=False)
"""

# we allocate calipers in units of 2
# one of them goes in zone X, one in zone Y
