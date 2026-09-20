# Database Schema

## ai_analysis_task

- id
- case_id
- status
- mode
- agent_version
- model_version
- prompt_version
- created_by
- started_at
- completed_at
- created_at
- updated_at

## ai_investigation_plan

- id
- task_id
- version
- step_no
- title
- status
- depends_on
- created_at

## ai_tool_execution

- id
- task_id
- plan_step_id
- tool_id
- input_hash
- status
- latency
- result_ref
- error_code
- created_at

## ai_evidence

- id
- task_id
- source_type
- source_id
- metric
- value
- unit
- event_time
- status
- raw_ref
- created_at

## ai_finding

- id
- task_id
- type
- title
- description
- evidence_ids
- created_at

## ai_hypothesis

- id
- task_id
- root_cause
- confidence
- supporting_evidence
- contradicting_evidence
- uncertainties
- created_at

## ai_recommendation

- id
- task_id
- type
- priority
- action
- reason
- created_at

## ai_action

- id
- task_id
- recommendation_id
- risk_level
- approval_policy
- status
- idempotency_key
- created_at

## ai_approval

- id
- action_id
- approver
- decision
- reason
- decided_at

## ai_execution

- id
- action_id
- execution_status
- result_ref
- started_at
- completed_at

## ai_verification

- id
- action_id
- status
- metrics
- conclusion
- verified_at
