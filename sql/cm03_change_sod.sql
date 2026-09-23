-- ITGC-CM-03  Segregation of duties: requester cannot approve own change
SELECT 'ITGC-CM-03' AS control_id, c.change_id AS source_record_id, c.system_id,
       c.requested_by, c.approved_by, c.implementation_date
FROM change_log c
WHERE c.implementation_date BETWEEN :period_start AND :period_end || ' 23:59'
  AND c.approved_by IS NOT NULL
  AND c.approved_by = c.requested_by;
