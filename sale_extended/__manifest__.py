{
    'name': 'Sale_extended',
    'version': '18.0',
    'summary': 'Sale Extended',
    'sequence': 10,
    'description': """ Sale Extended For sales and spares """,
    'depends': ['base', 'sale', ],
    'data': [
        'security/ir.model.access.csv',
        'views/sale_extended.xml',
        'wizard/saleorder_reports_views.xml',
        'report/sale_report.xml',

    ],

    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
