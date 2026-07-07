-- ============================================================
-- SQL Crack Friendly Query Examples
-- Purpose: open this file in SQL Crack to visualize query flows.
-- These are SELECT/JOIN queries based on your database schema.
-- ============================================================

-- ============================================================
-- 01. Employee list with user, role, department, position, manager
-- Flow:
-- employees -> users -> roles -> departments -> positions -> manager employee
-- ============================================================
SELECT
    e.employee_id,
    e.employee_code,
    e.full_name,
    e.phone,
    e.status AS employee_status,
    u.email,
    u.status AS user_status,
    r.name AS role_name,
    d.name AS department_name,
    p.name AS position_name,
    m.full_name AS manager_name
FROM employees AS e
LEFT JOIN users AS u
    ON u.user_id = e.user_id
LEFT JOIN roles AS r
    ON r.role_id = u.role_id
LEFT JOIN departments AS d
    ON d.department_id = e.department_id
LEFT JOIN positions AS p
    ON p.position_id = e.position_id
LEFT JOIN employees AS m
    ON m.employee_id = e.manager_id
WHERE e.status = 'active'
ORDER BY e.full_name;

-- ============================================================
-- 02. Current face profile status of each employee
-- Flow:
-- employees -> face_profiles
-- ============================================================
SELECT
    e.employee_id,
    e.employee_code,
    e.full_name,
    fp.profile_id,
    fp.status AS face_profile_status,
    fp.qdrant_collection,
    fp.embedding_model,
    fp.embedding_version,
    fp.created_at AS face_registered_at
FROM employees AS e
LEFT JOIN face_profiles AS fp
    ON fp.employee_id = e.employee_id
WHERE e.status = 'active'
ORDER BY e.full_name;

-- ============================================================
-- 03. Attendance records with employee and shift information
-- Flow:
-- attendance_records -> employees -> departments -> work_shifts
-- ============================================================
SELECT
    ar.record_id,
    ar.work_date,
    e.employee_code,
    e.full_name,
    d.name AS department_name,
    ws.name AS shift_name,
    ws.start_time AS shift_start_time,
    ws.end_time AS shift_end_time,
    ar.check_in_time,
    ar.check_out_time,
    ar.status,
    ar.late_minutes,
    ar.early_leave_minutes,
    ar.worked_minutes,
    ar.source
FROM attendance_records AS ar
JOIN employees AS e
    ON e.employee_id = ar.employee_id
LEFT JOIN departments AS d
    ON d.department_id = e.department_id
LEFT JOIN work_shifts AS ws
    ON ws.shift_id = ar.shift_id
WHERE ar.work_date = CURRENT_DATE
ORDER BY ar.work_date DESC, e.full_name;

-- ============================================================
-- 04. Raw attendance events from AI service
-- Flow:
-- attendance_events -> employees -> face_profiles
-- ============================================================
SELECT
    ae.event_id,
    ae.event_time,
    ae.event_type,
    ae.confidence_score,
    ae.anti_spoof_score,
    ae.is_accepted,
    ae.rejection_reason,
    e.employee_code,
    e.full_name,
    fp.profile_id AS face_profile_id,
    fp.status AS face_profile_status
FROM attendance_events AS ae
LEFT JOIN employees AS e
    ON e.employee_id = ae.employee_id
LEFT JOIN face_profiles AS fp
    ON fp.employee_id = e.employee_id
WHERE ae.event_time >= CURRENT_DATE
ORDER BY ae.event_time DESC;

-- ============================================================
-- 05. Leave requests with approver and leave type
-- Flow:
-- leave_requests -> employees -> leave_types -> approver employee
-- ============================================================
SELECT
    lr.request_id,
    e.employee_code,
    e.full_name,
    lt.name AS leave_type_name,
    lr.start_date,
    lr.end_date,
    lr.time_type,
    lr.total_days,
    lr.reason,
    lr.status,
    approver.full_name AS approved_by_name,
    lr.approved_at,
    lr.rejection_reason
FROM leave_requests AS lr
JOIN employees AS e
    ON e.employee_id = lr.employee_id
JOIN leave_types AS lt
    ON lt.leave_type_id = lr.leave_type_id
LEFT JOIN employees AS approver
    ON approver.employee_id = lr.approved_by
ORDER BY lr.created_at DESC;

-- ============================================================
-- 06. Pending attendance correction requests
-- Flow:
-- correction_requests -> employees -> attendance_records -> reviewer employee
-- ============================================================
SELECT
    acr.request_id,
    e.employee_code,
    e.full_name,
    ar.work_date,
    ar.check_in_time AS old_check_in_time,
    ar.check_out_time AS old_check_out_time,
    acr.requested_check_in,
    acr.requested_check_out,
    acr.reason,
    acr.status,
    reviewer.full_name AS reviewed_by_name,
    acr.reviewed_at,
    acr.rejection_reason
FROM attendance_correction_requests AS acr
JOIN employees AS e
    ON e.employee_id = acr.employee_id
LEFT JOIN attendance_records AS ar
    ON ar.record_id = acr.attendance_record_id
LEFT JOIN employees AS reviewer
    ON reviewer.employee_id = acr.reviewed_by
WHERE acr.status = 'pending'
ORDER BY acr.created_at DESC;

-- ============================================================
-- 07. Employee shift assignment timeline
-- Flow:
-- employee_shift_assignments -> employees -> work_shifts -> creator user
-- ============================================================
SELECT
    esa.assignment_id,
    e.employee_code,
    e.full_name,
    ws.name AS shift_name,
    ws.start_time,
    ws.end_time,
    esa.effective_date,
    esa.end_date,
    creator.email AS created_by_email
FROM employee_shift_assignments AS esa
JOIN employees AS e
    ON e.employee_id = esa.employee_id
JOIN work_shifts AS ws
    ON ws.shift_id = esa.shift_id
LEFT JOIN users AS creator
    ON creator.user_id = esa.created_by
ORDER BY e.full_name, esa.effective_date DESC;

-- ============================================================
-- 08. Department manager mapping
-- Flow:
-- department_managers -> departments -> employees
-- ============================================================
SELECT
    d.department_id,
    d.name AS department_name,
    d.code AS department_code,
    manager.employee_id AS manager_id,
    manager.employee_code AS manager_code,
    manager.full_name AS manager_name,
    dm.assigned_at
FROM department_managers AS dm
JOIN departments AS d
    ON d.department_id = dm.department_id
JOIN employees AS manager
    ON manager.employee_id = dm.manager_id
ORDER BY d.name, manager.full_name;

-- ============================================================
-- 09. Attendance dashboard summary by department
-- Flow:
-- attendance_records -> employees -> departments -> aggregate
-- ============================================================
SELECT
    d.department_id,
    d.name AS department_name,
    ar.work_date,
    COUNT(*) AS total_records,
    COUNT(*) FILTER (WHERE ar.status = 'present') AS present_count,
    COUNT(*) FILTER (WHERE ar.status = 'late') AS late_count,
    COUNT(*) FILTER (WHERE ar.status = 'early_leave') AS early_leave_count,
    COUNT(*) FILTER (WHERE ar.status = 'absent') AS absent_count,
    SUM(ar.late_minutes) AS total_late_minutes,
    SUM(ar.worked_minutes) AS total_worked_minutes
FROM attendance_records AS ar
JOIN employees AS e
    ON e.employee_id = ar.employee_id
LEFT JOIN departments AS d
    ON d.department_id = e.department_id
WHERE ar.work_date BETWEEN CURRENT_DATE - INTERVAL '7 days' AND CURRENT_DATE
GROUP BY d.department_id, d.name, ar.work_date
ORDER BY ar.work_date DESC, d.name;

-- ============================================================
-- 10. Audit trail for one object type
-- Flow:
-- audit_logs -> users -> roles
-- ============================================================
SELECT
    al.log_id,
    al.created_at,
    al.action,
    al.object_type,
    al.object_id,
    al.old_value,
    al.new_value,
    al.reason,
    u.email AS performed_by_email,
    r.name AS performed_by_role
FROM audit_logs AS al
LEFT JOIN users AS u
    ON u.user_id = al.performed_by
LEFT JOIN roles AS r
    ON r.role_id = u.role_id
WHERE al.object_type = 'attendance_record'
ORDER BY al.created_at DESC;
