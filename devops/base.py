from datetime import datetime
import json
import time

import boto

from devops import settings
from devops import boto_adapt


# TODO
# separate notions: config vs. deployment
# config: security group, AMI, external AMI

SSH_PORT = 22


class SecurityGroupRule(object):
    """See the docs for the Boto API"""
    def __init__(self, ip_protocol, from_port, to_port, cidr_ip=None, src_group_name=None):
        assert (cidr_ip is not None) ^ (src_group_name is not None), \
            'Must instantiate with EITHER cidr_ip or src_group_name, not both'
        self.ip_protocol = ip_protocol
        self.from_port = from_port
        self.to_port = to_port
        self.cidr_ip = cidr_ip
        self.src_group_name = src_group_name

    def __str__(self):
        if self.src_group_name:
            return '%s - %s' % (self.ip_protocol, self.src_group_name)
        else:
            return '%s - %s-%s - %s' % (self.ip_protocol, self.from_port, self.to_port, self.cidr_ip)

    @classmethod
    def rules_from_ec2_rule(cls, ec2_rule):
        return [cls(ec2_rule.ip_protocol, ec2_rule.from_port, ec2_rule.to_port,
                grant.cidr_ip, grant.groupName) for grant in ec2_rule.grants]


def fetch_ec2_security_group(ec2_conn, group_name):
    security_groups = ec2_conn.get_all_security_groups(groupnames=[group_name])
    assert len(security_groups) == 1
    return security_groups[0]


class SecurityGroup(object):
    def __init__(self, name, description, rules):
        self.name = name
        self.description = description
        self.rules = rules

    def __str__(self):
        return self.name

    def create_or_update(self, ec2_conn):

        print 'Creating or updating security group "%s"' % self.name
        some_changes_made = False

        try:
            ec2_groups = ec2_conn.get_all_security_groups(groupnames=[self.name])
        except boto.exception.EC2ResponseError:
            print 'Creating security group "%s"' % self.name
            ec2_group = ec2_conn.create_security_group(name=self.name, description=self.description)
            some_changes_made = True
        else:
            assert len(ec2_groups) == 1
            ec2_group = ec2_groups[0]

        if ec2_group.description != self.description:
            print 'Description on the EC2 group ("%s") doesn\'t match desired description ("%s")' % (ec2_group.description, self.description)
            print "We're not able to change the description via Boto -- maybe someday?"

        # Are any of the rules in this definition not present in the ec2_group?

        for rule in self.rules:
            is_present = False
            for r in ec2_group.rules:
                if rule.ip_protocol == r.ip_protocol \
                and int(rule.from_port) == int(r.from_port) \
                and int(rule.to_port) == int(r.to_port):
                    for g in r.grants:
                        if rule.cidr_ip is not None \
                        and g.cidr_ip == rule.cidr_ip:
                            is_present = True
                            break
                        elif rule.src_group_name is not None \
                        and g.group_id is not None \
                        and g.groupName == rule.src_group_name:
                            # The groupName attribute exists if the group_id is not None
                            is_present = True
                            break

            if not is_present:
                print 'Adding into the EC2 security group: "%s"' % rule
                if rule.src_group_name:
                    src_group = fetch_ec2_security_group(ec2_conn, rule.src_group_name)
                else:
                    src_group = None
                ret = ec2_group.authorize(ip_protocol=rule.ip_protocol,
                                          from_port=rule.from_port,
                                          to_port=rule.to_port,
                                          cidr_ip=rule.cidr_ip,
                                          src_group=src_group)
                assert ret == True
                some_changes_made = True

        # Refresh the EC2 security group (seems necessary)
        ec2_group = fetch_ec2_security_group(ec2_conn, self.name)

        # Are any of the rules in the EC2 security group not present in this definition?

        # In the EC2 security group, the data model is that we can have many grants under a rule
        # So this is actually checking whether any of the EC2 "rule grants" are not present in this definition
        for rule in ec2_group.rules:
            for g in rule.grants:
                is_present = False
                for r in self.rules:
                    if rule.ip_protocol == r.ip_protocol \
                    and int(rule.from_port) == int(r.from_port) \
                    and int(rule.to_port) == int(r.to_port):
                        if g.cidr_ip is not None \
                        and g.cidr_ip == r.cidr_ip:
                            is_present = True
                            break
                        elif g.group_id is not None \
                        and g.groupName == r.src_group_name:
                            # The groupName attribute exists if the group_id is not None
                            is_present = True
                            break

                if not is_present:
                    # The rule in the EC2 security group is NOT present in self.rules -- so
                    # delete the EC2 rule
                    print 'Revoking from the EC2 security group: "%s"' % rule
                    if g.group_id:
                        src_group = fetch_ec2_security_group(ec2_conn, g.groupName)
                    else:
                        src_group = None
                    ec2_group.revoke(ip_protocol=rule.ip_protocol,
                                     from_port=rule.from_port,
                                     to_port=rule.to_port,
                                     cidr_ip=g.cidr_ip,
                                     src_group=src_group)
                    some_changes_made = True

        if not some_changes_made:
            print 'Made no changes for security group "%s"' % self.name

    @property
    def allows_ssh(self):
        """
        Returns True if and only if the security group allows SSH access from the outside -- i.e.,
        from any IP.
        """
        for rule in self.rules:
            if rule.ip_protocol == 'tcp' \
            and rule.from_port <= SSH_PORT <= rule.to_port \
            and rule.cidr_ip == '0.0.0.0/0' \
            and rule.src_group_name is None:
                return True
        return False

    @classmethod
    def from_ec2(cls, ec2_conn, name):
        ec2_group = fetch_ec2_security_group(ec2_conn, name)
        rules = []
        for ec2_rule in ec2_group.rules:
            rules.extend(SecurityGroupRule.rules_from_ec2_rule(ec2_rule))
        security_group = cls(ec2_group.name, ec2_group.description, rules)
        return security_group


class ExternalAMI(object):
    """
    An ExternalAMI is an AMI that we DON'T define, and that
    isn't "managed" by devops.  E.g., a canonical Ubuntu AMI.
    """
    def __init__(self, ami_id):
        self.ami_id = ami_id


class AMI(object):
    def __init__(self, name, vers, env, parent_ami, config_units):
        super(AMI, self).__init__()
        # The "name" of the AMI -- e.g., "Python"
        self.name = name
        # Whenever we change the contents of the AMI (e.g., add a config_unit),
        # we should increment the vers
        self.vers = vers
        self.env = env
        self.parent_ami = parent_ami
        self.config_units = config_units
        # The wrapped AWS AMI
        self.aws_ami = None

    @property
    def ami_id(self):
        return self.aws_ami.id if self.aws_ami else None

    def create(self, ec2_conn, security_group,
               zone=settings.ALL_AVAILABILITY_ZONES[0],  # Any zone is fine
               instance_type=settings.INSTANCE_TYPE_FOR_AMI_CREATION):

        # TODO should verify that the version is greater than the version on
        # any existing AMI for this AMI name
        # TODO should guard against parent_ami being None -- as it might be
        # if, e.g., we haven't created that parent yet

        assert security_group.allows_ssh, 'The security group used for AMI creation ' + \
                                          '("%s") must allow SSH access' % security_group

        print 'Creating new instance -- parent AMI ID: %s, zone: %s, instance type: %s' % \
            (self.parent_ami.ami_id, zone, instance_type)

        instance = boto_adapt.new_instance(ec2_conn, self.parent_ami.ami_id, instance_type,
            zone, user_data='', security_groups=(), ebs_optimized=False)

        tag_name = '%s-ami-template' % self.name
        print 'Adding tag "Name": %s' % tag_name
        instance.add_tag('Name', tag_name)

        for cu in self.config_units:
            print 'Running config unit: %s' % cu
            cu.run('%s@%s' % (settings.USERNAME, instance.public_dns_name))

        desc = '%s_%s' % (self.name, datetime.now().strftime('%Y%m%d'))
        print 'Creating new AMI from instance %s' % instance.id
        new_ami_id = ec2_conn.create_image(instance.id, name=desc, description=desc)

        time.sleep(30)
        print 'Terminating instance %s' % instance.id
        instance.terminate()

        self.aws_ami = ec2_conn.get_image(new_ami_id)
        tags_dict = {'Name': self.name,
                     'devops_name': self.name,
                     'devops_vers': self.vers,
                     'devops_env': self.env}
        for k, v in tags_dict.items():
            print 'Adding tag "%s": %s' % (k, v)
            self.aws_ami.add_tag(k, v)

        return new_ami_id


# TODO
# TODO tie an instance to a security group
class Instance(object):
    def __init__(self, instance_type, instance_name, config_vers, release, application, env, ami_id,
                 ec2_instance_type, zone, security_groups, config_units, ebs_optimized=False):
        super(Instance, self).__init__()
        # E.g., "caliper"
        self.instance_type = instance_type
        # E.g., "caliper-2"
        self.instance_name = instance_name
        # Whenever we change the contents of the instance (e.g., add a config_unit),
        # we should increment the vers
        self.config_vers = config_vers
        # Each "release" that creates a new instance increments this -- e.g., "2012-12-10-a"
        self.release = release
        # For us, this will be "locately".  For larger shops, they may want to make use of this for
        # segmenting their inventory.
        self.application = application
        # E.g., "prod", "test"
        self.env = env
        # The parent AMI that this instance is based on
        self.ami_id = ami_id
        # The AWS instance type (e.g., "c1.medium")
        self.ec2_instance_type = ec2_instance_type
        # The availability zone
        self.zone = zone
        # The security groups
        self.security_groups = security_groups
        # The config units to apply to this instance
        self.config_units = config_units
        # EBS optimized?
        self.ebs_optimized = ebs_optimized
        # The wrapped AWS instance
        self.aws_instance = None

    def create(self, ec2_conn, zone):
        tags_dict = {'Name': self.instance_name,
                     'devops_type': self.instance_type,
                     'devops_vers': self.config_vers,
                     'devops_release': self.release,
                     'devops_applic': self.application,
                     'devops_env': self.env}
        user_data = json.dumps(tags_dict)
        print 'Creating new instance -- instance type: %s, instance name: %s, ' % (self.instance_type, self.instance_name) + \
              'ec2 instance type: %s, AMI ID: %s, zone: %s' % (self.ec2_instance_type, self.ami_id, self.zone)
        instance = boto_adapt.new_instance(ec2_conn, self.ami_id, self.ec2_instance_type, self.zone,
                                           user_data, self.security_groups, ebs_optimized=self.ebs_optimized)
        for k, v in tags_dict.items():
            print 'Adding tag "%s": %s' % (k, v)
            instance.add_tag(k, v)

        # TODO take things up here -- need to emulate the current system's do_setup_instance
