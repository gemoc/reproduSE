# Configuration file for jupyterhub.

import os
import subprocess

from traitlets.config import get_config

from dockerspawner import DockerSpawner
from oauthenticator import GitHubOAuthenticator

c = get_config()


def _api_headers(access_token):
    return {
        "Accept": "application/json",
        "User-Agent": "JupyterHub",
        "Authorization": "token {}".format(access_token),
    }

class DiverSEGitHubOAuthenticator(GitHubOAuthenticator):
    admin_organizations = {'diverse-team', 'diverse-project'}

    async def authenticate(self, handler, data=None):
        userdict = await super().authenticate(handler, data)
        if self.admin_organizations:
            for org in self.admin_organizations:
                userdict['admin'] = await self._check_membership_allowed_organizations(org, userdict['name'], userdict['auth_state']['access_token'])
            self.log.info(userdict)

        return userdict

c.JupyterHub.authenticator_class = DiverSEGitHubOAuthenticator
c.GitHubOAuthenticator.oauth_callback_url = f'https://{os.environ["EXTERNAL_HOSTNAME"]}/hub/oauth_callback'

c.JupyterHub.db_url = f'postgresql://{os.environ["POSTGRES_USER"]}' \
        f':{os.environ["POSTGRES_PASSWORD"]}@{os.environ["POSTGRES_HOST"]}' \
        f'/{os.environ["POSTGRES_DB"]}'

c.JupyterHub.spawner_class = DockerSpawner
c.DockerSpawner.image = os.environ['DOCKER_JUPYTER_IMAGE']
c.DockerSpawner.network_name = os.environ['DOCKER_NETWORK_NAME']
c.DockerSpawner.notebook_dir = '/workspace'
c.DockerSpawner.remove = True
c.DockerSpawner.volumes = {os.environ['DOCKER_NOTEBOOKS_HOST_FOLDER'] + '/jupyterhub-user-{username}': '/workspace'}
c.DockerSpawner.post_start_cmd = 'conda env update --name base --file environment.yml'
c.JupyterHub.hub_ip = os.environ['HUB_IP']


def init_workspace(spawner):
    username = spawner.escaped_name
    workspace_folder = os.environ['DOCKER_NOTEBOOKS_FOLDER'] + f'/jupyterhub-user-{username}'
    if not os.path.isdir(workspace_folder):
        os.mkdir(workspace_folder)
    subprocess.check_call(['chown', '-R', '1000:100', workspace_folder])


async def pre_hook(spawner):
    init_workspace(spawner)


async def post_hook(spawner):
    pass


c.Spawner.pre_spawn_hook = pre_hook
c.Spawner.post_stop_hook = post_hook
