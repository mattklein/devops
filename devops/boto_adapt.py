from collections import defaultdict
import time

from devops import settings
fab_api = settings.fab_api


def new_instance(ec2_conn, ami_id, instance_type, zone, user_data, security_groups=[], ebs_optimized=False):
    reservation = ec2_conn.run_instances(image_id=ami_id,
                                         instance_type=instance_type,
                                         security_groups=security_groups,
                                         placement=zone,
                                         key_name=settings.KEYPAIR_NAME,
                                         user_data=user_data,
                                         ebs_optimized=ebs_optimized)
    time.sleep(5)
    instance = reservation.instances[0]
    for i in range(1, 21):
        status = instance.update()
        if status == 'pending':
            print 'Instance is pending (attempt %d)...' % i
            time.sleep(5)
            continue
        else:
            break

    if status != 'running':
        raise Exception("Couldn't start instance (status: %s)" % status)

    print 'Instance is running'

    success = False
    for i in range(1, 21):
        with fab_api.settings(host_string='%s@%s' % (settings.USERNAME, instance.public_dns_name)):
            try:
                res = fab_api.run('echo "Hello world"')
                if res.failed:
                    raise Exception()
                success = True
            except:
                print "Couldn't run command on instance (attempt %d)..." % i
                time.sleep(5)
                continue
            else:
                break

    if not success:
        raise Exception("Couldn't run command on instance")

    print 'Able to run command on instance.  Moving on...'
    time.sleep(5)

    print 'Removing existing known_hosts entry for %s and %s' % \
        (instance.public_dns_name, instance.ip_address)
    fab_api.local('ssh-keygen -R %s -R %s' % (instance.public_dns_name, instance.ip_address))

    return instance


class OpsRegistry(object):
    def __init__(self, ec2_conn, env):
        self.ec2_conn = ec2_conn
        self.env = env
        self._ami_dict = None  # Lazily loaded and cached
        self._instances = None  # Lazily loaded and cached

    def _get_amis(self):
        """
        Sets _ami_dict to a dict of AMIs, keyed by AMI name.  The result of each dict
        entry is a LIST of AMIs that have that name (because we don't know that there's
        one and only one AMI with that name).  The list is sorted by (devops_vers, name)
        descending -- the intent being that the most current AMI is first in the list.
        """
        if self.env:
            filters = {'tag:devops_env': self.env}
        else:
            filters = None
        amis = self.ec2_conn.get_all_images(owners=[settings.AWS_OWNER_ID], filters=filters)
        d = defaultdict(list)
        for ami in amis:
            d[ami.tags['Name']].append(ami)
        sorted_d = {}
        for k, v in d.items():
            sorted_d[k] = sorted(d[k], key=lambda x: (x.tags['devops_vers'], x.name),
                                 reverse=True)
        return sorted_d

    def _get_instances(self):
        if self.env:
            filters = {'tag:devops_env': self.env}
        else:
            filters = None
        reservs = self.ec2_conn.get_all_instances(filters=filters)
        instances = []
        for r in reservs:
            instances.extend(r.instances)
        return instances

    def get_ami(self, name, version='latest', force_refresh=False):
        """version could be: 'latest', or a string that's interpreted as the version number, or a
        NEGATIVE integer that's interpreted as the number of versions BEFORE the latest version"""
        if not self._ami_dict or force_refresh:
            self._ami_dict = self._get_amis()
        amis = self._ami_dict.get(name)
        if version == 'latest':
            return amis[0]
        else:
            try:
                version = int(version)  # Raises ValueError if version isn't an int
                if version >= 0:
                    raise ValueError
                offset = -version
                # If they're asking for a version that's MORE NEGATIVE than there are versions
                # for, act as if they asked for the most possible negative version
                return amis[min(offset, len(amis) - 1)]
            except ValueError:
                # version isn't a negative integer, so interpret it as an actual devops_vers
                for ami in amis:
                    if ami.tags['devops_vers'] == version:
                        return ami
                return None

    def get_registered_hosts(self, force_refresh=False):
        """Returns a dict of <registered_host_alias>: <instance_id>"""
        if not self._instances or force_refresh:
            self._instances = self._get_instances()
        d = {}
        for i in self._instances:
            host_alias = i.tags.get('registered_host_alias')
            if host_alias:
                d[host_alias] = i.id
        return d
