"""OpenLDAP backup to a GIT repo.

This will backup ALL data in the supplied LDAP host to the specified GIT repo.
It will commit changes, if there are any, but leaves it alone if there were no
diffs.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import datetime
import io
import logging
import os
import time

import click

from git import repo
from six.moves import urllib_parse

from treadmill import context
from treadmill import fs
from treadmill import subproc

_FIVE_MINS = 300

_LOGGER = logging.getLogger(__name__)


def _get_repo_filename(ldap_repo, filename):
    """Determine repo file name based on relativity to repo"""
    repo_dir = ldap_repo.working_tree_dir
    _LOGGER.debug('repo_dir: %s', repo_dir)

    basename = filename
    if filename.startswith(repo_dir):
        basename = filename[len(repo_dir) + 1:]
    _LOGGER.debug('basename: %r', basename)

    return basename


def _file_in_repo(ldap_repo, filename):
    """Determine if file in the index/repo"""
    basename = _get_repo_filename(ldap_repo, filename)
    for (path, _stage), _entry in ldap_repo.index.entries.items():
        if basename == path:
            _LOGGER.info('Found %s in index', basename)
            return True
    return False


def _commit_file(ldap_repo, filename, commit_msg):
    """Commit a file to the master index"""
    basename = _get_repo_filename(ldap_repo, filename)

    ldap_repo.index.add([basename])

    _LOGGER.info('Committing %s to index', basename)
    # author = git.Actor('', 'author@example.com')
    # committer = git.Actor('A committer', 'committer@example.com')
    ldap_repo.index.commit(commit_msg)


def _add_initial_readme(ldap_repo, readme, ldap_host):
    """Add inital README file to repo"""
    with io.open(readme, 'w') as fh:
        fh.write('Temp file for LDAP backup of {}'.format(ldap_host))

    _commit_file(ldap_repo, readme, 'Initial commit')


def _safe_init_repo(repo_dir, ldap_host):
    """Create GIT repo if it doesn't exist yet"""
    readme = os.path.join(repo_dir, 'README')

    if repo.fun.is_git_dir(os.path.join(repo_dir, '.git')):
        _LOGGER.info('GIT repo %s has already been initialized', repo_dir)
        ldap_repo = repo.Repo(repo_dir)

        if not _file_in_repo(ldap_repo, readme):
            _add_initial_readme(ldap_repo, readme, ldap_host)

        return ldap_repo

    ldap_repo = repo.Repo.init(repo_dir)

    if not _file_in_repo(ldap_repo, readme):
        _add_initial_readme(ldap_repo, readme, ldap_host)

    return ldap_repo


def _backup_ldap(uri, search_suffix, ldap_repo, ldap_host):
    """Run ldapsearch to backup to repo dir"""
    subproc.get_aliases(aliases_path='ms_aliases')
    ldif = subproc.check_output([
        'ldapsearch',
        '-H', uri,
        '-b', search_suffix,
        '-Q', '-LLL', '*', '+'
    ])
    repo_dir = ldap_repo.working_tree_dir
    ldif_file = os.path.join(repo_dir, '{}.ldif'.format(ldap_host))

    first_run = False
    if not _file_in_repo(ldap_repo, ldif_file):
        first_run = True

    _LOGGER.info('Writting LDIF to %s', ldif_file)
    with io.open(ldif_file, 'w') as fh:
        fh.write(ldif)

    if first_run:
        _commit_file(
            ldap_repo,
            ldif_file,
            'Initial LDIF backup commit for {}'.format(ldap_host)
        )
        return ldif_file

    diff = ldap_repo.index.diff(None)
    _LOGGER.debug('diff: %r', diff)
    if not diff:
        _LOGGER.info('No diffs since last run, not committing')
        return ldif_file

    _commit_file(
        ldap_repo,
        ldif_file,
        'Updates for {} at {}'.format(
            ldap_host,
            datetime.datetime.now().isoformat()
        )
    )
    return ldif_file


def init():
    """Main command handler."""

    @click.command(name='ldap-backup')
    @click.option('--uri', help='LDAP URI', required=True)
    @click.option('--backup-dir', help='Backup GIT directory',
                  required=True,
                  type=click.Path(dir_okay=True, writable=True))
    @click.option('--search-suffix', help='LDAP search suffic')
    @click.option('--interval', help='Wait interval before making a backup',
                  default=_FIVE_MINS, type=int)
    def ldap_backup(uri, backup_dir, search_suffix, interval):
        """LDAP backup to GIT repo"""
        fs.mkdir_safe(backup_dir, mode=0o755)

        # Use urlparse to extract LDAP host
        ldapurl_parsed = urllib_parse.urlparse(uri)
        ldap_host = ldapurl_parsed.netloc

        if ldapurl_parsed.port is not None:
            ldap_host = ldap_host[:-len(str(ldapurl_parsed.port)) - 1]
        _LOGGER.debug('ldap_host: %s', ldap_host)

        ldap_repo = _safe_init_repo(backup_dir, ldap_host)
        _LOGGER.debug('ldap_repo: %r', ldap_repo)

        if not search_suffix:
            search_suffix = context.GLOBAL.ldap_suffix

        while True:
            _LOGGER.info('Backing up %s at %s', uri, search_suffix)
            backup_file = _backup_ldap(
                uri, search_suffix, ldap_repo, ldap_host
            )
            _LOGGER.info('Processed %s', backup_file)

            time.sleep(interval)

    return ldap_backup
