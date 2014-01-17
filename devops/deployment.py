from datetime import datetime
import os
import StringIO

from devops import settings
from devops.instance_config import ConfigUnit

fab_api = settings.fab_api


class CodeDeployment(ConfigUnit):
    """
    A CodeDeployment represents the deployment of some codebase (stored in a given repository).
    """

    # TODO we're going to want to get a handle to all of the deployment units that are on an instance --
    # that represents the code that we've deployed to the instance -- so store something about this in the
    # instance metadata.  So when a deployment unit is applied to an instance, let's store some piece
    # of metadata at that time.

    # TODO may want to store an attribute that represents the "release" of this code deployment --
    # e.g., 2012-12-08, or 1.0.124b, etc.
    def __init__(self, desc, repo, dirname, repo_containing_folder, target_containing_folder,
                 activate_immediately=False):
        super(CodeDeployment, self).__init__(desc)
        self.repo = repo
        self.dirname = dirname
        self.repo_containing_folder = repo_containing_folder
        self.target_containing_folder = target_containing_folder
        self.activate_immediately = activate_immediately
        self.timestamp_suffix = None  # Set when we "run" (create the code directory)

    def activate(self, host_string):
        if not self.timestamp_suffix:
            raise Exception("Can't activate since there's no timestamp_suffix (run() hasn't been run?)")
        out = StringIO.StringIO()
        with fab_api.settings(host_string=host_string):
            cmd = 'cd {} && '.format(self.target_containing_folder) + \
                  'rm -f {} && '.format(self.dirname) + \
                  'ln -s {dirname}_{timestamp} {dirname}'.format(dirname=self.dirname,
                                                                 timestamp=self.timestamp_suffix)
            ret = fab_api.run(cmd, stdout=out)
            if ret.failed:
                raise Exception('Fabric run failed: %s' % cmd)

        return out

    def run(self, host_string):
        self.timestamp_suffix = datetime.now().strftime('%Y%m%d_%H%M%S%f')
        source_path = os.path.join(self.repo_containing_folder, self.dirname)
        dest_path = os.path.join(self.target_containing_folder,
                                 '%s_%s' % (self.dirname, self.timestamp_suffix))
        out1 = StringIO.StringIO()
        with fab_api.settings(host_string=host_string):
            cmd = self.repo.export_cmd(source_path, dest_path)
            ret = fab_api.run(cmd, stdout=out1)
            if ret.failed:
                raise Exception('Fabric run failed: %s' % cmd)

            if self.activate_immediately:
                out2 = self.activate(host_string)
            else:
                out2 = None

        return out1.getvalue() + (('\n' + out2.getvalue()) if out2 and out2.getvalue() else '')


class SvnCodeRepository(object):
    def __init__(self, root_url, ssh_key_placement):
        super(SvnCodeRepository, self).__init__()
        self.root_url = root_url
        self.ssh_key_placement = ssh_key_placement

    def export_cmd(self, source_folder, dest_folder):
        """Returns a command (typically to be run on a remote instance) to export from
        the repository."""
        return 'LC_ALL=C SVN_SSH="ssh -i %s/%s -o StrictHostKeyChecking=no" ' % \
                    (self.ssh_key_placement.remote_dirname, self.ssh_key_placement.ssh_key.filename) + \
               'svn export %s/%s %s' % (self.root_url, source_folder, dest_folder)
