# type: ignore[assignment] # flake8: max-line-length[99]
# Configuration file for jupyterhub.

import json
import os
import re
import shutil
import subprocess
import sys

from jupyterhub.handlers.base import BaseHandler
from tornado.web import authenticated
from traitlets.config import get_config

from dockerspawner import DockerSpawner
from oauthenticator import GitHubOAuthenticator


class DiverSEGitHubOAuthenticator(GitHubOAuthenticator):
    admin_organizations = {'diverse-team', 'diverse-project', 'gemoc'}

    async def authenticate(self, handler, data=None):
        userdict = await super().authenticate(handler, data)
        userdict['admin'] = False
        if self.admin_organizations:
            for org in self.admin_organizations:
                userdict['admin'] |= await self._check_membership_allowed_organizations(
                    org, userdict['name'],
                    userdict['auth_state']['access_token']
                )

        return userdict


class ReproduSEDockerSpawner(DockerSpawner):
    def options_from_form(self, formdata):
        options = {}
        for key in ['artifact', 'lab']:
            if key in formdata:
                options[key] = formdata[key][0]
        return options


c = get_config()

c.JupyterHub.allow_named_servers = True
c.JupyterHub.db_url = ('postgresql://'
                       f'{os.environ["POSTGRES_USER"]}:{os.environ["POSTGRES_PASSWORD"]}@'
                       f'{os.environ["POSTGRES_HOST"]}/{os.environ["POSTGRES_DB"]}')
c.JupyterHub.hub_ip = os.environ['HUB_IP']
c.JupyterHub.template_paths = ['/etc/jupyterhub/templates/']

c.JupyterHub.authenticator_class = DiverSEGitHubOAuthenticator
c.GitHubOAuthenticator.oauth_callback_url = (f'https://{os.environ["EXTERNAL_HOSTNAME"]}'
                                             '/hub/oauth_callback')

c.JupyterHub.spawner_class = ReproduSEDockerSpawner
c.DockerSpawner.image = os.environ['DOCKER_JUPYTER_IMAGE']
c.DockerSpawner.network_name = os.environ['DOCKER_NETWORK_NAME']
c.DockerSpawner.notebook_dir = '/workspace'
c.DockerSpawner.pull_policy = 'always'
c.DockerSpawner.remove = True
c.DockerSpawner.volumes = {
    f'{os.environ["DOCKER_NOTEBOOKS_HOST_FOLDER"]}/jupyterhub-user-{{username}}': '/workspace'
}
c.DockerSpawner.post_start_cmd = 'conda env update --name base --file environment.yml'

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
c.JupyterHub.tornado_settings = {
    'cookie_options': {'SameSite': 'None', 'Secure': True},
    'headers': {
        'Content-Security-Policy': 'frame-ancestors self *',
        'Access-Control-Allow-Origin': '*'
    }
}
c.Spawner.args = [("--NotebookApp.tornado_settings={"
                   "'cookie_options': {'SameSite': 'None', 'Secure': True},"
                   "'headers': {"
                   "'Content-Security-Policy': 'frame-ancestors self *',"
                   "'Access-Control-Allow-Origin': '*'"
                   "}}"),
                  "--NotebookApp.disable_check_xsrf=True"]


def init_workspace(spawner):
    username = spawner.escaped_name
    workspace_folder = f'{os.environ["DOCKER_NOTEBOOKS_FOLDER"]}/jupyterhub-user-{username}'
    if not os.path.isdir(workspace_folder):
        os.mkdir(workspace_folder)
        subprocess.check_call(['chown', '-R', '1000:100', workspace_folder])

    git_source = ''
    notebook_file = ''
    if 'artifact' in spawner.user_options:
        artifact = spawner.user_options['artifact']

        with open('/etc/jupyterhub/artifacts.json', 'r') as f:
            artifacts = json.loads(f.read())
            if artifact in artifacts:
                git_source = artifacts[artifact]['url']
                notebook_file = artifacts[artifact]['file']
            else:
                raise KeyError(f'Unknown artifact {artifact}')

        repo_name = re.sub('\\.git$', '', git_source.split('/')[-1])
        target_folder = f'{workspace_folder}/{artifact}/{repo_name}'
        spawner.notebook_dir = f'/workspace/{artifact}/{repo_name}'

        if not os.path.isdir(target_folder):
            subprocess.check_call(['git', 'clone', '--recurse-submodules',
                                   git_source, target_folder])
            subprocess.check_call(['chown', '-R', '1000:100', target_folder])

    else:
        raise KeyError('Missing artifact')

    if 'lab' in spawner.user_options:
        lab = spawner.user_options['lab']
        if lab == '0':
            spawner.environment['JUPYTERHUB_SINGLEUSER_APP'] = 'notebook.notebookapp.NotebookApp'
            spawner.args.append(f'--NotebookApp.default_url=/notebooks/{notebook_file}')


def clear_workspace(spawner):
    if 'artifact' in spawner.user_options:
        username = spawner.escaped_name
        target_folder = (f'{os.environ["DOCKER_NOTEBOOKS_FOLDER"]}/jupyterhub-user-{username}'
                         f'/{spawner.user_options["artifact"]}')
        if os.path.isdir(target_folder):
            shutil.rmtree(target_folder)


async def pre_hook(spawner):
    init_workspace(spawner)


async def post_hook(spawner):
    clear_workspace(spawner)


c.Spawner.pre_spawn_hook = pre_hook
c.Spawner.post_stop_hook = post_hook


class ArtifactHandler(BaseHandler):
    @authenticated
    async def get(self, artifact):
        self.log.info(self.request.query)
        user = await self.get_current_user()
        lab = self.get_argument('lab', default='1')

        self.log.info(f'/spawn/{user.escaped_name}/{artifact}?artifact={artifact}&lab={lab}')
        return self.redirect(
            f'/spawn/{user.escaped_name}/{artifact}?artifact={artifact}&lab={lab}'
        )


c.JupyterHub.extra_handlers.append((r'/artifact/(?P<artifact>[^/]+)/', ArtifactHandler, {}))
