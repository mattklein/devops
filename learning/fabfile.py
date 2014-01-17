from fabric.api import local, run, env, settings
from fabric import operations as fab_ops


env.hosts = ['ubuntu@siphon-1', 'ubuntu@siphon-2']
env.key_filename = '/Users/mattklein/.ssh/locately.pem'


def hello():
    local('echo Hello world')


def hello2():
    run('echo hello world')


def open_shell():
    fab_ops.open_shell()

with settings(host_string='ubuntu@siphon-1',
              key_filename='/Users/mattklein/.ssh/locately.pem'):
    run('ls -l')
    pass

# More global way of setting environment
env['host_string'] = 'ubuntu@siphon-1'
key_filename = '/Users/mattklein/.ssh/locately.pem'
