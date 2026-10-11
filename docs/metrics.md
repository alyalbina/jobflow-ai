# Product metric contract

## Technical discovery

Collected messages are unique source/message records, including non-vacancy posts. Valid vacancies are unique currently available parsed jobs. Duplicate rate is `(live posts − distinct normalized content hashes) / live posts`; it measures repeated content across source posts, not transport retries. Exact hashing is not proof that two differently linked job templates are the same employer opening. Relevant vacancies means the current rule recommendation is Apply, not labelled ground truth.

Source attribution uses the original canonical job source. Cross-posts are not independent discoveries. Country/role breakdowns keep Unknown visible. Salary observations retain currency and period; missing values are excluded and never replaced by zero.

## Applications

Submission requires manual confirmation. Funnels use historical explicit membership in Saved, Applied, Screening, Interview and Offer. Each transition's numerator is the intersection with its preceding-stage cohort; its denominator is that recorded preceding cohort. Skipped stages are not inferred. Current status distribution is displayed separately.

Response rate = Applied applications with a recorded Screening, Interview, Test Assignment, Offer or Rejected event / all explicit Applied applications. Rejected is interpreted as a recorded recruiter rejection, not an automated no-response classification. First-response time uses the earliest qualifying event on/after the recorded application date. No Response does not count as a response. Right-censored active applications remain in the applied denominator; recent cohorts have less opportunity, so observed rates should be read with elapsed time.

## Matching quality

The positive class is manual user judgement that a vacancy is relevant for review/applying, not eventual hiring. Precision@10 uses the current top ten available ranked results (or the smaller available collection) only when every selected result has a user label. Recall is shown only for a fully labelled bounded available collection with at least one positive. Unlabelled jobs are never assumed negative. False positives/negatives refer only to labelled records and the current Apply recommendation. Preference changes can alter the ranking; they are not a controlled quality experiment.

## Measuring real usefulness after activation

Before launch, record a one-week manual-search baseline: minutes spent checking sources, useful unique vacancies, applications actually submitted and their dates. During use, record the same quantities weekly using Analytics → Your weekly measurement log (no browsing history or message surveillance). Discovery-to-application delay requires the actual first-discovered timestamp, not merely the channel publication date; JobFlow records `first_discovered_at` on initial persistence and reports intervals only with valid observed timestamps. Initial backfill is included and must be separated when interpreting monitoring latency. Label a bounded stable sample for precision/recall and track correction categories.

Compare descriptive weekly medians/rates with cohort size and time since application. The dashboard splits recorded outcomes by source, country, role and exact CV version with applied-cohort denominators; interpret only with adequate counts. Weekly quality panels use saved label-time scores at the 75 threshold, distinct from Precision@10 and the full Apply policy. Neither pre/post differences nor a handful of interviews establish that JobFlow or a particular CV caused better results. Technical ingestion/deduplication correctness is distinct from saved time, relevance quality and recruiter conversion. No measured business effect is currently claimed.
