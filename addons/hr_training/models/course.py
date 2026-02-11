# -*- coding: utf-8 -*-
from collections import defaultdict, deque

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class HrTrainingCourse(models.Model):
    _name = "hr.training.course"
    _description = "Training Course"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name"

    name = fields.Char(required=True, tracking=True)
    code = fields.Char(tracking=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    category_id = fields.Many2one("hr.training.course.category", string="Category")
    description = fields.Html()
    is_mandatory = fields.Boolean(default=False, tracking=True)
    validity_months = fields.Integer(
        default=0,
        help="0 means no expiry. If > 0, certificates expire after this many months.",
        tracking=True,
    )
    issues_certificate = fields.Boolean(
        default=True,
        tracking=True,
        help="If enabled, completing an enrollment will issue a certificate.",
    )
    evaluation_mode = fields.Selection(
        selection=[
            ("manual", "Manual"),
            ("survey", "Survey (not installed)"),
            ("elearning", "eLearning (not installed)"),
            ("hybrid", "Hybrid (not installed)"),
        ],
        default="manual",
        required=True,
        tracking=True,
        help="In this module implementation, only Manual is implemented. Other modes are reserved for future optional add-ons.",
    )
    require_attendance = fields.Boolean(
        default=True,
        tracking=True,
        help="If enabled, the enrollment must be marked Present/Excused before completion.",
    )
    allow_self_enroll = fields.Boolean(
        default=True,
        tracking=True,
        help="If disabled, only HR Training Managers can create enrollments.",
    )
    requires_manager_approval = fields.Boolean(
        default=False,
        tracking=True,
        help="If enabled, enrollments have an intermediate 'Manager Approved' state.",
    )

    prerequisite_course_ids = fields.Many2many(
        "hr.training.course",
        "hr_training_course_prereq_rel",
        "course_id",
        "prereq_course_id",
        string="Prerequisites",
        help="Courses that must have a valid (active) certificate before enrolling.",
    )

    session_ids = fields.One2many("hr.training.session", "course_id", string="Sessions")
    certificate_ids = fields.One2many("hr.training.certificate", "course_id", string="Certificates")

    _sql_constraints = [
        (
            "code_company_uniq",
            "unique(company_id, code)",
            "The course code must be unique per company.",
        ),
    ]

    @api.constrains("validity_months")
    def _check_validity_months(self):
        for rec in self:
            if rec.validity_months is not None and rec.validity_months < 0:
                raise ValidationError(_("Validity months must be 0 or a positive number."))

    @api.constrains("prerequisite_course_ids")
    def _check_prerequisites_no_cycles(self):
        """
        Prevent:
        - self prerequisites
        - prerequisite cycles (A -> B -> A)
        """
        for rec in self:
            if rec in rec.prerequisite_course_ids:
                raise ValidationError(_("A course cannot be a prerequisite of itself."))

        # Detect cycles per company graph (only among records in this batch + their prereqs)
        # We do it record-by-record to keep error messages actionable.
        for rec in self:
            # BFS from rec following prerequisites; if we reach rec again => cycle
            visited = set()
            q = deque(rec.prerequisite_course_ids)
            while q:
                c = q.popleft()
                if c.id == rec.id:
                    raise ValidationError(
                        _("Prerequisite cycle detected for course '%s'. Please revise prerequisites.") % rec.display_name
                    )
                if c.id in visited:
                    continue
                visited.add(c.id)
                q.extend(c.prerequisite_course_ids)
