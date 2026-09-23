-- ITGC-UA-01  New user access approval
-- Exception: in-period non-privileged grant with no approver, or approved by the grantee.
SELECT 'ITGC-UA-01'      AS control_id,
       a.grant_id        AS source_record_id,
       a.employee_id, a.system_id, a.access_level, a.request_ticket, a.date_granted,
       CASE WHEN a.approver_id IS NULL THEN 'No approver recorded on grant'
            ELSE 'Grantee approved own access' END AS exception_type
FROM user_access_log a
WHERE a.date_granted BETWEEN :period_start AND :period_end
  AND a.access_level NOT IN (SELECT access_level FROM privileged_levels)
  AND (a.approver_id IS NULL OR a.approver_id = a.employee_id)
ORDER BY a.date_granted;
