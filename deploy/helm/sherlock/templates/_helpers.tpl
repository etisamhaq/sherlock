{{- define "sherlock.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "sherlock.fullname" -}}
{{- printf "%s-%s" .Release.Name (include "sherlock.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "sherlock.labels" -}}
app.kubernetes.io/name: {{ include "sherlock.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version }}
{{- end -}}

{{- define "sherlock.selectorLabels" -}}
app.kubernetes.io/name: {{ include "sherlock.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "sherlock.serviceAccountName" -}}
{{- if .Values.serviceAccount.create -}}
{{- default (include "sherlock.fullname" .) .Values.serviceAccount.name -}}
{{- else -}}
{{- default "default" .Values.serviceAccount.name -}}
{{- end -}}
{{- end -}}
