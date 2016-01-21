# -*-  coding: utf-8 -*-
"""project settings"""

# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.


import os.path

DEFAULT_LANG = 'en'

BASE_DIR = os.path.dirname(os.path.realpath(__file__))

# path of the activity modules which will be invoked by workflow tasks
ACTIVITY_MODULES_IMPORT_PATHS = ['zengine.views']
# absolute path to the workflow packages
WORKFLOW_PACKAGES_PATHS = [os.path.join(BASE_DIR, 'diagrams')]

AUTH_BACKEND = 'zengine.auth.auth_backend.AuthBackend'

PERMISSION_MODEL = 'zengine.models.Permission'
USER_MODEL = 'zengine.models.User'
ROLE_MODEL = 'zengine.models.Role'
# left blank to use StreamHandler aka stderr
# set 'file' for logging 'LOG_FILE'
LOG_HANDLER = os.environ.get('LOG_HANDLER')

LOG_LEVEL = os.environ.get('LOG_LEVEL', 'DEBUG')

# logging dir for file handler
# LOG_DIR = os.environ.get('LOG_DIR', '/tmp/')

# log file
LOG_FILE = os.environ.get('LOG_FILE', '/tmp/zengine.log')

DEFAULT_CACHE_EXPIRE_TIME = 99999999  # seconds

# workflows that dosen't require logged in user
ANONYMOUS_WORKFLOWS = ['login', 'login.']

# currently only affects logging level
DEBUG = bool(int(os.environ.get('DEBUG', 0)))


# PYOKO SETTINGS
DEFAULT_BUCKET_TYPE = os.environ.get('DEFAULT_BUCKET_TYPE', 'zengine_models')
RIAK_SERVER = os.environ.get('RIAK_SERVER', 'localhost')
RIAK_PROTOCOL = os.environ.get('RIAK_PROTOCOL', 'http')
RIAK_PORT = os.environ.get('RIAK_PORT', 8098)

REDIS_SERVER = os.environ.get('REDIS_SERVER', '127.0.0.1:6379')

ALLOWED_ORIGINS = [
                      'http://127.0.0.1:8080',
                      'http://127.0.0.1:9001',
                  ] + os.environ.get('ALLOWED_ORIGINS', '').split(',')

ENABLED_MIDDLEWARES = [
    'zengine.middlewares.CORS',
    'zengine.middlewares.RequireJSON',
    'zengine.middlewares.JSONTranslator',
]

SESSION_OPTIONS = {
    'session.cookie_expires': True,
    'session.type': 'redis',
    'session.url': REDIS_SERVER,
    'session.auto': True,
    'session.path': '/',
}

VIEW_URLS = [
    # ('falcon URI template', 'python path to view method/class'),
    ('/menu', 'zengine.views.menu.Menu'),
]

MESSAGES = {
    'lane_change_invite_title': 'System needs you!',
    'lane_change_invite_body': 'Some workflow reached a state that needs your action, '
                                'please follow the link bellow',
    'lane_change_message_title': '',
    'lane_change_message_body': 'Some workflow reached a state that needs your action, '
                                'please follow the link bellow',

}

CATALOG_DATA_MANAGER = 'zengine.lib.catalog_data.catalog_data_manager'

OBJECT_MENU = {}
ADMIN_MENUS = []
DEFAULT_WF_CATEGORY_NAME = 'General Workflows'
DEFAULT_OBJECT_CATEGORY_NAME = 'Object Tasks'

DATE_DEFAULT_FORMAT = "%d.%m.%Y"
DATETIME_DEFAULT_FORMAT = "%d.%m.%Y %H:%s"


ENABLE_SIMPLE_CRUD_MENU = True

PERMISSION_PROVIDER = 'zengine.auth.permissions.get_all_permissions'
