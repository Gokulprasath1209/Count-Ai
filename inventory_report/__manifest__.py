{
    'name': 'inventory wizard',
    'version': '18.0',
    'summary': 'wizard',
    'sequence': 10,
    'description': """inventory report""",
    'depends': ['base', 'stock', 'product'],
    'data': [
        'security/ir.model.access.csv',
        'views/inven_views.xml',
        'wizard/inven_wizard_views.xml',
        'report/invent_report.xml',
],

    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
