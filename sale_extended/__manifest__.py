{
    'name': 'Sale_extended',
    'version': '18.0',
    'summary': 'Sale Extended',
    'sequence': 10,
    'description': """ Sale Extended For sales and spares """,
    'depends': ['base','sale',],
    'data': [
        'views/sale_extended.xml',
        # 'views/menus.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
