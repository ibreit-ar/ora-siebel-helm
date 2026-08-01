{{/*
Expand the name of the chart.
*/}}
{{- define "siebel.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "siebel.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
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
Create the name of the service account to use
*/}}
{{- define "siebel.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "siebel.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Return the storage class value, comment values for on-prem in values.yaml
*/}}
{{- define "siebel-sfs.storage" -}}
{{- if .storageClassName -}}
storageClassName: {{ .storageClassName -}}
{{- end -}}
{{- end -}}

{{/*
Return the proper CGW image
*/}}
{{- define "siebel.image" -}}
{{- $registryName := .Values.image.siebel.registry -}}
{{- $repositoryName := .Values.image.siebel.repository -}}
{{- $tag := .Values.image.siebel.tag | toString -}}
{{- printf "%s/%s:%s" $registryName $repositoryName $tag -}}
{{- end -}}


{{/*
Return the proper Initialization image name
*/}}
{{- define "dbutils.image" -}}
{{- $registryName := .Values.image.dbutils.registry -}}
{{- $repositoryName := .Values.image.dbutils.repository -}}
{{- $tag := .Values.image.dbutils.tag | toString -}}
{{- printf "%s/%s:%s" $registryName $repositoryName $tag -}}
{{- end -}}

{{/*
Return the proper configure job image
*/}}
{{- define "configure.image" -}}
{{- $registryName := .Values.image.configure.registry -}}
{{- $repositoryName := .Values.image.configure.repository -}}
{{- $tag := .Values.image.configure.tag | toString -}}
{{- printf "%s/%s:%s" $registryName $repositoryName $tag -}}
{{- end -}}

{{/*
Return the proper arranger job image
*/}}
{{- define "arranger.image" -}}
{{- $registryName := .Values.image.arranger.registry -}}
{{- $repositoryName := .Values.image.arranger.repository -}}
{{- $tag := .Values.image.arranger.tag | toString -}}
{{- printf "%s/%s:%s" $registryName $repositoryName $tag -}}
{{- end -}}

{{/*
Return the proper busybox image
*/}}
{{- define "busybox.image" -}}
{{- $registryName := .Values.image.busybox.registry -}}
{{- $repositoryName := .Values.image.busybox.repository -}}
{{- $tag := .Values.image.busybox.tag | toString -}}
{{- printf "%s/%s:%s" $registryName $repositoryName $tag -}}
{{- end -}}

{{/*
Return the proper Docker Image Registry Secret Names
*/}}
{{- define "siebel.imagePullSecrets" -}}
{{- if .Values.imagePullSecrets -}}
imagePullSecrets:
{{- range .Values.imagePullSecrets }}
  - name: {{ . }}
{{- end -}}
{{- end -}}
{{- end -}}


{{/*
Return the proper Initialization image name
*/}}
{{- define "utils.image" -}}
{{- $registryName := .Values.image.utils.registry -}}
{{- $repositoryName := .Values.image.utils.repository -}}
{{- $tag := .Values.image.utils.tag | toString -}}
{{- printf "%s/%s:%s" $registryName $repositoryName $tag -}}
{{- end -}}