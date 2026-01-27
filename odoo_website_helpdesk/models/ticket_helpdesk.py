import logging
from datetime import timedelta
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

PRIORITIES = [
    ('0', 'Very Low'),
    ('1', 'Low'),
    ('2', 'Normal'),
    ('3', 'High'),
    ('4', 'Very High'),
]

RATING = [
    ('0', 'Very Low'),
    ('1', 'Low'),
    ('2', 'Normal'),
    ('3', 'High'),
    ('4', 'Very High'),
    ('5', 'Extreme High')
]


class TicketHelpDesk(models.Model):
    _name = 'ticket.helpdesk'
    _description = 'Helpdesk Ticket'
    _order = 'priority desc, start_date asc,id'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    def _default_show_create_task(self):
        return self.env['ir.config_parameter'].sudo().get_param(
            'odoo_website_helpdesk.show_create_task')

    def _default_show_category(self):
        return self.env['ir.config_parameter'].sudo().get_param(
            'odoo_website_helpdesk.show_category')

    def record_voice_action(self):
        return True

    def action_save_ticket(self):
        """
        Validates required fields, generates a ticket name, 
        and posts a notification to the chatter.
        """
        base_group = self.env.ref('base.group_user', raise_if_not_found=False)
        if base_group not in self.env.user.groups_id:
            raise UserError(_("You do not have permission to create this ticket."))

        required_fields = {
            'start_date': 'Issue Date',
            'department': 'Raising Department',
            'customer_id': 'Mill Name',
            'ticket_type_id': 'Machine',
            'machine_number': 'Machine #',
            'cabinet_version': 'Cabinet Version',
            'category_type': 'Software Version',
            'category': 'Category',
            'priority': 'Priority',
            'problem_heading': 'Problem Heading',
            'description': 'Problem Description',
        }

        for record in self:
            missing = [label for field, label in required_fields.items() if not record[field]]
            if missing:
                raise UserError(_("The following fields are mandatory and must be filled:\n- %s") % "\n- ".join(missing))

            record_sudo = record.sudo()
            if not record_sudo.name or record_sudo.name == 'New':
                # Map category to corresponding sequence code
                category = record.category
                sequence_code_map = {
                    'software': 'ticket.helpdesk.software',
                    'hardware': 'ticket.helpdesk.hardware',
                    'validation': 'ticket.helpdesk.validation',
                    'customer': 'ticket.helpdesk.customer',
                    'others': 'ticket.helpdesk.others',
                }
                # Get the appropriate sequence code, fallback to default if category not found
                sequence_code = sequence_code_map.get(category, 'ticket.helpdesk')
                record_sudo.name = record_sudo.env['ir.sequence'].sudo().next_by_code(sequence_code)
                
                # Post message to chatter
                record.message_post(body=_("Ticket %s has been created successfully.") % record_sudo.name)
                
        return True

    name = fields.Char('Name', default=lambda self: _('New'),
                       help='Ticket Name')
    customer_id = fields.Many2one('res.partner',
                                  string='Mill Name',
                                  required=True,
                                  help='Customer Name')
    customer_name = fields.Char('Customer Name', help='Customer Name')
    subject = fields.Text('Subject',
                          help='Subject of the Ticket')
    description = fields.Text('Description',
                              help='Description')
    category_type = fields.Selection([
        ('software_2.6.4', 'Software Issues - 2.6.4'),
        ('software_2.2.6', 'Software Issues - 2.2.6'),
        ('software_2.6.7', 'Software Issues - 2.6.7'),
        ('software_1.1.8', 'Software Issues - 1.1.8'),
        ('software_2.0.0', 'Software Issues - 2.0.0'),
        ('hardware_v1.1', 'Hardware Issues - V1.1'),
        ('hardware_v1.6', 'Hardware Issues - V1.6'),
        ('hardware_v10', 'Hardware Issues - V10'),
        ('hardware_v11', 'Hardware Issues - V11'),
        ('hardware_sd', 'Hardware Issues - SD'),
        ('hardware_ss', 'Hardware Issues - SS'),
        ('model_false_positive', 'Model Issues - Defects (False Positive)'),
        ('model_false_negative', 'Model Issues - Defects (False Negative)'),
    ], string='Software Version', required=True, help="Select category and version/type of issue.")

    # email = fields.Char('Email', help='Email')
    # phone = fields.Char('Phone', help='Contact Number')
    department = fields.Selection(
        [
            ('customer_message', 'Customer Message'),
            ('customer_calls', 'Customer Calls'),
            ('service_team', 'Service Team'),
            ('validation_team', 'Validation Team'),
            ('software_team', 'Software Team'),
            ('marketing_sales', 'Marketing / Sales Team'),
            ('support_team', 'Support Team'),
            ('customer_success', 'Customer Success'),
        ],
        string="Raising Department",
        required=True
    )
    category = fields.Selection(
        [
            ('software', 'Software'),
            ('validation', 'Validation'),
            ('customer', 'Customer'),
            ('hardware', 'Hardware'),
            ('others', 'Others'),
        ],
        string="Category",
        required=True
    )

    cabinet_version = fields.Char(string="Cabinet Version", required=True)
    machine_number = fields.Char(string="Machine Number", required=True)
    priority = fields.Selection(
        [
            ('low', 'Low'),
            ('medium', 'Medium'),
            ('hard', 'Hard'),
        ],
        string="Priority",
        default='medium',
        required=True,
        tracking=True
    )
    assigned_user_id = fields.Many2one('res.users', string="Informed By")
    team_head_id = fields.Many2one('res.users', string="Team Leader")
    created_by = fields.Many2one('res.users', string="Created By", default=lambda self: self.env.user, readonly=True)
    voice_recording = fields.Binary("Voice Recording", attachment=True, help="Upload or record voice notes")
    image_upload = fields.Binary("Image Upload", attachment=True,
                                 help="Upload image from gallery")
    video_recording = fields.Binary("Video Recording")
    video_filename = fields.Char("Video Filename")
    team_id = fields.Many2one('team.helpdesk', string='Helpdesk Team',
                              help='Helpdesk Team Name')
    product_ids = fields.Many2many('product.template',
                                   string='product heading',
                                   help='Product Name')
    project_id = fields.Many2one('project.project',
                                 string='Project',
                                 readonly=False,
                                 related='team_id.project_id',
                                 store=True,
                                 help='Project Name')
    # priority = fields.Selection(PRIORITIES, default='1', help='Priority of the Ticket')
    stage_id = fields.Many2one('ticket.stage', string='Stage',
                               tracking=True,
                               group_expand='_read_group_stage_ids',
                               help='Stages')
    user_id = fields.Many2one('res.users',
                              default=lambda self: self.env.user,
                              check_company=True,
                              index=True, tracking=True,
                              help='Login User', string='Assigned To')
    cost = fields.Float('Cost per hour', help='Cost Per Unit')
    service_product_id = fields.Many2one('product.product',
                                         string='Service Product',
                                         help='Service Product',
                                         domain=[('type', '=', 'service')])
    # create_date = fields.Datetime('Creation Date', help='Created date')
    start_date = fields.Datetime('Issue Date', required=True, help='Start Date')
    end_date = fields.Datetime('End Date', help='End Date')
    date_id = fields.Date('Date')
    problem_heading = fields.Char(
        'Problem Heading', required=True, readonly=False, help='Short description of the ticket', )
    # user_id = fields.Many2one('res.users',
    #                               string='Validated By')

    public_ticket = fields.Boolean(string="Public Ticket",
                                   help='Public Ticket')
    invoice_ids = fields.Many2many('account.move',
                                   string='Invoices',
                                   help='Invoicing id')
    task_ids = fields.Many2many('project.task',
                                string='Tasks',
                                help='Task id')
    color = fields.Integer(string="Color", help='Color')
    replied_date = fields.Datetime('Replied date', help='Replied Date')
    last_update_date = fields.Datetime('Last Update Date',
                                       help='Last Update Date')
    ticket_type_id = fields.Many2one('helpdesk.type',
                                     string='Machine name', required=True, help='Ticket Type')
    team_head_id = fields.Many2one('res.users', string='Team Leader',
                                   compute='_compute_team_head_id',
                                   help='Team Leader Name')
    assigned_user_id = fields.Many2one('res.users', string='Informed By',
                                       domain=lambda self: [('groups_id', 'in',
                                                             self.env.ref(
                                                                 'odoo_website_helpdesk.helpdesk_user').id)],
                                       help='Assigned User Name')
    category_id = fields.Many2one('helpdesk.category', string='Category',
                                  help='Category')
    tags_ids = fields.Many2many('helpdesk.tag', help='Tags', string='problem heading')
    assign_user = fields.Boolean(default=False, help='Assign User',
                                 string='Assign User')
    attachment_ids = fields.One2many('ir.attachment', 'res_id',
                                     help='Attachment Line',
                                     string='Attachments')
    merge_ticket_invisible = fields.Boolean(string='Merge Ticket',
                                            help='Merge Ticket Invisible or Not',
                                            default=False)
    merge_count = fields.Integer(string='Merge Count', help='Merged Tickets Count')
    active = fields.Boolean(default=True, help='Active', string='Active')

    show_create_task = fields.Boolean(string="Show Create Task",
                                      help='Show created task or not',
                                      default=_default_show_create_task,
                                      compute='_compute_show_create_task')
    create_task = fields.Boolean(string="Create Task", readonly=False,
                                 help='Create task or not',
                                 related='team_id.create_task', store=True)
    billable = fields.Boolean(string="Billable", default=False,
                              help='Is billable or not')
    show_category = fields.Boolean(default=_default_show_category,
                                   string="Show Category",
                                   help='Show category or not',
                                   compute='_compute_show_category')
    customer_rating = fields.Selection(RATING, default='0', readonly=True)
    review = fields.Char('Review', readonly=True, help='Ticket review')
    kanban_state = fields.Selection([
        ('normal', 'Ready'),
        ('done', 'In Progress'),
        ('blocked', 'Blocked'),
    ], default='normal')
    status_bar_view = fields.Boolean(
        string='Status Bar Editable',
        compute="_compute_status_bar_view",
        help="True if the current user can update the stage (Manager or Admin)"
    )
    camera_selection=fields.Selection([
        ('camera-1','camera-1'),
        ('camera-2','camera-2'),
        ('Both','Both')
    ],
    string='Camera')
    camera_name = fields.Selection([
        ('panther','panther'),
        ('Green','green')
    ],
    string='camera type')
    
    # Timer-related fields
    is_timer_running = fields.Boolean(
        string='Timer Running',
        default=False,
        help='Indicates if the timer is currently running'
    )
    total_time_spent = fields.Float(
        string='Total Time Spent',
        compute='_compute_total_time_spent',
        store=True,
        help='Total time spent on this ticket in hours'
    )
    timer_start = fields.Datetime(
        string='Timer Start',
        help='When the current timer session started'
    )
    timer_pause = fields.Datetime(
        string='Timer Pause',
        help='When the timer was paused'
    )
    timesheet_ids = fields.One2many(
        'ticket.timesheet',
        'ticket_id',
        string='Timesheet Entries',
        help='Time tracking entries for this ticket'
    )
    
    @api.onchange('customer_id')
    def _onchange_customer_id(self):
        """Auto-populate Machine Name (ticket_type_id) from the selected Customer."""
        if self.customer_id and self.customer_id.ticket_type_id:
            self.ticket_type_id = self.customer_id.ticket_type_id

    @api.depends('timesheet_ids.duration')
    def _compute_total_time_spent(self):
        """Compute total time spent from all timesheet entries"""
        for record in self:
            record.total_time_spent = sum(record.timesheet_ids.mapped('duration'))

    def action_forward_team(self):
        for rec in self:
            if rec.department == "software":
                rec.department = "hardware"
            else:
                rec.department = "software"

    @api.depends_context('create_uid')
    def _compute_status_bar_view(self):
        """Compute if user can edit the stage (Admin or Helpdesk Manager only)."""
        user = self.env.user
        for rec in self:
            is_admin = user.has_group('base.group_system')
            is_manager = user.has_group('odoo_website_helpdesk.group_helpdesk_manager')
            # Only Admins and Helpdesk Managers can edit the stage
            rec.status_bar_view = bool(is_admin or is_manager)
            print('+++++++++++++++++++++++++', rec.status_bar_view)

    # @api.onchange('team_id', 'team_head_id')
    # def _onchange_team_id(self):
    #     li = self.team_id.member_ids.mapped('id')
    #     return {'domain': {'assigned_user_id': [('id', 'in', li)]}}

    @api.depends('team_id')
    def _compute_team_head_id(self):
        self.team_head_id = self.team_id.team_lead_id.id

    @api.onchange('stage_id')
    def _onchange_stage_id(self):

        rec_id = self._origin.id
        data = self.env['ticket.helpdesk'].search([('id', '=', rec_id)])
        data.last_update_date = fields.Datetime.now()
        if self.stage_id.starting_stage:
            data.start_date = fields.Datetime.now()
        
        # Auto-start timer when moving to progress stage
        if self.stage_id.is_progress_stage and not data.is_timer_running:
            data.action_start_timer()
        
        # Auto-stop timer when moving to closing or cancel stage
        if (self.stage_id.closing_stage or self.stage_id.cancel_stage) and data.is_timer_running:
            data.action_stop_timer()
            data.end_date = fields.Datetime.now()
        elif self.stage_id.closing_stage or self.stage_id.cancel_stage:
            data.end_date = fields.Datetime.now()
        
        if self.stage_id.template_id:
            mail_template = self.stage_id.template_id
            mail_template.send_mail(self._origin.id, force_send=True)

    @api.depends('video_filename')
    def _compute_video_url(self):
        for rec in self:
            if rec.video_recording:
                rec.video_url = f"data:video/mp4;base64,{rec.video_recording.decode('utf-8')}"
            else:
                rec.video_url = False

    def assign_to_teamleader(self):
        """Assigning team leader function"""
        if self.team_id:
            self.team_head_id = self.team_id.team_lead_id.id
            mail_template = self.env.ref(
                'odoo_website_helpdesk.odoo_website_helpdesk_assign')
            mail_template.sudo().write({
                'email_to': self.team_head_id.email,
                'subject': self.name
            })
            mail_template.sudo().send_mail(self.id, force_send=True)
        else:
            raise ValidationError("Please choose a Helpdesk Team")

    def _compute_show_category(self):
        """Compute show category"""
        show_category = self._default_show_category()
        for rec in self:
            rec.show_category = show_category

    def _compute_show_create_task(self):
        """Compute the created task"""
        show_create_task = self._default_show_create_task()
        for record in self:
            record.show_create_task = show_create_task

    def auto_close_ticket(self):
        """Automatically closing the ticket"""
        auto_close = self.env['ir.config_parameter'].sudo().get_param(
            'odoo_website_helpdesk.auto_close_ticket')
        if auto_close:
            no_of_days = self.env['ir.config_parameter'].sudo().get_param(
                'odoo_website_helpdesk.no_of_days')
            records = self.env['ticket.helpdesk'].search([])
            for rec in records:
                days = (fields.Datetime.today() - rec.create_date).days
                if days >= int(no_of_days):
                    close_stage_id = self.env['ticket.stage'].search(
                        [('closing_stage', '=', True)])
                    if close_stage_id:
                        rec.stage_id = close_stage_id

    def default_stage_id(self):
        """Method to return the default stage"""
        return self.env['ticket.stage'].search(
            [('name', '=', 'Draft')], limit=1).id

    def _read_group_stage_ids(self, stages, domain):
        """Return the stages to stage_ids"""
        stage_ids = self.env['ticket.stage'].search([])
        return stage_ids

    @api.model_create_multi
    def create(self, vals_list):
        """Create function"""
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                # Map category to corresponding sequence code
                category = vals.get('category')
                sequence_code_map = {
                    'software': 'ticket.helpdesk.software',
                    'hardware': 'ticket.helpdesk.hardware',
                    'validation': 'ticket.helpdesk.validation',
                    'customer': 'ticket.helpdesk.customer',
                    'others': 'ticket.helpdesk.others',
                }
                # Get the appropriate sequence code, fallback to default if category not found
                sequence_code = sequence_code_map.get(category, 'ticket.helpdesk')
                vals['name'] = self.env['ir.sequence'].next_by_code(sequence_code) or _('New')
        return super(TicketHelpDesk, self).create(vals_list)

    def write(self, vals):
        """Write function"""
        result = super(TicketHelpDesk, self).write(vals)
        return result

    def action_create_invoice(self):
        """Create Invoice based on the ticket"""
        tasks = self.env['project.task'].search(
            [('project_id', '=', self.project_id.id),
             ('ticket_id', '=', self.id)]).filtered(
            lambda line: not line.ticket_billed)
        if not tasks:
            raise UserError('No Tasks to Bill')
        total = sum(x.effective_hours for x in tasks if
                    x.effective_hours > 0 and not x.some_flag)
        invoice_no = self.env['ir.sequence'].next_by_code('ticket.invoice')
        self.env['account.move'].create([{
            'name': invoice_no,
            'move_type': 'out_invoice',
            'partner_id': self.customer_id.id,
            'ticket_id': self.id,
            'date': fields.Date.today(),
            'invoice_date': fields.Date.today(),
            'invoice_line_ids': [(0, 0, {
                'product_id': self.service_product_id.id,
                'name': self.service_product_id.name,
                'quantity': total,
                'product_uom_id': self.service_product_id.uom_id.id,
                'price_unit': self.cost,
                'account_id': self.service_product_id.categ_id.property_account_income_categ_id.id,
            })],
        }])
        for task in tasks:
            task.ticket_billed = True
        return {
            'effect': {
                'fadeout': 'medium',
                'message': 'Billed Successfully!',
                'type': 'rainbow_man',
            }
        }

    def action_open_tasks(self):
        return {
            'name': 'Tasks',
            'domain': [('ticket_id', '=', self.id)],
            'res_model': 'project.task',
            'view_mode': 'list,form',
            'type': 'ir.actions.act_window',
        }

    def action_open_invoices(self):
        return {
            'name': 'Invoice',
            'domain': [('ticket_id', '=', self.id)],
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'type': 'ir.actions.act_window',
        }

    def action_open_merged_tickets(self):
        ticket_ids = self.env['support.ticket'].search(
            [('merged_ticket', '=', self.id)])
        helpdesk_ticket_ids = ticket_ids.mapped('display_name')
        help_ticket_records = self.env['ticket.helpdesk'].search(
            [('name', 'in', helpdesk_ticket_ids)])
        return {
            'type': 'ir.actions.act_window',
            'name': 'Helpdesk Ticket',
            'view_mode': 'list,form',
            'res_model': 'ticket.helpdesk',
            'domain': [('id', 'in', help_ticket_records.ids)],
            'context': self.env.context,
        }

    # def action_confirm_ticket(self):
    #     """Confirm button pressed, keep stage unchanged."""
    #     # Do your custom logic here
    #     # For example, send a message or perform checks
    #
    #     # Example: log a message
    #     for ticket in self:
    #         ticket.message_post(
    #             body=f"Ticket confirmed by {self.env.user.name} at stage '{ticket.stage_id.name}'"
    #         )
    #
    #     # Ensure stage_id stays unchanged (no write)
    #     return True

    ticket_ids = fields.One2many('ticket.help.desk.line', 'help_desk_id', string='Ticket')


    def action_start_timer(self):
        """Start the timer for this ticket"""
        for record in self:
            if not record.is_timer_running:
                # Create a new timesheet entry
                self.env['ticket.timesheet'].create({
                    'ticket_id': record.id,
                    'user_id': self.env.user.id,
                    'start_time': fields.Datetime.now(),
                    'is_active_session': True,
                })
                record.write({
                    'is_timer_running': True,
                    'timer_start': fields.Datetime.now(),
                    'timer_pause': False,
                })
        return True

    def action_pause_timer(self):
        """Pause the timer for this ticket"""
        for record in self:
            if record.is_timer_running:
                # Find the active timesheet entry and close it
                active_timesheet = self.env['ticket.timesheet'].search([
                    ('ticket_id', '=', record.id),
                    ('is_active_session', '=', True),
                ], limit=1)
                
                if active_timesheet:
                    active_timesheet.write({
                        'end_time': fields.Datetime.now(),
                        'is_active_session': False,
                    })
                
                record.write({
                    'is_timer_running': False,
                    'timer_pause': fields.Datetime.now(),
                })
        return True

    def action_stop_timer(self):
        """Stop the timer for this ticket (same as pause but called on stage change)"""
        return self.action_pause_timer()


    @api.model
    def get_dashboard_stats(self, search_query=None, date_filter=None):
        """Fetch statistics for the helpdesk dashboard with search and date filters."""
        Ticket = self.env['ticket.helpdesk']
        base_domain = []

        # 1. Handle Search Query
        if search_query:
            search_domain = [
                '|', '|', '|', '|', '|', '|', '|', '|', '|', '|',
                ('name', 'ilike', search_query),
                ('problem_heading', 'ilike', search_query),
                ('customer_id.name', 'ilike', search_query),
                ('ticket_type_id.name', 'ilike', search_query),
                ('department', 'ilike', search_query),
                ('machine_number', 'ilike', search_query),
                ('cabinet_version', 'ilike', search_query),
                ('category_type', 'ilike', search_query),
                ('category', 'ilike', search_query),
                ('priority', 'ilike', search_query),
                ('stage_id.name', 'ilike', search_query),
            ]
            base_domain += search_domain

        # 2. Handle Date Filters
        if date_filter:
            date_domain = []
            today = fields.Date.today()
            if date_filter == 'daily':
                date_domain = [('create_date', '>=', today)]
            elif date_filter == 'weekly':
                # Start of week (Monday)
                start_of_week = today - timedelta(days=today.weekday())
                date_domain = [('create_date', '>=', start_of_week)]
            elif date_filter == 'monthly':
                start_of_month = today.replace(day=1)
                date_domain = [('create_date', '>=', start_of_month)]
            elif isinstance(date_filter, dict):
                # Custom range: {'start': 'YYYY-MM-DD', 'end': 'YYYY-MM-DD'}
                if date_filter.get('start'):
                    date_domain.append(('create_date', '>=', date_filter['start']))
                if date_filter.get('end'):
                    date_domain.append(('create_date', '<=', date_filter['end']))
            
            base_domain += date_domain

        # KPI Counts
        total_tickets = Ticket.search_count(base_domain)
        hardware_tickets = Ticket.search_count(base_domain + [('category', '=', 'hardware')])
        software_tickets = Ticket.search_count(base_domain + [('category', '=', 'software')])
        validation_tickets = Ticket.search_count(base_domain + [('category', '=', 'validation')])
        
        # Open tickets (excluding closed/cancelled)
        open_stages = self.env['ticket.stage'].search([
            ('closing_stage', '=', False),
            ('cancel_stage', '=', False)
        ])
        open_tickets = Ticket.search_count(base_domain + [('stage_id', 'in', open_stages.ids)])

        # Status distribution for charts
        def get_status_counts(category=None):
            domain = list(base_domain)
            if category:
                domain.append(('category', '=', category))
            
            stats = {
                'opened': Ticket.search_count(domain + [('stage_id.starting_stage', '=', True)]),
                'in_progress': Ticket.search_count(domain + [('stage_id.is_progress_stage', '=', True)]),
                'completed': Ticket.search_count(domain + [('stage_id.closing_stage', '=', True)]),
            }
            return stats

        hardware_status = get_status_counts('hardware')
        software_status = get_status_counts('software')
        validation_status = get_status_counts('validation')
        all_status = get_status_counts()

        # Recent Tickets
        recent_tickets_records = Ticket.search(base_domain, limit=4, order='create_date desc')
        recent_tickets = []
        for ticket in recent_tickets_records:
            recent_tickets.append({
                'id': ticket.id,
                'name': ticket.name,
                'problem_heading': ticket.problem_heading,
                'customer_name': ticket.customer_id.name,
                'category': ticket.category,
                'stage_id': [ticket.stage_id.id, ticket.stage_id.name] if ticket.stage_id else False,
                'priority': ticket.priority,
                'create_date': ticket.create_date,
            })

        return {
            'total_tickets': total_tickets,
            'hardware_tickets': hardware_tickets,
            'software_tickets': software_tickets,
            'validation_tickets': validation_tickets,
            'open_tickets': open_tickets,
            'hardware_status': hardware_status,
            'software_status': software_status,
            'validation_status': validation_status,
            'all_status': all_status,
            'recent_tickets': recent_tickets,
        }

    @api.model
    def get_tickets_data(self, filters=None):
        """Fetch tickets with detailed filtering for the 'All Tickets' view."""
        domain = []
        if filters:
            if filters.get('search'):
                domain += ['|', '|', '|',
                           ('name', 'ilike', filters['search']),
                           ('problem_heading', 'ilike', filters['search']),
                           ('customer_id.name', 'ilike', filters['search']),
                           ('ticket_type_id.name', 'ilike', filters['search'])]
            
            if filters.get('category') and filters['category'] != 'all':
                domain.append(('category', '=', filters['category']))
                
            if filters.get('mill') and filters['mill'] != 'all':
                domain.append(('customer_id', '=', int(filters['mill'])))
                
            if filters.get('status') and filters['status'] != 'all':
                domain.append(('stage_id', '=', int(filters['status'])))
                
            if filters.get('team') and filters['team'] != 'all':
                domain.append(('team_id', '=', int(filters['team'])))

            if filters.get('date_range'):
                dr = filters['date_range']
                if dr.get('start'):
                    domain.append(('create_date', '>=', dr['start']))
                if dr.get('end'):
                    domain.append(('create_date', '<=', dr['end']))

        tickets = self.search(domain, order='create_date desc')
        
        return [{
            'id': t.id,
            'name': t.name,
            'create_date': t.create_date,
            'problem_heading': t.problem_heading,
            'customer_name': t.customer_id.name,
            'machine_name': t.ticket_type_id.name,
            'category': t.category,
            'priority': t.priority,
            'stage': t.stage_id.name if t.stage_id else 'Draft',
            'assigned_to': t.user_id.name if t.user_id else 'Unassigned',
        } for t in tickets]

    @api.model
    def get_filter_data(self):
        """Fetch metadata for dashboard dropdown filters."""
        return {
            'mills': [{'id': p.id, 'name': p.name} for p in self.env['res.partner'].search([('is_company', '=', True)])],
            'teams': [{'id': t.id, 'name': t.name} for t in self.env['team.helpdesk'].search([])],
            'stages': [{'id': s.id, 'name': s.name} for s in self.env['ticket.stage'].search([])],
            'categories': [
                {'id': 'software', 'name': 'Software'},
                {'id': 'hardware', 'name': 'Hardware'},
                {'id': 'validation', 'name': 'Validation'},
            ]
        }


class TicketHelpDeskLine(models.Model):
    _name = 'ticket.help.desk.line'
    _description = 'Helpdesk Ticket Line'

    help_desk_id = fields.Many2one('ticket.helpdesk', string='Help Desk', ondelete='cascade')
    voice_recording = fields.Binary("Voice Recording", help="Record or upload voice notes")
    has_voice_recording = fields.Boolean(compute='_compute_has_voice_recording', string="Has Recording")
    image_upload = fields.Binary("Image Upload", attachment=True, help="Upload image from gallery")
    video_recording = fields.Binary("Video Recording", attachment=True)
    video_filename = fields.Char("Video Filename")
    recording_duration = fields.Integer("Recording Duration (seconds)", readonly=True)
    recording_date = fields.Datetime("Recording Date", default=fields.Datetime.now, readonly=True)

    @api.model
    def get_binary_field_data(self, res_id, res_field):
        vv = self.search([('id', '=', res_id)])
        ff = getattr(vv, res_field)
        return ff

    @api.depends('voice_recording')
    def _compute_has_voice_recording(self):
        for record in self:
            record.has_voice_recording = bool(record.voice_recording)

# class ProjectTask(models.Model):
#     _inherit = 'project.task'
#
#     helpdesk_ticket_id = fields.Many2one(
#         'ticket.helpdesk',
#         string="Helpdesk Ticket",
#         ondelete='cascade'
#     )
