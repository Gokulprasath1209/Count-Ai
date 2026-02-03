{
    'name': 'Purchase Cost Update',
    'version': '18.0.1.0.0',
    'summary': 'Update product standard price from purchase order',
    'description': """
        Automatically update product.template standard_price when a Purchase Order is confirmed.
        - Updates based on the most recent purchase unit price
        - Applies update only after PO confirmation
        - Respects product UoM conversion
        - Handles currency conversion
        - Logs updates in product chatter
    """,
    'category': 'Purchase',
    'author': 'Antigravity',
    'depends': ['purchase', 'stock'],
    'data': [
        'views/purchase_order_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
