# -*- coding: utf-8 -*-
import json
from datetime import datetime, date

from odoo import http, _
from odoo.http import request
from odoo.exceptions import AccessError, UserError, ValidationError


def _json_response(payload, status=200):
    """Return a JSON HTTP response."""
    return request.make_response(
        json.dumps(payload, default=str),
        headers=[("Content-Type", "application/json")],
        status=status,
    )


def _parse_json_body():
    """Parse JSON body (best-effort)."""
    try:
        raw = request.httprequest.data or b""
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return {}


def _int(v, default=None):
    try:
        if v is None or v == "":
            return default
        return int(v)
    except Exception:
        return default


def _bool(v, default=None):
    if v is None:
        return default
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v)
    s = str(v).strip().lower()
    if s in ("1", "true", "yes", "y", "on"):
        return True
    if s in ("0", "false", "no", "n", "off"):
        return False
    return default


def _serialize_course(course):
    return {
        "id": course.id,
        "name": course.name,
        "code": course.code,
        "active": course.active,
        "company_id": course.company_id.id if course.company_id else False,
        "category_id": course.category_id.id if course.category_id else False,
        "description": course.description,
        "is_mandatory": course.is_mandatory,
        "validity_months": course.validity_months,
        "issues_certificate": course.issues_certificate,
        "evaluation_mode": course.evaluation_mode,
        "require_attendance": course.require_attendance,
        "allow_self_enroll": course.allow_self_enroll,
        "requires_manager_approval": course.requires_manager_approval,
        "prerequisite_course_ids": course.prerequisite_course_ids.ids,
    }


def _serialize_session(session):
    return {
        "id": session.id,
        "name": session.name,
        "course_id": session.course_id.id if session.course_id else False,
        "company_id": session.company_id.id if session.company_id else False,
        "start_datetime": session.start_datetime,
        "end_datetime": session.end_datetime,
        "location": session.location,
        "instructor_employee_id": session.instructor_employee_id.id if session.instructor_employee_id else False,
        "instructor_user_id": session.instructor_user_id.id if session.instructor_user_id else False,
        "capacity": session.capacity,
        "state": session.state,
        "approved_enrollment_count": session.approved_enrollment_count,
        "available_seat_count": session.available_seat_count,
        "notes": session.notes,
    }


def _serialize_enrollment(enr):
    return {
        "id": enr.id,
        "session_id": enr.session_id.id if enr.session_id else False,
        "course_id": enr.course_id.id if enr.course_id else False,
        "employee_id": enr.employee_id.id if enr.employee_id else False,
        "company_id": enr.company_id.id if enr.company_id else False,
        "request_date": enr.request_date,
        "state": enr.state,
        "approval_user_id": enr.approval_user_id.id if enr.approval_user_id else False,
        "approval_date": enr.approval_date,
        "attendance_status": enr.attendance_status,
        "attendance_marked_by": enr.attendance_marked_by.id if enr.attendance_marked_by else False,
        "attendance_marked_on": enr.attendance_marked_on,
        "score": enr.score,
        "completion_date": enr.completion_date,
        "certificate_id": enr.certificate_id.id if enr.certificate_id else False,
        "reason_reject": enr.reason_reject,
        "reason_cancel": enr.reason_cancel,
        "notes": enr.notes,
    }


def _serialize_certificate(cert):
    return {
        "id": cert.id,
        "name": cert.name,
        "employee_id": cert.employee_id.id if cert.employee_id else False,
        "course_id": cert.course_id.id if cert.course_id else False,
        "company_id": cert.company_id.id if cert.company_id else False,
        "enrollment_id": cert.enrollment_id.id if cert.enrollment_id else False,
        "issue_date": cert.issue_date,
        "expiry_date": cert.expiry_date,
        "state": cert.state,
        "revoked_date": cert.revoked_date,
        "revoked_by": cert.revoked_by.id if cert.revoked_by else False,
        "revoked_reason": cert.revoked_reason,
        "attachment_id": cert.attachment_id.id if cert.attachment_id else False,
        "external_reference": cert.external_reference,
    }


def _handle_exception(e):
    """Map Odoo exceptions to JSON errors."""
    if isinstance(e, AccessError):
        return _json_response({"error": "access_error", "message": str(e)}, status=403)
    if isinstance(e, (UserError, ValidationError)):
        return _json_response({"error": "user_error", "message": str(e)}, status=400)
    return _json_response({"error": "server_error", "message": str(e)}, status=500)


def _is_training_manager():
    return request.env.user.has_group("hr_training.group_training_manager")


def _current_employee():
    """Return hr.employee record linked to current user (if any)."""
    return request.env["hr.employee"].search([("user_id", "=", request.env.user.id)], limit=1)


class HrTrainingRestApiController(http.Controller):
    """
    REST-style APIs for hr_training.

    Notes:
    - All endpoints require an authenticated Odoo session (auth='user').
    - Access control is enforced by Odoo ACLs/record rules; we do NOT blanket sudo().
    - Write operations that should be restricted to HR Training Managers additionally check group.
    """

    # -------------------------
    # Courses
    # -------------------------
    @http.route("/hr_training/api/courses", type="http", auth="user", methods=["GET"], csrf=False)
    def list_courses(self, **query):
        try:
            limit = _int(query.get("limit"), 50)
            offset = _int(query.get("offset"), 0)
            active = _bool(query.get("active"), None)
            name = query.get("name")

            domain = []
            if active is not None:
                domain.append(("active", "=", active))
            if name:
                domain.append(("name", "ilike", name))

            Course = request.env["hr.training.course"]
            records = Course.search(domain, limit=limit, offset=offset, order="name asc, id asc")
            total = Course.search_count(domain)

            return _json_response(
                {
                    "data": [_serialize_course(c) for c in records],
                    "meta": {"total": total, "limit": limit, "offset": offset},
                }
            )
        except Exception as e:
            return _handle_exception(e)

    @http.route("/hr_training/api/courses/<int:course_id>", type="http", auth="user", methods=["GET"], csrf=False)
    def get_course(self, course_id, **_query):
        try:
            course = request.env["hr.training.course"].browse(course_id).exists()
            if not course:
                return _json_response({"error": "not_found", "message": "Course not found"}, status=404)
            return _json_response({"data": _serialize_course(course)})
        except Exception as e:
            return _handle_exception(e)

    @http.route("/hr_training/api/courses", type="http", auth="user", methods=["POST"], csrf=False)
    def create_course(self, **_query):
        try:
            if not _is_training_manager():
                raise AccessError(_("Only Training Managers can create courses."))
            body = _parse_json_body()
            vals = {
                k: body.get(k)
                for k in (
                    "name",
                    "code",
                    "active",
                    "company_id",
                    "category_id",
                    "description",
                    "is_mandatory",
                    "validity_months",
                    "issues_certificate",
                    "evaluation_mode",
                    "require_attendance",
                    "allow_self_enroll",
                    "requires_manager_approval",
                )
                if k in body
            }
            # M2M write command
            if "prerequisite_course_ids" in body:
                vals["prerequisite_course_ids"] = [(6, 0, body.get("prerequisite_course_ids") or [])]

            course = request.env["hr.training.course"].create(vals)
            return _json_response({"data": _serialize_course(course)}, status=201)
        except Exception as e:
            return _handle_exception(e)

    @http.route("/hr_training/api/courses/<int:course_id>", type="http", auth="user", methods=["PUT"], csrf=False)
    def update_course(self, course_id, **_query):
        try:
            if not _is_training_manager():
                raise AccessError(_("Only Training Managers can update courses."))
            course = request.env["hr.training.course"].browse(course_id).exists()
            if not course:
                return _json_response({"error": "not_found", "message": "Course not found"}, status=404)

            body = _parse_json_body()
            vals = {
                k: body.get(k)
                for k in (
                    "name",
                    "code",
                    "active",
                    "company_id",
                    "category_id",
                    "description",
                    "is_mandatory",
                    "validity_months",
                    "issues_certificate",
                    "evaluation_mode",
                    "require_attendance",
                    "allow_self_enroll",
                    "requires_manager_approval",
                )
                if k in body
            }
            if "prerequisite_course_ids" in body:
                vals["prerequisite_course_ids"] = [(6, 0, body.get("prerequisite_course_ids") or [])]

            course.write(vals)
            return _json_response({"data": _serialize_course(course)})
        except Exception as e:
            return _handle_exception(e)

    # -------------------------
    # Sessions
    # -------------------------
    @http.route("/hr_training/api/sessions", type="http", auth="user", methods=["GET"], csrf=False)
    def list_sessions(self, **query):
        try:
            limit = _int(query.get("limit"), 50)
            offset = _int(query.get("offset"), 0)
            course_id = _int(query.get("course_id"))
            state = query.get("state")

            domain = []
            if course_id:
                domain.append(("course_id", "=", course_id))
            if state:
                domain.append(("state", "=", state))

            Session = request.env["hr.training.session"]
            records = Session.search(domain, limit=limit, offset=offset, order="start_datetime desc, id desc")
            total = Session.search_count(domain)

            return _json_response(
                {
                    "data": [_serialize_session(s) for s in records],
                    "meta": {"total": total, "limit": limit, "offset": offset},
                }
            )
        except Exception as e:
            return _handle_exception(e)

    @http.route("/hr_training/api/sessions/<int:session_id>", type="http", auth="user", methods=["GET"], csrf=False)
    def get_session(self, session_id, **_query):
        try:
            session = request.env["hr.training.session"].browse(session_id).exists()
            if not session:
                return _json_response({"error": "not_found", "message": "Session not found"}, status=404)
            return _json_response({"data": _serialize_session(session)})
        except Exception as e:
            return _handle_exception(e)

    @http.route("/hr_training/api/sessions", type="http", auth="user", methods=["POST"], csrf=False)
    def create_session(self, **_query):
        try:
            if not _is_training_manager():
                raise AccessError(_("Only Training Managers can create sessions."))
            body = _parse_json_body()
            vals = {
                k: body.get(k)
                for k in (
                    "course_id",
                    "start_datetime",
                    "end_datetime",
                    "location",
                    "instructor_employee_id",
                    "instructor_user_id",
                    "capacity",
                    "notes",
                )
                if k in body
            }
            session = request.env["hr.training.session"].create(vals)
            return _json_response({"data": _serialize_session(session)}, status=201)
        except Exception as e:
            return _handle_exception(e)

    @http.route("/hr_training/api/sessions/<int:session_id>", type="http", auth="user", methods=["PUT"], csrf=False)
    def update_session(self, session_id, **_query):
        try:
            if not _is_training_manager():
                raise AccessError(_("Only Training Managers can update sessions."))
            session = request.env["hr.training.session"].browse(session_id).exists()
            if not session:
                return _json_response({"error": "not_found", "message": "Session not found"}, status=404)

            body = _parse_json_body()
            vals = {
                k: body.get(k)
                for k in (
                    "course_id",
                    "start_datetime",
                    "end_datetime",
                    "location",
                    "instructor_employee_id",
                    "instructor_user_id",
                    "capacity",
                    "state",
                    "notes",
                )
                if k in body
            }
            session.write(vals)
            return _json_response({"data": _serialize_session(session)})
        except Exception as e:
            return _handle_exception(e)

    # -------------------------
    # Enrollments
    # -------------------------
    @http.route("/hr_training/api/enrollments", type="http", auth="user", methods=["GET"], csrf=False)
    def list_enrollments(self, **query):
        try:
            limit = _int(query.get("limit"), 50)
            offset = _int(query.get("offset"), 0)
            session_id = _int(query.get("session_id"))
            employee_id = _int(query.get("employee_id"))
            state = query.get("state")

            domain = []
            if session_id:
                domain.append(("session_id", "=", session_id))
            if employee_id:
                domain.append(("employee_id", "=", employee_id))
            if state:
                domain.append(("state", "=", state))

            Enrollment = request.env["hr.training.enrollment"]
            records = Enrollment.search(domain, limit=limit, offset=offset, order="request_date desc, id desc")
            total = Enrollment.search_count(domain)

            return _json_response(
                {
                    "data": [_serialize_enrollment(e) for e in records],
                    "meta": {"total": total, "limit": limit, "offset": offset},
                }
            )
        except Exception as e:
            return _handle_exception(e)

    @http.route("/hr_training/api/enrollments/<int:enrollment_id>", type="http", auth="user", methods=["GET"], csrf=False)
    def get_enrollment(self, enrollment_id, **_query):
        try:
            enr = request.env["hr.training.enrollment"].browse(enrollment_id).exists()
            if not enr:
                return _json_response({"error": "not_found", "message": "Enrollment not found"}, status=404)
            return _json_response({"data": _serialize_enrollment(enr)})
        except Exception as e:
            return _handle_exception(e)

    @http.route("/hr_training/api/enrollments", type="http", auth="user", methods=["POST"], csrf=False)
    def create_enrollment(self, **_query):
        try:
            body = _parse_json_body()

            # Defaults: if employee_id not provided, use current user's employee if available.
            employee_id = body.get("employee_id")
            if not employee_id:
                emp = _current_employee()
                if emp:
                    employee_id = emp.id

            vals = {
                "session_id": body.get("session_id"),
                "employee_id": employee_id,
            }

            if not vals["session_id"] or not vals["employee_id"]:
                raise UserError(_("session_id and employee_id are required (employee_id can be inferred from the logged-in user if linked)."))

            # If user tries to enroll another employee, restrict to Training Managers.
            if int(vals["employee_id"]) != (_current_employee().id if _current_employee() else -1):
                if not _is_training_manager():
                    raise AccessError(_("You can only create enrollments for yourself."))

            enr = request.env["hr.training.enrollment"].create(vals)
            return _json_response({"data": _serialize_enrollment(enr)}, status=201)
        except Exception as e:
            return _handle_exception(e)

    @http.route("/hr_training/api/enrollments/<int:enrollment_id>/manager_approve", type="http", auth="user", methods=["POST"], csrf=False)
    def enrollment_manager_approve(self, enrollment_id, **_query):
        try:
            enr = request.env["hr.training.enrollment"].browse(enrollment_id).exists()
            if not enr:
                return _json_response({"error": "not_found", "message": "Enrollment not found"}, status=404)
            enr.action_manager_approve()
            return _json_response({"data": _serialize_enrollment(enr)})
        except Exception as e:
            return _handle_exception(e)

    @http.route("/hr_training/api/enrollments/<int:enrollment_id>/approve", type="http", auth="user", methods=["POST"], csrf=False)
    def enrollment_approve(self, enrollment_id, **_query):
        try:
            if not _is_training_manager():
                raise AccessError(_("Only Training Managers can approve enrollments."))
            enr = request.env["hr.training.enrollment"].browse(enrollment_id).exists()
            if not enr:
                return _json_response({"error": "not_found", "message": "Enrollment not found"}, status=404)
            enr.action_approve()
            return _json_response({"data": _serialize_enrollment(enr)})
        except Exception as e:
            return _handle_exception(e)

    @http.route("/hr_training/api/enrollments/<int:enrollment_id>/reject", type="http", auth="user", methods=["POST"], csrf=False)
    def enrollment_reject(self, enrollment_id, **_query):
        try:
            if not _is_training_manager():
                raise AccessError(_("Only Training Managers can reject enrollments."))
            enr = request.env["hr.training.enrollment"].browse(enrollment_id).exists()
            if not enr:
                return _json_response({"error": "not_found", "message": "Enrollment not found"}, status=404)

            body = _parse_json_body()
            if "reason_reject" in body:
                enr.reason_reject = body.get("reason_reject")

            enr.action_reject()
            return _json_response({"data": _serialize_enrollment(enr)})
        except Exception as e:
            return _handle_exception(e)

    @http.route("/hr_training/api/enrollments/<int:enrollment_id>/cancel", type="http", auth="user", methods=["POST"], csrf=False)
    def enrollment_cancel(self, enrollment_id, **_query):
        try:
            enr = request.env["hr.training.enrollment"].browse(enrollment_id).exists()
            if not enr:
                return _json_response({"error": "not_found", "message": "Enrollment not found"}, status=404)

            # Allow self-cancel (record rules apply). HR managers can cancel any.
            body = _parse_json_body()
            if "reason_cancel" in body:
                enr.reason_cancel = body.get("reason_cancel")

            enr.action_cancel()
            return _json_response({"data": _serialize_enrollment(enr)})
        except Exception as e:
            return _handle_exception(e)

    @http.route("/hr_training/api/enrollments/<int:enrollment_id>/attendance", type="http", auth="user", methods=["POST"], csrf=False)
    def enrollment_mark_attendance(self, enrollment_id, **_query):
        try:
            # Typically instructor/HR; record rules will limit access, and model method also validates state.
            enr = request.env["hr.training.enrollment"].browse(enrollment_id).exists()
            if not enr:
                return _json_response({"error": "not_found", "message": "Enrollment not found"}, status=404)

            body = _parse_json_body()
            status = body.get("status")
            enr.action_mark_attendance(status)
            return _json_response({"data": _serialize_enrollment(enr)})
        except Exception as e:
            return _handle_exception(e)

    @http.route("/hr_training/api/enrollments/<int:enrollment_id>/complete", type="http", auth="user", methods=["POST"], csrf=False)
    def enrollment_complete(self, enrollment_id, **_query):
        try:
            enr = request.env["hr.training.enrollment"].browse(enrollment_id).exists()
            if not enr:
                return _json_response({"error": "not_found", "message": "Enrollment not found"}, status=404)

            enr.action_mark_completed()
            return _json_response({"data": _serialize_enrollment(enr)})
        except Exception as e:
            return _handle_exception(e)

    @http.route("/hr_training/api/enrollments/<int:enrollment_id>/fail", type="http", auth="user", methods=["POST"], csrf=False)
    def enrollment_fail(self, enrollment_id, **_query):
        try:
            enr = request.env["hr.training.enrollment"].browse(enrollment_id).exists()
            if not enr:
                return _json_response({"error": "not_found", "message": "Enrollment not found"}, status=404)

            enr.action_mark_failed()
            return _json_response({"data": _serialize_enrollment(enr)})
        except Exception as e:
            return _handle_exception(e)

    # -------------------------
    # Certificates
    # -------------------------
    @http.route("/hr_training/api/certificates", type="http", auth="user", methods=["GET"], csrf=False)
    def list_certificates(self, **query):
        try:
            limit = _int(query.get("limit"), 50)
            offset = _int(query.get("offset"), 0)
            employee_id = _int(query.get("employee_id"))
            course_id = _int(query.get("course_id"))
            state = query.get("state")

            domain = []
            if employee_id:
                domain.append(("employee_id", "=", employee_id))
            if course_id:
                domain.append(("course_id", "=", course_id))
            if state:
                domain.append(("state", "=", state))

            Certificate = request.env["hr.training.certificate"]
            records = Certificate.search(domain, limit=limit, offset=offset, order="issue_date desc, id desc")
            total = Certificate.search_count(domain)

            return _json_response(
                {
                    "data": [_serialize_certificate(c) for c in records],
                    "meta": {"total": total, "limit": limit, "offset": offset},
                }
            )
        except Exception as e:
            return _handle_exception(e)

    @http.route("/hr_training/api/certificates/<int:certificate_id>", type="http", auth="user", methods=["GET"], csrf=False)
    def get_certificate(self, certificate_id, **_query):
        try:
            cert = request.env["hr.training.certificate"].browse(certificate_id).exists()
            if not cert:
                return _json_response({"error": "not_found", "message": "Certificate not found"}, status=404)
            return _json_response({"data": _serialize_certificate(cert)})
        except Exception as e:
            return _handle_exception(e)

    @http.route("/hr_training/api/certificates/<int:certificate_id>/revoke", type="http", auth="user", methods=["POST"], csrf=False)
    def revoke_certificate(self, certificate_id, **_query):
        try:
            if not _is_training_manager():
                raise AccessError(_("Only Training Managers can revoke certificates."))
            cert = request.env["hr.training.certificate"].browse(certificate_id).exists()
            if not cert:
                return _json_response({"error": "not_found", "message": "Certificate not found"}, status=404)

            body = _parse_json_body()
            if "revoked_reason" in body:
                cert.revoked_reason = body.get("revoked_reason")

            cert.action_revoke()
            return _json_response({"data": _serialize_certificate(cert)})
        except Exception as e:
            return _handle_exception(e)
