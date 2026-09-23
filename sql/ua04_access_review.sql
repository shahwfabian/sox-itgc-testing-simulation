-- ITGC-UA-04  Quarterly user access review: every system-quarter reviewed on time by a named reviewer
WITH expected AS (
    SELECT s.system_id, q.quarter
    FROM systems s
    CROSS JOIN (SELECT '2025-Q1' AS quarter UNION ALL SELECT '2025-Q2'
                UNION ALL SELECT '2025-Q3' UNION ALL SELECT '2025-Q4') q
)
SELECT 'ITGC-UA-04' AS control_id,
       COALESCE(r.review_id, 'UAR-' || e.quarter || '-' || e.system_id) AS source_record_id,
       e.system_id, e.quarter, r.due_date, r.completion_date, r.reviewer_id,
       CASE WHEN r.review_id IS NULL THEN 'Review not performed'
            WHEN r.completion_date IS NULL THEN 'Review not completed'
            WHEN r.reviewer_id IS NULL THEN 'No reviewer recorded'
            ELSE 'Review completed after due date' END AS exception_type
FROM expected e
LEFT JOIN access_reviews r ON r.system_id = e.system_id AND r.quarter = e.quarter
WHERE r.review_id IS NULL OR r.completion_date IS NULL OR r.reviewer_id IS NULL
   OR r.completion_date > r.due_date;
