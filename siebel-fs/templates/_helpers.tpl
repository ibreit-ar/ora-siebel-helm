{{/*
Return the Siebel Cloud manager Image
*/}}
{{- define "scm.image" -}}
{{- $registryName := .Values.image.registry -}}
{{- $repositoryName := .Values.image.repository -}}
{{- $tag := .Values.image.tag | toString -}}
{{- printf "%s/%s:%s" $registryName $repositoryName $tag -}}
{{- end -}}

{{- define "siebel.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "siebel.labels" -}}
helm.sh/chart: {{ include "siebel.chart" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
oracle.siebel.namespace-envid: {{ .Values.namespaceEnvid }}
{{- end }}


{{/*
Return the proper busybox image
*/}}
{{- define "busybox.image" -}}
{{- $values := .Values | default dict -}}
{{- $image := $values.image | default dict -}}
{{- $busybox := $image.busybox | default dict -}}

{{- $registry := $busybox.registry | default "" -}}
{{- $repository := $busybox.repository | default "busybox" -}}
{{- $tag := $busybox.tag | default "latest" | toString -}}

{{- if $registry -}}
{{- printf "%s/%s:%s" $registry $repository $tag -}}
{{- else -}}
{{- printf "%s:%s" $repository $tag -}}
{{- end -}}
{{- end -}}
