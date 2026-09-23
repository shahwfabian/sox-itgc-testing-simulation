-- ITGC-PA-01  Privileged grants must match an approval record (ticket, employee, system, level)
--             dated on or before the grant.
SELECT 'ITGC-PA-01' AS control_id, a.grant_id AS source_record_id, a.employee_id, a.system_id,
       a.access_level, a.request_ticket, a.date_granted,
       p.approval_id, p.access_level_approved, p.system_id AS approved_system, p.approval_date,
       CASE WHEN p.approval_id IS NULL THEN 'No approval record in register; ' ELSE '' END ||
       CASE WHEN p.approval_id IS NOT NULL AND p.employee_id <> a.employee_id THEN 'Different employee; ' ELSE '' END ||
       CASE WHEN p.approval_id IS NOT NULL AND p.system_id <> a.system_id THEN 'Different system; ' ELSE '' END ||
       CASE WHEN p.approval_id IS NOT NULL AND p.access_level_approved <> a.access_level THEN 'Level mismatch; ' ELSE '' END ||
       CASE WHEN p.approval_date > a.date_granted THEN 'Approved after grant; ' ELSE '' END AS exception_type
FROM user_access_log a
LEFT JOIN privileged_access_approvals p ON p.request_ticket = a.request_ticket
WHERE a.date_granted BETWEEN :period_start AND :period_end
  AND a.access_level IN (SELECT access_level FROM privileged_levels)
  AND (p.approval_id IS NULL
       OR p.employee_id <> a.employee_id
       OR p.system_id <> a.system_id
       OR p.access_level_approved <> a.access_level
       OR p.approval_date > a.date_granted)
ORDER BY a.date_granted;
