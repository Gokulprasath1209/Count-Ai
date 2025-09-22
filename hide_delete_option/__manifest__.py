# -*- coding: utf-8 -*-
{
    'name': 'Hide Delete for groups',
    'summary': 'Hide Delete for groups',
    'description': """
    """,
    'version': '18.0.1.0.0',
    "author": "Croissant",
    "license": "OPL-1",
    'depends': ['web'],
    'images': [
        'static/description/banner.png',

    ],
    'assets': {
        'web.assets_backend': [
            'hide_delete_option/static/src/search/*/*',
        ],
    },
    'data': ['security/groups.xml'],
    'installable': True,
}
