# -*- coding: utf-8 -*-
from odoo import api, fields, models


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    training_enrollment_count = fields.Integer(compute="_compute_training_counts")
    training_certificate_count = fields.Integer(compute="_compute_training_counts")

    training_enrollment_ids = fields.One2many(
        "hr.training.enrollment",
        "employee_id",
        string="Training Enrollments",
        readonly=True,
    )
    training_certificate_ids = fields.One2many(
        "hr.training.certificate",
        "employee_id",
        string="Training Certificates",
        readonly=True,
    )

    @api.depends("training_enrollment_ids", "training_certificate_ids")
    def _compute_training_counts(self):
        Enrollment = self.env["hr.training.enrollment"]
        Certificate = self.env["hr.training.certificate"]
        for emp in self:
            emp.training_enrollment_count = Enrollment.search_count([("employee_id", "=", emp.id)])
            emp.training_certificate_count = Certificate.search_count([("employee_id", "=", emp.id)])

    def action_open_training_enrollments(self):
        return {
            "type": "ir.actions.act_window",
            "name": "Training Enrollments",
            "res_model": "hr.training.enrollment",
            "view_mode": "tree,form",
            "domain": [("employee_id", "=", self.id)],
            "context": {"default_employee_id": self.id},
        }

    def action_open_training_certificates(self):
        return {
            "type": "ir.actions.act_window",
            "name": "Training Certificates",
            "res_model": "hr.training.certificate",
            "view_mode": "tree,form",
            "domain": [("employee_id", "=", self.id)],
            "context": {"default_employee_id": self.id},
        }
