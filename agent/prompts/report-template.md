# Report rendering rules

Render only fields that passed report schema and semantic validation.

- Observed: format the linked evidence value, unit, entity and event time.
- Inferred: state the relationship and cite every evidence ID used.
- Hypothesis: use “Potential root cause”; include support, contradictions and missing evidence.
- Recommendation: describe an engineer action and rationale; never imply execution.
- Uncertainty: name missing source or conflicting evidence and its impact.

Do not add facts, causal language, probability labels, HTML, Markdown links, production status changes or hidden reasoning. The UI renders sections and source links.
