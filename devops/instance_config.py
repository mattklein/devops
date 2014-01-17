import abc
import os
import StringIO

from devops import settings
fab_api = settings.fab_api


class ConfigUnit(object):
    """
    A ConfigUnit represents some configuration that is performed on an instance.
    It's got to have a run() method.
    """
    __metaclass__ = abc.ABCMeta

    def __init__(self, desc):
        super(ConfigUnit, self).__init__()
        self.desc = desc

    def __unicode__(self):
        return unicode(self.desc)

    def __str__(self):
        return unicode(self).encode('utf-8')

    @abc.abstractmethod
    def run(self, host_string):
        pass


class CommandStrs(ConfigUnit):
    """
    A CommandStrs is a ConfigUnit that's comprised of some sequence
    of strings that are to be executed on the instance.
    """
    def __init__(self, desc, commands):
        """Commands is a list of commands (strings) that are executed on an instance."""
        super(CommandStrs, self).__init__(desc)
        self.commands = commands

    def __add__(self, other):
        if not isinstance(other, CommandStrs):
            raise Exception('Invalid to add a %s object to a CommandStrs' % type(other))
        return CommandStrs(desc=self.desc + ' -> ' + other.desc,
                           commands=self.commands + other.commands)

    def run(self, host_string):
        out = StringIO.StringIO()
        with fab_api.settings(host_string=host_string):
            for s in self.commands:
                ret = fab_api.run(s, stdout=out)
                if ret.failed:
                    raise Exception('Fabric run failed: %s' % s)
        return out.getvalue()


class SshKey(object):
    def __init__(self, filename, local_dir):
        super(SshKey, self).__init__()
        self.filename = filename
        self.local_dir = local_dir

    @property
    def local_path(self):
        return os.path.join(self.local_dir, self.filename)


class SshKeyPlacement(ConfigUnit):
    """
    A SshKeyPlacement represents the placement of an SSH key.
    """
    def __init__(self, desc, ssh_key, remote_dir):
        super(SshKeyPlacement, self).__init__(desc)
        self.ssh_key = ssh_key
        self.remote_dir = remote_dir

    def run(self, host_string):
        with fab_api.settings(host_string=host_string):
            cmd = 'mkdir -p %s' % self.remote_dir
            ret = fab_api.run(cmd)
            if ret.failed:
                raise Exception('Fabric run failed: %s' % cmd)
            ret = fab_api.put(self.ssh_key.local_path,
                              os.path.join(self.remote_dir, self.ssh_key.filename),
                              mode=0600)
            if ret.failed:
                raise Exception('Fabric put failed')


class PutFile(ConfigUnit):
    """
    A PutFile represents the "put" of a local file onto a remote instance.  If
    only_if_existing_file_identical_to is passed, the file will only be "put"
    if the existing remote file (i.e., the file we would be replacing) is
    identical to that file.
    """
    def __init__(self, desc, local_dir, local_filename, remote_dir, remote_filename,
                 only_if_existing_file_identical_to=None):
        super(PutFile, self).__init__(desc)
        self.local_dir = local_dir
        self.local_filename = local_filename
        self.remote_dir = remote_dir
        self.remote_filename = remote_filename
        self.only_if_existing_file_identical_to = only_if_existing_file_identical_to

    def run(self, host_string):
        remote_filepath = os.path.join(self.remote_dir, self.remote_filename)
        if self.only_if_existing_file_identical_to:
            with fab_api.settings(host_string=host_string, warn_only=True):
                cmd = 'diff %s %s' % (remote_filepath, self.only_if_existing_file_identical_to)
                ret = fab_api.run(cmd)
                if ret.return_code != 0:
                    raise Exception("Existing file (%s) doesn't match expected file (%s)" % \
                        (remote_filepath, self.only_if_existing_file_identical_to))
        with fab_api.settings(host_string=host_string):
            ret = fab_api.put(os.path.join(self.local_dir, self.local_filename), remote_filepath)
            if ret.failed:
                raise Exception('Fabric put failed')


class RemoteCopyFile(ConfigUnit):
    def __init__(self, desc, source_filepath, dest_filepath,
                 use_sudo=False,
                 only_if_existing_file_identical_to=None):
        super(RemoteCopyFile, self).__init__(desc)
        self.source_filepath = source_filepath
        self.dest_filepath = dest_filepath
        self.use_sudo = use_sudo
        self.only_if_existing_file_identical_to = only_if_existing_file_identical_to

    def run(self, host_string):
        if self.only_if_existing_file_identical_to:
            with fab_api.settings(host_string=host_string, warn_only=True):
                cmd = 'sudo ' if self.use_sudo else '' + \
                      'diff %s %s' % (self.dest_filepath, self.only_if_existing_file_identical_to)
                ret = fab_api.run(cmd)
                if ret.return_code != 0:
                    raise Exception("Existing file (%s) doesn't match expected file (%s)" % \
                        (self.dest_filepath, self.only_if_existing_file_identical_to))
        with fab_api.settings(host_string=host_string):
            ret = fab_api.run('sudo ' if self.use_sudo else '' + \
                              'cp -p %s %s' % (self.source_filepath, self.dest_filepath))
            if ret.failed:
                raise Exception('Fabric put failed')
