-- ITGC-CM-02  Documented rollback plan (normalizes Yes / Y / yes spellings)
SELECT 'ITGC-CM-02' AS control_id, c.change_id AS source_record_id, c.system_id, c.change_type,
       c.requested_by, c.implementation_date, c.rollback_plan
FROM change_log c
WHERE c.implementation_date BETWEEN :period_start AND :period_end || ' 23:59'
  AND UPPER(TRIM(COALESCE(c.rollback_plan, ''))) NOT IN ('YES', 'Y')
ORDER BY c.implementation_date;
