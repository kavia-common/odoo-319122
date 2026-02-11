# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class HrTrainingCertificate(models.Model):
    _name = "hr.training.certificate"
    _description = "Training Certificate"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "issue_date desc, id desc"

    name = fields.Char(compute="_compute_name", store=True, tracking=True)

    employee_id = fields.Many2one("hr.employee", required=True, ondelete="restrict", tracking=True, index=True)
    course_id = fields.Many2one("hr.training.course", required=True, ondelete="restrict", tracking=True, index=True)
    company_id = fields.Many2one("res.company", related="course_id.company_id", store=True, index=True)
    enrollment_id = fields.Many2one("hr.training.enrollment", ondelete="set null", tracking=True)

    issue_date = fields.Date(default=lambda self: fields.Date.today(), required=True, tracking=True)
    expiry_date = fields.Date(compute="_compute_expiry_date", store=True, tracking=True)

    state = fields.Selection(
        selection=[
            ("active", "Active"),
            ("expired", "Expired"),
            ("revoked", "Revoked"),
        ],
        compute="_compute_state",
        store=True,
        tracking=True,
        index=True,
    )

    revoked_date = fields.Date(tracking=True)
    revoked_by = fields.Many2one("res.users", tracking=True)
    revoked_reason = fields.Text(tracking=True)

    attachment_id = fields.Many2one("ir.attachment", string="Certificate File")
    external_reference = fields.Char()

    @api.depends("employee_id", "course_id")
    def _compute_name(self):
        for rec in self:
            if rec.employee_id and rec.course_id:
                rec.name = "%s - %s" % (rec.employee_id.name, rec.course_id.name)
            else:
                rec.name = _("Training Certificate")

    @api.depends("issue_date", "course_id.validity_months")
    def _compute_expiry_date(self):
        for rec in self:
            if not rec.issue_date:
                rec.expiry_date = False
                continue
            months = rec.course_id.validity_months or 0
            if months <= 0:
                rec.expiry_date = False
            else:
                rec.expiry_date = rec.issue_date + relativedelta(months=months)

    @api.depends("expiry_date", "revoked_date")
    def _compute_state(self):
        today = fields.Date.today()
        for rec in self:
            if rec.revoked_date:
                rec.state = "revoked"
            elif rec.expiry_date and rec.expiry_date < today:
                rec.state = "expired"
            else:
                rec.state = "active"

    @api.constrains("employee_id", "course_id", "state")
    def _check_no_duplicate_active(self):
        for rec in self:
            if rec.state != "active":
                continue
            dup = self.search_count([
                ("id", "!=", rec.id),
                ("employee_id", "=", rec.employee_id.id),
                ("course_id", "=", rec.course_id.id),
                ("state", "=", "active"),
            ])
            if dup:
                raise ValidationError(_("An active certificate already exists for this employee and course."))

    def action_revoke(self):
        for rec in self:
            if rec.state == "revoked":
                continue
            rec.revoked_date = fields.Date.today()
            rec.revoked_by = self.env.user
            # state recomputed by compute method
