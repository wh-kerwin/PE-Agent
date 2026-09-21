# 未决事项与工作清单

## 外部输入（阻塞生产接入）

- [ ] 宿主 Case API、caseVersion、Case 类型与入口权限
- [ ] SSO/IAM 委托、租户与关联实体授权方式
- [ ] Lot/Wafer/Tool/Recipe/SPC/FDC 接口、单位、时区、SLA
- [ ] 历史 Case/Case Book 结构与幂等写入协议
- [ ] TypeSafe 企业条款、数据区域/ZDR、API Key 和实际账号限额
- [ ] 已确认 Yield Drop 历史样本与专家标注资源

## 已完成实现

- [x] M1 mock-first Dashboard vertical slice：FastAPI、Vue 嵌入式分析抽屉与合成场景
- [x] 任务、outbox、持久化事件、worker lease/fence、取消与恢复基础能力
- [x] Mock platform adapters、Evidence 规范化与越权边界校验
- [x] Recorded Jev adapter、Choice/Score/Noul 契约与 synthetic live opt-in smoke test
- [x] Report Schema、证据引用、身份元数据与语义校验
- [x] Engineer Review、mock-only Case Book archive、幂等与 revision 语义
- [x] SSE replay、cursor 限制、heartbeat、terminal close 与周期性权限复核
- [x] PostgreSQL migration、生命周期 CHECK 约束、并发/租约/回滚集成测试
- [x] Compose、Helm、非 root 容器、CI、preflight 与 contract/deployment validation
- [x] 安全回归：scope hash 服务端派生、禁止权限范围扩张、生产 fail-closed

## 待完成或受阻

- [ ] 安装前端 lockfile 依赖后运行 typecheck、unit test、build、Playwright E2E 与浏览器验收（当前被环境策略阻塞）
- [ ] 实际 Compose image build/up 与 nginx 非 root/read-only 浏览器验收
- [ ] Helm CLI lint/template 与 clean-checkout smoke test
- [ ] 宿主 Case API、SSO/IAM、制造平台只读 adapters 与真实 Case Book adapter
- [ ] TypeSafe 企业条款、数据区域/ZDR、实际 API key/账号与 live 验收
- [ ] 持久化 tool execution 审计、normalized Evidence、model assessment 元数据
- [ ] worker lease renewal/checkpoint resume 与 SIGTERM/已安装 wheel 运行验收
- [ ] 黄金集、CJK/故障/越权扩展测试和 shadow pilot

## 已完成的设计资产

- [x] V1 边界、嵌入交互、任务状态与错误语义
- [x] 官方 Jev 能力核实与职责映射
- [x] API/SSE/Tool/Report 机器契约和合成样例

负责人、日期和优先级由项目排期工具维护，本文不伪造承诺。
