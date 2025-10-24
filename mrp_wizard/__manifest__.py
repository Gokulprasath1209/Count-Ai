{
    'name': 'manufacturing  wizard',
    'version': '18.0',
    'summary': 'wizard',
    'sequence': 10,
    'description': """MO report""",
    'depends': ['base','mrp' ],
    'data': [
        'security/ir.model.access.csv',
        'views/mrp_views.xml',
        'wizard/mrp_report_views.xml',
        'report/mrp_report.xml',
],

    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
