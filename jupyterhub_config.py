# Configuration file for jupyterhub.

import json
import os
import re
import shutil
import subprocess
import sys

from traitlets.config import get_config

from dockerspawner import DockerSpawner
from oauthenticator import GitHubOAuthenticator


class DiverSEGitHubOAuthenticator(GitHubOAuthenticator):
    admin_organizations = {'diverse-team', 'diverse-project'}

    async def authenticate(self, handler, data=None):
        userdict = await super().authenticate(handler, data)
        if self.admin_organizations:
            for org in self.admin_organizations:
                userdict['admin'] = await self._check_membership_allowed_organizations(org, userdict['name'], userdict['auth_state']['access_token'])

        return userdict


class ReproduSEDockerSpawner(DockerSpawner):
    def options_from_form(self, formdata):
        options = {}
        for key in ['artifact']:
            if key in formdata:
                options[key] = formdata[key][0]
        return options


c = get_config()

c.JupyterHub.authenticator_class = DiverSEGitHubOAuthenticator
c.GitHubOAuthenticator.oauth_callback_url = f'https://{os.environ["EXTERNAL_HOSTNAME"]}/hub/oauth_callback'

c.JupyterHub.db_url = f'postgresql://{os.environ["POSTGRES_USER"]}' \
        f':{os.environ["POSTGRES_PASSWORD"]}@{os.environ["POSTGRES_HOST"]}' \
        f'/{os.environ["POSTGRES_DB"]}'

c.JupyterHub.spawner_class = ReproduSEDockerSpawner
c.DockerSpawner.image = os.environ['DOCKER_JUPYTER_IMAGE']
c.DockerSpawner.network_name = os.environ['DOCKER_NETWORK_NAME']
c.DockerSpawner.notebook_dir = '/workspace'
c.DockerSpawner.pull_policy = 'always'
c.DockerSpawner.remove = True
c.DockerSpawner.volumes = {os.environ['DOCKER_NOTEBOOKS_HOST_FOLDER'] + '/jupyterhub-user-{username}': '/workspace'}
c.DockerSpawner.post_start_cmd = 'conda env update --name base --file environment.yml'
c.JupyterHub.hub_ip = os.environ['HUB_IP']

c.JupyterHub.load_roles = [
    {
        "name": "jupyterhub-idle-culler-role",
        "scopes": [
            "list:users",
            "read:users:activity",
            "read:servers",
            "delete:servers",
        ],
        "services": ["jupyterhub-idle-culler-service"],
    }
]
c.JupyterHub.services = [
    {
        "name": "jupyterhub-idle-culler-service",
        "command": [
            sys.executable,
            "-m", "jupyterhub_idle_culler",
            "--timeout=3600",
        ],
    }
]


def init_workspace(spawner):
    username = spawner.escaped_name
    workspace_folder = f'{os.environ["DOCKER_NOTEBOOKS_FOLDER"]}/jupyterhub-user-{username}'
    if not os.path.isdir(workspace_folder):
        os.mkdir(workspace_folder)
        subprocess.check_call(['chown', '-R', '1000:100', workspace_folder])

    if 'artifact' in spawner.user_options:
        artifact = spawner.user_options['artifact']
        git_source = ''

        with open('/etc/jupyterhub/artifacts.json', 'r') as f:
            artifacts = json.loads(f.read())
            if artifact in artifacts:
                git_source = artifacts[artifact]
            else:
                raise KeyError(f'Unknown artifact {artifact}')

        repo_name = re.sub('\\.git$', '', git_source.split('/')[-1])
        target_folder = f'{workspace_folder}/{artifact}/{repo_name}'
        spawner.notebook_dir = f'/workspace/{artifact}/{repo_name}'

        if not os.path.isdir(target_folder):
            subprocess.check_call(['git', 'clone', '--recurse-submodules', git_source, target_folder])
            subprocess.check_call(['chown', '-R', '1000:100', target_folder])

    else:
        raise KeyError('Missing artifact')


def clear_workspace(spawner):
    if 'artifact' in spawner.user_options:
        username = spawner.escaped_name
        target_folder = f'{os.environ["DOCKER_NOTEBOOKS_FOLDER"]}/jupyterhub-user-{username}/{spawner.user_options["artifact"]}'
        if os.path.isdir(target_folder):
            shutil.rmtree(target_folder)


async def pre_hook(spawner):
    init_workspace(spawner)


async def post_hook(spawner):
    clear_workspace(spawner)


c.Spawner.pre_spawn_hook = pre_hook
c.Spawner.post_stop_hook = post_hook
