-- 017_borderline_classification_lane.sql — Migration retroattiva per distinguere gli articoli BORDERLINE nel DB

UPDATE articles a
SET classification_lane = 'borderline'
FROM llm_request_ledger l
WHERE l.article_id = a.id
  AND a.classification_lane = 'complex'
  AND COALESCE(a.was_escalated, FALSE) = FALSE
  AND l.status = 'completed'
  AND (l.purpose LIKE 'classify:%' OR l.purpose = 'classify_article')
  AND LOWER(COALESCE(l.reasoning_effort, 'none')) = 'none';
