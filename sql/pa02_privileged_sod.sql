-- ITGC-PA-02  Privileged access approver must be independent of the grantee
SELECT 'ITGC-PA-02' AS control_id, a.grant_id AS source_record_id, a.employee_id, a.system_id,
       a.access_level, p.approval_id, p.approver_id
FROM user_access_log a
JOIN privileged_access_approvals p ON p.request_ticket = a.request_ticket
WHERE a.date_granted BETWEEN :period_start AND :period_end
  AND a.access_level IN (SELECT access_level FROM privileged_levels)
  AND p.approver_id = a.employee_id;
