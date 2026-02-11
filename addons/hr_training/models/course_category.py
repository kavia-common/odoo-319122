# -*- coding: utf-8 -*-
from odoo import api, fields, models


class HrTrainingCourseCategory(models.Model):
    _name = "hr.training.course.category"
    _description = "Training Course Category"
    _order = "name"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", string="Company")
