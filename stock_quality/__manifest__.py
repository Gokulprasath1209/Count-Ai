{
    'name': 'Stock Quality',
    'version': '18.0',
    'summary': 'Stock Quality',
    'sequence': 10,
    'description': """ Stock Quality """,
    'depends': [
        'base',
        'stock',
        'purchase_requisition',
        'product',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/seq.xml',
        'views/quality_test_view.xml',
        'views/stock_move.xml',
        'views/product_template_views.xml',
        'wizard/quality_wizard_views.xml',
        'report/quality_report_pdf.xml',
    ],
    # 'assets': {
    #     'web.assets_backend': [
    #         'stock_quality/static/src/js/stock_move_line_total_stock.js',
    #     ],
    # },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
