{{/*
Expand the name of the chart.
*/}}
{{- define "siebel.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}
{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "siebel.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}
{{/*
Common labels
*/}}
{{- define "siebel.labels" -}}
helm.sh/chart: {{ include "siebel.chart" . }}
{{ include "siebel.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
oracle.siebel.namespace-envid: {{ .Values.namespaceEnvid }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "siebel.selectorLabels" -}}
app.kubernetes.io/name: {{ include "siebel.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Return the proper CGW image
*/}}
{{- define "siebel.image" -}}
{{- $registryName := .Values.image.siebel.registry -}}
{{- $repositoryName := .Values.image.siebel.repository -}}
{{- printf "%s/%s" $registryName $repositoryName -}}
{{- end -}}

{{/*
Return the Custom Image Build Image
*/}}
{{- define "siebel.customImageBuilderImage" -}}
{{- $registryName := .Values.image.customImageBuilder.registry -}}
{{- $repositoryName := .Values.image.customImageBuilder.repository -}}
{{- $tag := .Values.image.customImageBuilder.tag | toString -}}
{{- printf "%s/%s:%s" $registryName $repositoryName $tag -}}
{{- end -}}

{{/*
Return the Busy Box Image tag
*/}}
{{- define "siebel.busyboxImage" -}}
{{- $registryName := .Values.image.busybox.registry -}}
{{- $repositoryName := .Values.image.busybox.repository -}}
{{- $tag := .Values.image.busybox.tag | toString -}}
{{- printf "%s/%s:%s" $registryName $repositoryName $tag -}}
{{- end -}}


{{/*
Return the proper custom image regex
*/}}
{{- define "tag.regex" -}}
{{- $appVersion := .Chart.AppVersion -}}
{{- $repositoryName := .Values.image.siebel.repository -}}
{{- printf "^%s.CUSTOM.(?P<num>.*)" $appVersion -}}
{{- end -}}



