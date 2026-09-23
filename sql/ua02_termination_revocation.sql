-- ITGC-UA-02  Timely revocation of terminated users (SLA = :termination_sla_bd business days)
-- Population: every grant active on the termination date of an in-period termination.
WITH active_at_term AS (
    SELECT t.employee_id, t.termination_date, a.grant_id, a.system_id, a.access_level, a.access_end_date
    FROM termination_log t
    JOIN user_access_log a ON a.employee_id = t.employee_id
    WHERE t.termination_date BETWEEN :period_start AND :period_end
      AND a.date_granted <= t.termination_date
      AND (a.access_end_date IS NULL OR a.access_end_date >= t.termination_date)
),
with_deadline AS (
    SELECT x.*,
           (SELECT d.cal_date FROM dim_date d
             WHERE d.cal_date > x.termination_date AND d.is_business_day = 1
             ORDER BY d.cal_date LIMIT 1 OFFSET :termination_sla_bd - 1) AS revoke_deadline,
           (SELECT COUNT(*) FROM dim_date d
             WHERE d.cal_date > x.termination_date
               AND d.cal_date <= COALESCE(x.access_end_date, :as_of)
               AND d.is_business_day = 1) AS bd_elapsed
    FROM active_at_term x
)
SELECT 'ITGC-UA-02' AS control_id, grant_id AS source_record_id, employee_id, system_id, access_level,
       termination_date, revoke_deadline, access_end_date, bd_elapsed,
       CASE WHEN access_end_date IS NULL THEN 'Open' ELSE 'Closed' END AS status
FROM with_deadline
WHERE access_end_date IS NULL OR access_end_date > revoke_deadline
ORDER BY termination_date, employee_id;
