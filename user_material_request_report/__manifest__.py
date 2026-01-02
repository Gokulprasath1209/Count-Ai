{
    'name': 'User Report',
    'version': '18.0',
    'summary': 'Material Request Report Wizard',
    'sequence': 10,
    'description': 'Material Request PDF Reports using Wizard',
    'depends': ['purchase'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/user_report_views.xml',
        'report/user_report.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
