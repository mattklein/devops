from fabric.contrib.files import contains, sed

from devops import settings
fab_api = settings.fab_api

# The name of the /etc/hosts file on the instance
HOSTS_FILENAME = '/etc/hosts'


class EtcHostsConfigurer(object):
    def __init__(self):
        # Doesn't really need to be a class, but maybe later?
        pass

    def update(self, ssh_host_string, alias, ip, hostname):
        with fab_api.settings(host_string=ssh_host_string):
            # If the hosts file contains the given alias, EDIT the IP and hostname on that line
            if contains(HOSTS_FILENAME, r'.*\s%s$' % alias, escape=False, use_sudo=True):
                sed(HOSTS_FILENAME, r'.*\s%s$' % alias, r'%s %s %s' % (ip, hostname, alias), use_sudo=True)
            # The hosts file does NOT contain the given alias; add a line for it
            else:
                for line in ['',
                    '# Will be auto-edited',
                    '%s %s %s' % (ip, hostname, alias)]:
                    fab_api.sudo('echo "%s" >> %s' % (line, HOSTS_FILENAME))
