# 历史 Case 与知识边界

V1 必需的是权限内、已解决历史 Case 检索。记录含 caseId、caseType、产品/步骤/Tool/Recipe、症状特征、工程师确认根因、resolution、closedAt、权限标签和版本。

相似度由代码组合结构化过滤与检索得分，并向用户展示匹配理由。只返回当前用户可见内容；未确认或结论冲突的案例标记，不进入“已确认根因”统计。当前 Case 的假设不能因历史频次直接确认为真。

SOP、Troubleshooting Guide、Equipment Manual 等全面知识检索属于 V2。接入时保存 documentId、version、effectiveAt、owner、permission 和段落引用；过期文档不得作为当前操作建议的唯一依据。
