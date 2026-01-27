from odoo.tests.common import TransactionCase
from odoo.tools import float_compare

class TestPurchaseCostUpdate(TransactionCase):

    def setUp(self):
        super(TestPurchaseCostUpdate, self).setUp()
        self.product = self.env['product.product'].create({
            'name': 'Test Product',
            'standard_price': 100.0,
            'type': 'product',
        })
        self.partner = self.env['res.partner'].create({
            'name': 'Test Vendor',
        })
        self.po = self.env['purchase.order'].create({
            'partner_id': self.partner.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'name': 'Test Product',
                'product_qty': 10.0,
                'price_unit': 120.0,
                'product_uom': self.product.uom_id.id,
                'date_planned': fields.Datetime.now(),
            })],
        })

    def test_cost_update_on_confirm(self):
        """ Test that confirming a PO updates the product standard price """
        self.assertEqual(self.product.standard_price, 100.0)
        self.po.button_confirm()
        self.assertEqual(self.product.standard_price, 120.0)

    def test_currency_conversion_cost_update(self):
        """ Test that cost is updated correctly when PO is in a different currency """
        # Activate another currency
        currency_euro = self.env.ref('base.EUR')
        currency_euro.active = True
        
        # Assume company currency is USD (rate 1.0) and EUR rate is 0.5 (1 EUR = 2 USD)
        # Note: In tests we might need to set rates explicitly if not depending on demo data
        # For safety, let's create a rate
        self.env['res.currency.rate'].create({
            'currency_id': currency_euro.id,
            'company_id': self.env.company.id,
            'rate': 2.0, # 1 unit of base currency = 2 EUR. So 1 EUR = 0.5 Base.
            'name': fields.Date.today(),
        })

        po_eur = self.env['purchase.order'].create({
            'partner_id': self.partner.id,
            'currency_id': currency_euro.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'name': 'Test Product EUR',
                'product_qty': 10.0,
                'price_unit': 200.0, # 200 EUR -> 100 USD (if rate is 2.0)
                'product_uom': self.product.uom_id.id,
                'date_planned': fields.Datetime.now(),
            })],
        })
        
        # Reset standard price
        self.product.standard_price = 50.0
        po_eur.button_confirm()
        
        # 200 EUR / 2.0 = 100 USD.
        self.assertEqual(self.product.standard_price, 100.0)
from odoo import fields
