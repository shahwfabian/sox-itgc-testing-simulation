-- ITGC-UA-03  HR separation notification within :hr_sla_bd business day(s) of termination
WITH t AS (
    SELECT t.*,
           (SELECT d.cal_date FROM dim_date d
             WHERE d.cal_date > t.termination_date AND d.is_business_day = 1
             ORDER BY d.cal_date LIMIT 1 OFFSET :hr_sla_bd - 1) AS notify_deadline
    FROM termination_log t
    WHERE t.termination_date BETWEEN :period_start AND :period_end
)
SELECT 'ITGC-UA-03' AS control_id, employee_id AS source_record_id, employee_id,
       termination_type, termination_date, notify_deadline, hr_notified_date
FROM t
WHERE hr_notified_date IS NULL OR hr_notified_date > notify_deadline
ORDER BY termination_date;
