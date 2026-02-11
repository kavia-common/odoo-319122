# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


class HrTrainingEnrollment(models.Model):
    _name = "hr.training.enrollment"
    _description = "Training Enrollment"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "request_date desc, id desc"

    session_id = fields.Many2one("hr.training.session", required=True, ondelete="cascade", tracking=True)
    course_id = fields.Many2one("hr.training.course", related="session_id.course_id", store=True, index=True)
    employee_id = fields.Many2one("hr.employee", required=True, ondelete="restrict", tracking=True)
    company_id = fields.Many2one("res.company", related="session_id.company_id", store=True, index=True)

    request_date = fields.Datetime(default=lambda self: fields.Datetime.now(), required=True, tracking=True)
    state = fields.Selection(
        selection=[
            ("requested", "Requested"),
            ("manager_approved", "Manager Approved"),
            ("approved", "Approved"),
            ("waitlisted", "Waitlisted"),
            ("rejected", "Rejected"),
            ("cancelled", "Cancelled"),
            ("attended", "Attended"),
            ("completed", "Completed"),
            ("failed", "Failed"),
        ],
        default="requested",
        required=True,
        tracking=True,
    )
    approval_user_id = fields.Many2one("res.users", string="Approved By", tracking=True)
    approval_date = fields.Datetime(string="Approved On", tracking=True)

    attendance_status = fields.Selection(
        selection=[
            ("present", "Present"),
            ("absent", "Absent"),
            ("excused", "Excused"),
        ],
        tracking=True,
    )
    attendance_marked_by = fields.Many2one("res.users", tracking=True)
    attendance_marked_on = fields.Datetime(tracking=True)

    score = fields.Float(tracking=True)
    completion_date = fields.Date(tracking=True)

    certificate_id = fields.Many2one("hr.training.certificate", tracking=True, readonly=True)
    reason_reject = fields.Text()
    reason_cancel = fields.Text()
    notes = fields.Text()

    _sql_constraints = [
        (
            "uniq_employee_session",
            "unique(session_id, employee_id)",
            "An employee can only be enrolled once per session.",
        ),
    ]

    @api.constrains("session_id", "employee_id")
    def _check_employee_company(self):
        for rec in self:
            if rec.session_id.company_id and rec.employee_id.company_id and rec.session_id.company_id != rec.employee_id.company_id:
                raise ValidationError(_("Employee company must match the session company."))

    def _user_is_training_manager(self):
        return self.env.user.has_group("hr_training.group_training_manager")

    def _check_self_enroll_allowed(self):
        for rec in self:
            if rec.course_id.allow_self_enroll:
                continue
            # If course disallows self enroll, only HR training managers can create
            if not rec._user_is_training_manager():
                raise AccessError(_("Self enrollment is not allowed for this course. Please contact HR."))

    def _check_session_is_published(self):
        for rec in self:
            if rec.session_id.state != "published":
                raise UserError(_("You can only request enrollment on published sessions."))

    def _check_prerequisites(self):
        """
        Enforce that the employee has an ACTIVE certificate for each prerequisite course.
        """
        Certificate = self.env["hr.training.certificate"]
        today = fields.Date.today()
        for rec in self:
            prereqs = rec.course_id.prerequisite_course_ids
            if not prereqs:
                continue
            certs = Certificate.search([
                ("employee_id", "=", rec.employee_id.id),
                ("course_id", "in", prereqs.ids),
                ("state", "=", "active"),
            ])
            certified_course_ids = set(certs.mapped("course_id").ids)
            missing = prereqs.filtered(lambda c: c.id not in certified_course_ids)
            if missing:
                raise UserError(
                    _("Prerequisites not satisfied. Missing valid certificates for: %s")
                    % ", ".join(missing.mapped("name"))
                )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        # Apply rules on initial creation (request)
        records._check_session_is_published()
        records._check_self_enroll_allowed()
        records._check_prerequisites()
        # If course requires manager approval, keep requested state; else HR may approve later.
        for rec in records:
            if rec.course_id.requires_manager_approval and rec.state == "requested":
                # keep as requested; manager action sets manager_approved
                continue
        return records

    def action_manager_approve(self):
        """
        Manager approval step (optional, controlled by course.requires_manager_approval).
        """
        for rec in self:
            if not rec.course_id.requires_manager_approval:
                raise UserError(_("Manager approval is not required for this course."))
            if rec.state != "requested":
                continue
            rec.state = "manager_approved"

    def action_approve(self):
        """
        HR approval. Applies capacity checks. May move to waitlisted when full.
        """
        for rec in self:
            if rec.state not in ("requested", "manager_approved"):
                continue

            # Enforce prerequisites again at approval time (in case certificates changed)
            rec._check_prerequisites()

            session = rec.session_id
            # Seat-holding states
            seat_holding_states = ("approved", "attended", "completed")
            approved_count = self.search_count([
                ("session_id", "=", session.id),
                ("state", "in", seat_holding_states),
            ])

            if session.capacity and session.capacity > 0 and approved_count >= session.capacity:
                rec.state = "waitlisted"
            else:
                rec.state = "approved"
                rec.approval_user_id = self.env.user
                rec.approval_date = fields.Datetime.now()

    def action_reject(self):
        for rec in self:
            if rec.state in ("completed",):
                raise UserError(_("You cannot reject a completed enrollment."))
            rec.state = "rejected"

    def action_cancel(self):
        for rec in self:
            if rec.state in ("completed",):
                raise UserError(_("You cannot cancel a completed enrollment. Revoke the certificate instead if needed."))
            rec.state = "cancelled"

    def action_mark_attendance(self, status):
        """
        status: present/absent/excused
        """
        if status not in ("present", "absent", "excused"):
            raise UserError(_("Invalid attendance status."))
        for rec in self:
            if rec.state not in ("approved", "waitlisted", "attended"):
                raise UserError(_("Attendance can only be marked for approved enrollments."))
            if rec.state == "waitlisted":
                raise UserError(_("Cannot mark attendance for a waitlisted enrollment."))

            rec.attendance_status = status
            rec.attendance_marked_by = self.env.user
            rec.attendance_marked_on = fields.Datetime.now()
            rec.state = "attended"

    def _issue_certificate_if_needed(self):
        for rec in self:
            if rec.certificate_id:
                continue
            if not rec.course_id.issues_certificate:
                continue

            cert_vals = {
                "employee_id": rec.employee_id.id,
                "course_id": rec.course_id.id,
                "enrollment_id": rec.id,
                "issue_date": fields.Date.today(),
            }
            cert = self.env["hr.training.certificate"].create(cert_vals)
            rec.certificate_id = cert.id

    def action_mark_completed(self):
        """
        Manual completion for manual evaluation mode.
        """
        for rec in self:
            if rec.state not in ("attended", "approved"):
                raise UserError(_("Enrollment must be attended/approved before completion."))

            if rec.course_id.require_attendance and rec.attendance_status not in ("present", "excused"):
                raise UserError(_("Attendance is required to complete this course."))

            # Only manual mode is implemented in this module.
            if rec.course_id.evaluation_mode != "manual":
                raise UserError(_("Only Manual evaluation mode is implemented in this module."))

            rec.state = "completed"
            rec.completion_date = fields.Date.today()
            rec._issue_certificate_if_needed()

    def action_mark_failed(self):
        for rec in self:
            if rec.state not in ("attended", "approved"):
                raise UserError(_("Enrollment must be attended/approved before marking failed."))
            rec.state = "failed"
