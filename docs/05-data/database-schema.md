# 持久化建议

这是逻辑 Schema，不绑定具体数据库方言。实现迁移前由后端团队确定字段类型、分区和保留期。

| 表 | 关键字段 / 约束 |
|---|---|
| ai_analysis_task | id, tenant_id, case_id, case_version, permission_scope_hash, status, phase, context_hash, lease_token, agent/model/prompt/schema versions, timestamps；终态 CAS |
| ai_task_event | task_id, sequence, type, payload_redacted, occurred_at；unique(task_id, sequence) |
| ai_outbox | id, aggregate_id, type, payload, published_at；与状态变更同事务 |
| ai_tool_execution | id, task_id, tool_id, args_hash, attempt, status, source_version, latency_ms, result_ref, error_code |
| ai_evidence | id, task_id, kind, observation_json, source_json, entity_refs, event_time, retrieved_at, quality_json, raw_ref |
| ai_model_assessment | id, task_id, question_id/version, primitive, state_hash, answer_json, requested_model, resolved_model, usage_json |
| ai_report | task_id, version, schema_version, report_json, created_at；unique(task_id, version)，不可变 |
| ai_engineer_review | id, task_id, report_version, revision, status, helpful, root_cause, comment, reviewer_id, timestamps |
| ai_casebook_archive | id, review_id, idempotency_key, external_id, status, error_code, timestamps |

索引至少覆盖 tenant+case+created_at、task+sequence、task+status。大体积原始 Tool Result 存受控对象存储，数据库保留加密引用与校验哈希。JSON 字段仍由应用 Schema 校验。

任务与事件必须同事务提交；报告发布和终态事件同事务。归档使用唯一 idempotency key。租户隔离优先由数据库策略和服务授权双层实施。
