{{/* Copyright 2020, Oracle Corporation and/or its affiliates           */}}
{{/* Licensed under the Universal Permissive License v 1.0 as shown at  */}}
{{/* http://oss.oracle.com/licenses/upl.                                */}}

{{/* vim: set filetype=mustache: */}}
{{/*
Expand the name of the chart.
*/}}


{{/*
Return the proper Apigen image
*/}}
{{- define "coherenceOperator.image" -}}
{{- $registryName := .Values.image.registry -}}
{{- $repositoryName := .Values.image.repository -}}
{{- $registryPrefix := .Values.image.registry_prefix -}}
{{- $tag := .Values.image.tag | toString -}}

{{- if $registryPrefix -}}
{{- printf "%s/%s/%s:%s" $registryName $registryPrefix $repositoryName $tag -}}
{{- else -}}
{{- printf "%s/%s:%s" $registryName $repositoryName $tag -}}

{{- end -}}
{{- end -}}

{{- define "coherence-operator.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "coherenceOperator.imagePullSecrets" -}}
{{- if .Values.imagePullSecrets -}}
imagePullSecrets:
{{- range .Values.imagePullSecrets }}
  - name: {{ . }}
{{- end -}}
{{- end -}}
{{- end -}}


{{/*
Return the proper Apigen image
*/}}
{{- define "defaultCoherenceServer.image" -}}
{{- $registryName := .Values.defaultCoherenceImage.registry -}}
{{- $repositoryName := .Values.defaultCoherenceImage.repository -}}
{{- $registryPrefix := .Values.defaultCoherenceImage.registry_prefix -}}
{{- $tag := .Values.defaultCoherenceImage.tag | toString -}}

{{- if $registryPrefix -}}
{{- printf "%s/%s/%s:%s" $registryName $registryPrefix $repositoryName $tag -}}
{{- else -}}
{{- printf "%s/%s:%s" $registryName $repositoryName $tag -}}

{{- end -}}
{{- end -}}



{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "coherence-operator.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "coherence-operator.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Create the release labels.
These are a common set of labels applied to all of the resources
generated from this chart.
*/}}
{{- define "coherence-operator.release_labels" }}
heritage: {{ .Release.Service | quote }}
release: {{ .Release.Name | quote }}
chart: {{ template "coherence-operator.chart" . }}
app: {{ template "coherence-operator.name" . }}
component: coherence-operator
{{- end }}
