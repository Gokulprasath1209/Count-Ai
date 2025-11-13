

class TicketPortal(portal.CustomerPortal):

    def _prepare_home_portal_values(self, counters):

        values = super()._prepare_home_portal_values(counters)
        if 'ticket_count' in counters:
            ticket_count = request.env['ticket.helpdesk'].search_count(
                self._get_tickets_domain()) if request.env[
                'ticket.helpdesk'].check_access_rights(
                'read', raise_exception=False) else 0
            values['ticket_count'] = ticket_count
        return values

    def _get_tickets_domain(self):

        return [('customer_id', '=', request.env.user.partner_id.id)]

    @http.route(['/my/tickets'], type='http', auth="user", website=True)
    def portal_my_tickets(self):

        domain = self._get_tickets_domain()
        tickets = request.env['ticket.helpdesk'].sudo().search(domain)
        values = {
            'default_url': "/my/tickets",
            'tickets': tickets,
            'page_name': 'ticket',
        }
        return request.render("odoo_website_helpdesk.portal_my_tickets",
                              values)

    @http.route(['/my/tickets/<int:id>'], type='http', auth="public",
                website=True)
    def portal_tickets_details(self, **kwargs):

        ticket_id = kwargs.get("id")
        details = request.env['ticket.helpdesk'].sudo().browse(ticket_id)
        data = {
            'page_name': 'ticket',
            'ticket': True,
            'details': details,
        }
        return request.render("odoo_website_helpdesk.portal_ticket_details",
                              data)

    @http.route('/my/tickets/download/<id>', auth='public',
                type='http',
                website=True)
    def ticket_download_portal(self, **kwargs):
        """
        Route to download a PDF version of a specific ticket.
        Args:
            ticket (str): The ID of the ticket to be downloaded.
        Returns:
            http.Response: The HTTP response with the PDF file for download.
        """
        ticket_id = int(kwargs.get('id'))
        data = {
            'help': request.env['ticket.helpdesk'].sudo().browse(ticket_id)}
        report = request.env.ref(
            'odoo_website_helpdesk.report_ticket')
        pdf, _ = report.sudo()._render_qweb_pdf(
            report, res_ids=ticket_id, data=data)
        pdf_http_headers = [('Content-Type', 'application/pdf'),
                            ('Content-Length', len(pdf)),
                            ('Content-Disposition',
                             'attachment; filename="Helpdesk Ticket.pdf"')]
        return request.make_response(pdf, headers=pdf_http_headers)
