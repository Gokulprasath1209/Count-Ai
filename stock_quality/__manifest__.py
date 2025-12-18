{
    'name': 'Stock Quality',
    'version': '18.0',
    'summary': 'Stock Quality',
    'sequence': 10,
    'description': """ Stock Quality """,
    'depends': ['base', 'stock','purchase_requisition','product'],
    'data': [
        'security/ir.model.access.csv',
        'data/seq.xml',
        'views/quality_test_view.xml',
        'views/stock_move.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
