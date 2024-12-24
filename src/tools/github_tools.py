import os
import json
from typing import Optional, List
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from phi.tools import Toolkit
from phi.utils.log import logger


load_dotenv()
try:
    from github import Github, GithubException, Auth
except ImportError:
    raise ImportError('`PyGithub` not installed. Please install using `pip install PyGithub`')


class GithubCommitStats(Toolkit):
    def __init__(self, access_token: Optional[str] = None, base_url: Optional[str] = None):
        super().__init__(name='github_commit_stats')
        self.access_token = access_token or os.getenv('GITHUB_ACCESS_TOKEN')
        self.base_url = base_url
        self.g = self._authenticate()

        self.register(self.get_monthly_commit_count)

    def _authenticate(self):
        'Authenticate with GitHub using the provided access token.'
        auth = Auth.Token(self.access_token)
        if self.base_url:
            logger.debug(f'Authenticating with GitHub Enterprise at {self.base_url}')
            return Github(base_url=self.base_url, auth=auth)
        else:
            logger.debug('Authenticating with public GitHub')
            return Github(auth=auth)

    def get_monthly_commit_count(self, repo_name: str) -> str:
        'Retrieves the number of commits made to a repository in the past month.\n\n        Args:\n            repo_name (str): The full name of the repository (e.g., owner/repo).\n\n        Returns:\n           A JSON-formatted string containing the commit count for the last month.'
        logger.debug(f'Getting monthly commit count for repository: {repo_name}')
        try:
            repo = self.g.get_repo(repo_name)

            now = datetime.now(timezone.utc)
            one_month_ago = now - timedelta(days=30)

            commits = repo.get_commits(since=one_month_ago)
            commit_count = 0
            for _ in commits:
                commit_count+=1

            return json.dumps({'commit_count': commit_count, 'repository':repo_name, 'since':one_month_ago.isoformat()}, indent=2)

        except GithubException as e:
            logger.error(f'Error getting monthly commit count: {e}')
            return json.dumps({'error': str(e)})


class GithubPullRequestStats(Toolkit):
    def __init__(self, access_token: Optional[str] = None, base_url: Optional[str] = None):
        super().__init__(name='github_pull_request_stats')
        self.access_token = access_token or os.getenv('GITHUB_ACCESS_TOKEN')
        self.base_url = base_url
        self.g = self._authenticate()
        self.register(self.list_monthly_pull_requests)

    def _authenticate(self):
        'Authenticate with GitHub using the provided access token.'
        auth = Auth.Token(self.access_token)
        if self.base_url:
            logger.debug(f'Authenticating with GitHub Enterprise at {self.base_url}')
            return Github(base_url=self.base_url, auth=auth)
        else:
            logger.debug('Authenticating with public GitHub')
            return Github(auth=auth)

    def list_monthly_pull_requests(self, repo_name: str) -> str:
        'Lists pull requests created in the past month for a repository.\n\n        Args:\n            repo_name (str): The full name of the repository (e.g., owner/repo).\n\n        Returns:\n            A JSON-formatted string containing a list of pull request details.'
        logger.debug(f'Listing monthly pull requests for repository: {repo_name}')
        try:
            repo = self.g.get_repo(repo_name)
            now = datetime.now(timezone.utc)
            one_month_ago = now - timedelta(days=30)
            pulls = repo.get_pulls(state='all', sort='created', direction='desc')

            pr_list = []
            for pull in pulls:
                 if pull.created_at > one_month_ago:
                     pr_info = {
                         'title': pull.title,
                         'number': pull.number,
                         'user': pull.user.login,
                         'created_at': pull.created_at.isoformat(),
                         'state': pull.state,
                      }
                     pr_list.append(pr_info)
            return json.dumps(pr_list, indent=2)
        except GithubException as e:
            logger.error(f'Error listing monthly pull requests: {e}')
            return json.dumps({'error': str(e)})
        
