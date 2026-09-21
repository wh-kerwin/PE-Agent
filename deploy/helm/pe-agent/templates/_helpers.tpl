{{- define "pe-agent.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "pe-agent.fullname" -}}
{{- printf "%s-%s" .Release.Name (include "pe-agent.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "pe-agent.labels" -}}
app.kubernetes.io/name: {{ include "pe-agent.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | quote }}
{{- end -}}

{{- define "pe-agent.selectorLabels" -}}
app.kubernetes.io/name: {{ include "pe-agent.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "pe-agent.podSecurityContext" -}}
runAsNonRoot: true
runAsUser: 10001
runAsGroup: 10001
fsGroup: 10001
seccompProfile:
  type: RuntimeDefault
{{- end -}}

{{- define "pe-agent.containerSecurityContext" -}}
allowPrivilegeEscalation: false
readOnlyRootFilesystem: true
capabilities:
  drop: ["ALL"]
{{- end -}}

{{- define "pe-agent.env" -}}
- name: PE_AGENT_DEPLOY_PROFILE
  value: {{ .Values.profile | quote }}
- name: PE_AGENT_ENVIRONMENT
  value: {{ .Values.config.environment | quote }}
- name: PE_AGENT_PLATFORM_PROFILE
  value: {{ .Values.config.platformProfile | quote }}
- name: PE_AGENT_DECISION_PROFILE
  value: {{ .Values.config.decisionProfile | quote }}
- name: PE_AGENT_ARCHIVE_ENABLED
  value: {{ .Values.config.archiveEnabled | quote }}
- name: PE_AGENT_PLATFORM_BASE_URL
  value: {{ .Values.config.platformBaseUrl | quote }}
- name: PE_AGENT_TYPESAFE_BASE_URL
  value: {{ .Values.config.typesafeBaseUrl | quote }}
- name: PE_AGENT_MOCK_SCENARIO_PATH
  value: {{ .Values.config.mockScenarioPath | quote }}
- name: PE_AGENT_DATABASE_URL
  valueFrom:
    secretKeyRef:
      name: {{ required "externalDatabase.secretName is required" .Values.externalDatabase.secretName }}
      key: {{ required "externalDatabase.urlKey is required" .Values.externalDatabase.urlKey }}
{{- end -}}
