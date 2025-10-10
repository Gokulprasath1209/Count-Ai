{
    'name': 'pruchase wizard',
    'version': '18.0',
    'summary': 'wizard',
    'sequence': 10,
    'description': """ Sale Extended For sales and spares """,
    'depends': ['purchase' ],
    'data': [
        'security/ir.model.access.csv',
        'views/purchase_order_views.xml',
        'wizard/purchase_order_wizard_views.xml',
        'report/purchase_report.xml',
],

    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
