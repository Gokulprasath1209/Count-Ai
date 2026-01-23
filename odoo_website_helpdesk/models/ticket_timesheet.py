# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class TicketTimesheet(models.Model):
    """Time tracking for helpdesk tickets"""
    _name = 'ticket.timesheet'
    _description = 'Ticket Timesheet'
    _order = 'start_time desc'

    ticket_id = fields.Many2one(
        'ticket.helpdesk',
        string='Ticket',
        required=True,
        ondelete='cascade',
        help='Related helpdesk ticket'
    )
    user_id = fields.Many2one(
        'res.users',
        string='User',
        required=True,
        default=lambda self: self.env.user,
        help='User who worked on this session'
    )
    start_time = fields.Datetime(
        string='Start Time',
        required=True,
        default=fields.Datetime.now,
        help='When this work session started'
    )
    end_time = fields.Datetime(
        string='End Time',
        help='When this work session ended'
    )
    duration = fields.Float(
        string='Duration (hours)',
        compute='_compute_duration',
        store=True,
        help='Duration of this work session in hours'
    )
    description = fields.Text(
        string='Description',
        help='Optional notes for this time session'
    )
    is_active_session = fields.Boolean(
        string='Active Session',
        default=True,
        help='Whether this session is currently active'
    )

    @api.depends('start_time', 'end_time')
    def _compute_duration(self):
        """Calculate duration in hours between start and end time"""
        for record in self:
            if record.start_time and record.end_time:
                delta = record.end_time - record.start_time
                record.duration = delta.total_seconds() / 3600.0
            elif record.start_time and record.is_active_session:
                # For active sessions, calculate duration from start to now
                delta = fields.Datetime.now() - record.start_time
                record.duration = delta.total_seconds() / 3600.0
            else:
                record.duration = 0.0

    duration_display = fields.Char(
        string='Duration',
        compute='_compute_duration_display',
        help='Duration displayed in minutes or hours:minutes'
    )

    @api.depends('duration')
    def _compute_duration_display(self):
        for record in self:
            duration_hours = record.duration
            if duration_hours < 1.0:
                # Less than 1 hour: display in minutes
                minutes = int(round(duration_hours * 60))
                record.duration_display = f"{minutes} min"
            else:
                # 1 hour or more: display in HH:MM
                hours = int(duration_hours)
                minutes = int(round((duration_hours - hours) * 60))
                record.duration_display = "{:02d}:{:02d}".format(hours, minutes)
