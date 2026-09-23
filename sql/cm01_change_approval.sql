-- ITGC-CM-01  Changes approved before implementation; emergency changes approved no later than
--             the :emergency_bd-th business day after implementation.
SELECT 'ITGC-CM-01' AS control_id, c.change_id AS source_record_id, c.system_id, c.change_type,
       c.requested_by, c.approved_by, c.approval_date, c.implementation_date,
       CASE WHEN c.approved_by IS NULL OR c.approval_date IS NULL THEN 'No approver / approval date recorded'
            WHEN c.change_type <> 'Emergency' THEN 'Approved after implementation'
            ELSE 'Emergency change approved outside 2-BD window' END AS exception_type
FROM change_log c
WHERE c.implementation_date BETWEEN :period_start AND :period_end || ' 23:59'
  AND (
        c.approved_by IS NULL OR c.approval_date IS NULL
     OR (c.change_type <> 'Emergency' AND c.approval_date > c.implementation_date)
     OR (c.change_type = 'Emergency'
         AND DATE(c.approval_date) > (SELECT d.cal_date FROM dim_date d
                                       WHERE d.cal_date > DATE(c.implementation_date) AND d.is_business_day = 1
                                       ORDER BY d.cal_date LIMIT 1 OFFSET :emergency_bd - 1))
      )
ORDER BY c.implementation_date;
