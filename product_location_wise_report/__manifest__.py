{
    'name': 'Location based products Screen',
    'version': '18.0',
    'sequence': 1,
    'category': 'Inventory',
    'author': 'AppsComp',
    'website': 'appscomp.com',
    'license': 'LGPL-3',
    'depends': ["base", "web", 'stock'],
    'module_type': '',
    'data': [
        'views/xml_view.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js',
            'https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js',
            'https://cdnjs.cloudflare.com/ajax/libs/jspdf/3.0.2/jspdf.umd.min.js',
            'https://cdnjs.cloudflare.com/ajax/libs/jspdf-autotable/3.5.25/jspdf.plugin.autotable.min.js',
            'product_location_wise_report/static/src/js/product.js',
            'product_location_wise_report/static/src/xml/product.xml',
        ],
    },
    'application': True,
}
