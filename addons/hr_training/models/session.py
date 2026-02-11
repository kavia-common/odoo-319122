# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class HrTrainingSession(models.Model):
    _name = "hr.training.session"
    _description = "Training Session"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "start_datetime desc, id desc"

    name = fields.Char(required=True, compute="_compute_name", store=True, tracking=True)
    course_id = fields.Many2one("hr.training.course", required=True, ondelete="restrict", tracking=True)
    company_id = fields.Many2one("res.company", related="course_id.company_id", store=True, index=True)
    start_datetime = fields.Datetime(required=True, tracking=True)
    end_datetime = fields.Datetime(required=True, tracking=True)
    location = fields.Char(tracking=True)
    instructor_employee_id = fields.Many2one("hr.employee", string="Instructor (Employee)", tracking=True)
    instructor_user_id = fields.Many2one("res.users", string="Instructor (User)", tracking=True)
    capacity = fields.Integer(
        default=0,
        tracking=True,
        help="0 means unlimited capacity. Otherwise, seat limit enforced on approval.",
    )
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("published", "Published"),
            ("in_progress", "In Progress"),
            ("done", "Done"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        required=True,
        tracking=True,
    )

    enrollment_ids = fields.One2many("hr.training.enrollment", "session_id", string="Enrollments")
    approved_enrollment_count = fields.Integer(compute="_compute_enrollment_counts", store=True)
    available_seat_count = fields.Integer(compute="_compute_enrollment_counts", store=True)
    notes = fields.Text()

    @api.depends("course_id", "start_datetime")
    def _compute_name(self):
        for rec in self:
            if rec.course_id and rec.start_datetime:
                rec.name = "%s - %s" % (rec.course_id.name, fields.Datetime.to_string(rec.start_datetime))
            elif rec.course_id:
                rec.name = rec.course_id.name
            else:
                rec.name = _("New Training Session")

    @api.depends("capacity", "enrollment_ids.state")
    def _compute_enrollment_counts(self):
        seat_holding_states = {"approved", "attended", "completed"}
        for rec in self:
            approved = len(rec.enrollment_ids.filtered(lambda e: e.state in seat_holding_states))
            rec.approved_enrollment_count = approved
            if rec.capacity and rec.capacity > 0:
                rec.available_seat_count = max(rec.capacity - approved, 0)
            else:
                # Unlimited: keep as 0 to avoid confusing UI math; views can hide when capacity=0.
                rec.available_seat_count = 0

    @api.constrains("start_datetime", "end_datetime")
    def _check_datetime_order(self):
        for rec in self:
            if rec.start_datetime and rec.end_datetime and rec.end_datetime <= rec.start_datetime:
                raise ValidationError(_("End time must be after start time."))

    def action_publish(self):
        for rec in self:
            if rec.state != "draft":
                continue
            rec.state = "published"

    def action_start(self):
        for rec in self:
            if rec.state != "published":
                continue
            rec.state = "in_progress"

    def action_done(self):
        for rec in self:
            if rec.state not in ("published", "in_progress"):
                continue
            rec.state = "done"

    def action_cancel(self):
        for rec in self:
            if rec.state == "done":
                continue
            rec.state = "cancelled"
