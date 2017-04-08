#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import random

from werkzeug.contrib.cache import NullCache

from mini_fiction import models

class ANSI:
    RESET = '\x1b[0m'
    BOLD = '\x1b[1m'
    RED = "\x1b[31m"
    GREEN = "\x1b[32m"
    YELLOW = "\x1b[33m"
    BLUE = "\x1b[34m"
    MAGENTA = "\x1b[35m"
    CYAN = "\x1b[36m"


class Status:
    title = 'Status'
    labels = {}

    def __init__(self, app):
        self.app = app

    def _ok(self, key, value):
        return {'mode': 'result', 'key': key, 'label': self.labels[key], 'value': value, 'status': 'ok'}

    def _warn(self, key, value):
        return {'mode': 'result', 'key': key, 'label': self.labels[key], 'value': value, 'status': 'warn'}

    def _fail(self, key, value):
        return {'mode': 'result', 'key': key, 'label': self.labels[key], 'value': value, 'status': 'fail'}


class SystemStatus(Status):
    title = 'System information'
    labels = {
        'python': 'Python',
        'env': 'Environment',
        'db': 'DB Provider',
        'sysencoding': 'Default encoding',
        'stdoutencoding': 'stdout encoding',
    }

    def python(self):
        return self._ok('python', sys.version.replace('\n', ' '))

    def env(self):
        return self._ok('env', os.environ.get('MINIFICTION_SETTINGS', 'mini_fiction.settings.Development'))

    def db(self):
        from mini_fiction.database import db
        return self._ok('db', str(type(db.provider)))

    def sysencoding(self):
        enc = sys.getdefaultencoding().lower()
        if enc == 'utf-8':
            return self._ok('sysencoding', enc)
        return self._warn('sysencoding', enc + ' (mini_fiction tested only with UTF-8)')

    def stdoutencoding(self):
        enc = sys.stdout.encoding.lower()
        if enc == 'utf-8':
            return self._ok('stdoutencoding', enc)
        return self._warn('stdoutencoding', enc + ' (mini_fiction tested only with UTF-8)')

    def generate(self):
        yield self.python()
        yield self.env()
        yield self.db()
        yield self.sysencoding()
        yield self.stdoutencoding()


class ProjectStatus(Status):
    title = 'Project configuration'
    labels = {
        'cache': 'Cache',
        'cache_working': 'Cache working',
        'email': 'E-Mail',
        'hasher': 'Password hasher',
        'media_root': 'Media directory',
        'static_root': 'Static files directory',
        'localstatic_root': 'Custom static files directory',
        'localtemplates': 'Custom templates directory',
        'sphinx': 'Sphinx search',
        'avatars': 'Avatars uploading',
        'celery': 'Celery',
        'diff': 'google-diff-match-patch',
    }

    def cache(self):
        return self._ok('cache', str(type(self.app.cache)))

    def cache_working(self):
        if isinstance(self.app.cache, NullCache):
            return self._ok('cache_working', 'disabled')

        k = ''.join(random.choice('abcdefghijklmnopqrstuvwxyz') for _ in range(10))
        self.app.cache.set('test_minifiction_status', k, timeout=30)

        if self.app.cache.get('test_minifiction_status') == k:
            return self._ok('cache_working', 'yes')
        return self._warn('cache_working', 'no')

    def email(self):
        if not self.app.config['ERROR_EMAIL_HANDLER_PARAMS'] and not self.app.config['EMAIL_HOST']:
            return self._ok('email', 'not configured')

        if self.app.config['ERROR_EMAIL_HANDLER_PARAMS'] is not None:
            if not isinstance(self.app.config['ERROR_EMAIL_HANDLER_PARAMS'], dict):
                return self._fail('email', 'not configured: ERROR_EMAIL_HANDLER_PARAMS must be dict {"mailhost": host}')

            if self.app.config['ERROR_EMAIL_HANDLER_PARAMS'].get('mailhost') != self.app.config['EMAIL_HOST']:
                return self._fail('email', 'ERROR_EMAIL_HANDLER_PARAMS["mailhost"] must be equal to EMAIL_HOST')

        from mini_fiction.utils.misc import connectmail

        try:
            s = connectmail()
            s.quit()
        except Exception as exc:
            return self._fail('email', 'failed: ' + str(exc))
        else:
            return self._ok('email', 'working')

    def hasher(self):
        hasher = self.app.config['PASSWORD_HASHER']

        if hasher == 'pbkdf2':
            return self._ok('hasher', 'PBKDF2-SHA256')

        if hasher == 'bcrypt':
            try:
                import bcrypt
            except ImportError:
                return self._fail('hasher', 'bcrypt, but cannot import module')
            return self._ok('hasher', 'bcrypt')

        if hasher == 'scrypt':
            try:
                import scrypt
            except ImportError:
                return self._fail('hasher', 'scrypt, but cannot import module')
            return self._ok('hasher', 'scrypt')

        return self._fail('hasher', 'unknown: {}'.format(hasher))

    def media_root(self):
        root = os.path.abspath(self.app.config['MEDIA_ROOT'])
        if not isinstance(root, str) or not os.path.isdir(root):
            return self._fail('media_root', 'not found: {}'.format(root))

        if not os.access(root, os.R_OK | os.W_OK | os.X_OK):
            return self._fail('media_root', 'permission denied: {}'.format(root))

        return self._ok('media_root', root)

    def static_root(self):
        if not self.app.config['STATIC_ROOT']:
            return self._fail('static_root', 'not set')
        root = os.path.abspath(self.app.config['STATIC_ROOT'])

        if not os.access(root, os.R_OK | os.X_OK):
            return self._fail('static_root', 'permission denied: {}'.format(root))

        return self._ok('static_root', root)

    def localstatic_root(self):
        if not self.app.config['LOCALSTATIC_ROOT']:
            return self._ok('localstatic_root', 'not set')
        root = os.path.abspath(self.app.config['LOCALSTATIC_ROOT'])

        if not isinstance(root, str) or not os.path.isdir(root):
            return self._fail('localstatic_root', 'not found: {}'.format(root))

        if not os.access(root, os.R_OK | os.X_OK):
            return self._fail('localstatic_root', 'permission denied: {}'.format(root))

        return self._ok('localstatic_root', root)

    def localtemplates(self):
        if not self.app.config['LOCALTEMPLATES']:
            return self._ok('localtemplates', 'not set')
        root = os.path.abspath(self.app.config['LOCALTEMPLATES'])

        if not isinstance(root, str) or not os.path.isdir(root):
            return self._fail('localtemplates', 'not found: {}'.format(root))

        if not os.access(root, os.R_OK | os.X_OK):
            return self._fail('localtemplates', 'permission denied: {}'.format(root))

        return self._ok('localtemplates', root)

    def sphinx(self):
        if self.app.config['SPHINX_DISABLED']:
            return self._ok('sphinx', 'disabled')

        try:
            with self.app.sphinx as sphinx:
                tables = sphinx.execute('show tables').fetchall()
        except Exception as exc:
            return self._fail('sphinx', 'failed: ' + str(exc))

        if ('stories', 'rt') not in tables or ('chapters', 'rt') not in tables:
            return self._fail('sphinx', 'working, but indexes are invalid')

        # TODO: full config test

        return self._ok('sphinx', 'working')

    def avatars(self):
        if not self.app.config['AVATARS_UPLOADING']:
            return self._ok('avatars', 'disabled')

        try:
            from PIL import Image
        except ImportError:
            return self._fail('avatars', 'enabled, but Pillow is not available')
        else:
            return self._ok('avatars', 'enabled')

    def celery(self):
        insp = self.app.celery.control.inspect(timeout=0.5)

        if self.app.config['CELERY_CONFIG']['task_always_eager']:
            return self._ok('celery', 'eager')

        try:
            active_tasks = insp.active()
        except Exception as exc:
            return self._fail('celery', 'failed to get active tasks: ' + str(exc))

        if active_tasks is None:
            return self._warn('celery', '0 workers, please run at least one or enable "task_always_eager"')

        try:
            scheduled_tasks = insp.scheduled()
        except Exception as exc:
            return self._fail('celery', 'failed to get scheduled tasks: ' + str(exc))

        return self._ok('celery', '{} workers, {} tasks active, {} tasks scheduled'.format(
            len(active_tasks or {}),
            sum(len(x) for x in active_tasks.values()),
            sum(len(x) for x in scheduled_tasks.values())
        ))

    def diff(self):
        try:
            import diff_match_patch  # pylint: disable=W0612
        except ImportError:
            return self._ok('diff', 'not installed (we recommend install it: pip install diff_match_patch_python)')

        from mini_fiction.utils.diff import get_diff_google

        try:
            assert get_diff_google('foo bar baz', 'foo baz baz') == [('=', 6), ('-', 'r'), ('+', 'z'), ('=', 4)]
        except Exception as exc:
            return self._fail('diff', 'not working: ' + str(exc))
        else:
            return self._ok('diff', 'working')

    def generate(self):
        yield self.cache()
        yield self.cache_working()
        yield self.email()
        yield self.hasher()
        yield self.media_root()
        yield self.static_root()
        yield self.localstatic_root()
        yield self.localtemplates()
        yield self.sphinx()
        yield self.avatars()
        yield self.celery()
        yield self.diff()


class UsersStatus(Status):
    title = 'Users'
    labels = {
        'last': 'Last',
        'count': 'Count',
        'active_count': 'Active count',
        'staff_count': 'Staff count',
        'superadmins_count': 'Superadmins count',
    }

    def last(self):
        last_user = models.Author.select().order_by(models.Author.id.desc()).first()
        if not last_user:
            return self._ok('last', 'none')
        return self._ok('last', '{}, {}'.format(last_user.username, last_user.date_joined))

    def count(self):
        return self._ok('count', str(models.Author.select().count()))

    def active_count(self):
        return self._ok('active_count', str(models.Author.select(lambda x: x.is_active).count()))

    def staff_count(self):
        return self._ok('staff_count', str(models.Author.select(lambda x: x.is_staff).count()))

    def superadmins_count(self):
        superadmins_count = models.Author.select(lambda x: x.is_staff and x.is_superuser).count()
        snostaff_count = models.Author.select(lambda x: not x.is_staff and x.is_superuser).count()

        if superadmins_count == 0:
            return self._ok('superadmins_count', "0 (you can create superadmin by 'mini_fiction createsuperuser')")
        if snostaff_count > 0:
            return self._warn('superadmins_count', '{} (and {} superadmins are not staff, maybe fix it?)'.format(superadmins_count, snostaff_count))
        return self._ok('superadmins_count', str(superadmins_count))

    def generate(self):
        yield self.last()
        yield self.count()
        yield self.active_count()
        yield self.staff_count()
        yield self.superadmins_count()


def generate(app, use_db_session=False):
    for Cat in (SystemStatus, ProjectStatus, UsersStatus):
        cat = Cat(app)
        yield {'mode': 'cat', 'title': cat.title}
        yield from cat.generate()


def print_all(app, colored=None):
    if colored is None:
        colored = sys.stdout.isatty()

    if colored:
        c = lambda x, t: getattr(ANSI, x) + t + ANSI.RESET
    else:
        c = lambda x, t: t

    if colored:
        print(ANSI.GREEN + ANSI.BOLD + 'mini_fiction' + ANSI.RESET)
    else:
        print('mini_fiction')

    fails = 0
    warns = 0

    labels = sum((list(x.labels.values()) for x in (SystemStatus, ProjectStatus, UsersStatus)), [])
    just = max(len(x) for x in labels) + 2

    for item in generate(app):
        if item['mode'] == 'cat':
            print()
            print(c('GREEN', item['title']))

        elif item['mode'] == 'result':
            print((item['label'] + ':').ljust(just), end='')
            if not colored or item['status'] == 'ok':
                print(item['value'])
            if item['status'] == 'warn':
                warns += 1
                if colored:
                    print(c('YELLOW', item['value']))
            elif item['status'] == 'fail':
                fails += 1
                if colored:
                    print(c('RED', item['value']))

    if fails > 0:
        print(c('RED', 'Found {} errors, please fix it before using mini_fiction'.format(fails)))
    if warns > 0:
        print(c('YELLOW', 'Found {} warnings, we recommend to fix it'.format(warns)))

    return fails, warns