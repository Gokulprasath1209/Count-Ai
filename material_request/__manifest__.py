{
    'name': 'Material Request',
    'version': '18.0',
    'summary': 'Material Request for MRP',
    'sequence': 10,
    'description': """ Material Request For MRP """,
    'depends': ['base', 'mrp', 'stock'],
    'data': [
        'security/ir.model.access.csv',
        'data/seqence.xml',
        'views/mrp_extended.xml',
        'views/material_request.xml',
        # 'views/menus.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
