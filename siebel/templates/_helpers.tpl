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
Return the proper DB Utility image name
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
Return the proper utility image
*/}}
{{- define "util.image" -}}
{{- $registryName := .Values.image.util.registry -}}
{{- $repositoryName := .Values.image.util.repository -}}
{{- $tag := .Values.image.util.tag | toString -}}
{{- printf "%s/%s:%s" $registryName $repositoryName $tag -}}
{{- end -}}

{{/*
Return the siebel logging image in the format of " registryName repositoryName Tag "
*/}}
{{- define "loggingCollector.image" -}}
{{- $registryName := .Values.logging.image.registry -}}
{{- $repositoryName := .Values.logging.image.repository -}}
{{- $tag := .Values.logging.image.tag | toString -}}
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

{{/*  Return the log format1 volume */}}
{{- define "logging.logFormat1Volume" -}}
- name: log-collector-config-volume
  mountPath: /etc/fluent/applicationcontainer_logs_format1.conf
  subPath: applicationcontainer_logs_format1.conf
{{- end -}}

{{/* Return the log format2 volume */}}
{{- define "logging.logFormat2Volume" -}}
- name: log-collector-config-volume
  mountPath: /etc/fluent/applicationcontainer_logs_format2.conf
  subPath: applicationcontainer_logs_format2.conf
{{- end -}}

{{/* Return the log format3 volume */}}
{{- define "logging.logFormat3Volume" -}}
- name: log-collector-config-volume
  mountPath: /etc/fluent/applicationcontainer_logs_format3.conf
  subPath: applicationcontainer_logs_format3.conf
{{- end -}}

{{/* Return the log format4 volume */}}
{{- define "logging.logFormat4Volume" -}}
- name: log-collector-config-volume
  mountPath: /etc/fluent/applicationcontainer_logs_format4.conf
  subPath: applicationcontainer_logs_format4.conf
{{- end -}}

{{/* Return the log filter volume */}}
{{- define "logging.logFilterVolume" -}}
- name: log-collector-config-volume
  mountPath: /etc/fluent/applicationcontainer_logs_filter.conf
  subPath: applicationcontainer_logs_filter.conf
{{- end -}}

{{/* Return the CFG tools log format volume */}}
{{- define "logging.cfgToolsFormatVolume" -}}
- name: log-collector-config-volume
  mountPath: /etc/fluent/cfgtool_logs_format.conf
  subPath: cfgtool_logs_format.conf
{{- end -}}

{{/* Return the SES OM log format volume */}}
{{- define "logging.sesOMLogFormat" -}}
- name: log-collector-config-volume
  mountPath: /etc/fluent/ses_om_logs_format.conf
  subPath: ses_om_logs_format.conf
{{- end -}}


{{/* Return the Siebel Server Service Log format volume */}}
{{- define "logging.siebSrvrServiceLogs" -}}
- name: log-collector-config-volume
  mountPath: /etc/fluent/ses_siebsrvr_service_logs.conf
  subPath: ses_siebsrvr_service_logs.conf
{{- end -}}


{{/* Return the log forwarder volume */}}
{{- define "logging.logForwarderVolume" -}}
- name: log-collector-config-volume
  mountPath: /etc/fluent/scm_forwarder_match.conf
  subPath: scm_forwarder_match.conf
{{- end -}}

{{/* Return the SAI Fluent volume */}}
{{- define "logging.saiFluentdConfVolume" -}}
- name: log-collector-config-volume
  mountPath: /etc/fluent/fluent.conf
  subPath: scm_sai_fluent.conf
{{- end -}}

{{/* Return the om log filter volume */}}
{{- define "logging.omLogFilterVolume" -}}
- name: log-collector-config-volume
  mountPath: /etc/fluent/om_logs_filter.conf
  subPath: om_logs_filter.conf
{{- end -}}


{{/* Return the SES Fluent volume */}}
{{- define "logging.sesFluentdConfVolume" -}}
- name: log-collector-config-volume
  mountPath: /etc/fluent/fluent.conf
  subPath: scm_ses_fluent.conf
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

