# -*- coding: utf-8 -*-

{
    'name': 'Manufacturing Report',
    'version': '18.0.1.0.0',
    'category': 'Manufacturing',
    'summary': 'Manufacturing Order PDF Report',
    'description': """
Manufacturing Report Wizard
----------------------------
• Manufacturing Order reports
• Filter by date and status
• PDF output
""",
    'author': 'Your Company Name',
    'website': 'https://www.yourcompany.com',
    'license': 'LGPL-3',

    'depends': ['base','mrp','stock',],

    'data': [
        'security/ir.model.access.csv',
        'report/data_report.xml',
        'wizard/production_report_views.xml',

    ],

    'installable': True,
    'application': True,

}
