{
    'name': 'Customer And Vendoer Creation',
    'version': '18.0',
    'summary': '',
    'sequence': 10,
    'description': """ Customer And Vendoer Creation """,
    'depends': ['base', 'contacts', 'account', 'purchase', 'purchase_requisition'],
    'data': [
        # 'data/res_group.xml',
        'views/res_partner_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
