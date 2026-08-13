

{{/*
Return the proper Apigen image
*/}}
{{- define "coherenceServer.image" -}}
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







