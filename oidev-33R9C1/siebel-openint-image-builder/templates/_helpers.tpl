{{/*
Return the proper custom image regex
*/}}
{{- define "tag.regex" -}}
{{- $appVersion := .Chart.AppVersion -}}
{{- printf "CM_%s.SIEBEL_OPENINT.*" $appVersion -}}
{{- end -}}

{{/*
Return the proper Apigen image
*/}}
{{- define "siebelOpenintImageBuilder.image" -}}
{{- $registryName := .Values.image.siebel_openint_image_builder.registry -}}
{{- $repositoryName := .Values.image.siebel_openint_image_builder.repository -}}
{{- $registryPrefix := .Values.image.siebel_openint_image_builder.registry_prefix -}}
{{- $tag := .Values.image.siebel_openint_image_builder.tag | toString -}}

{{- if $registryPrefix -}}
{{- printf "%s/%s/%s:%s" $registryName $registryPrefix $repositoryName $tag -}}
{{- else -}}
{{- printf "%s/%s:%s" $registryName $repositoryName $tag -}}

{{- end -}}
{{- end -}}


{{/*
Return the proper Docker Image Registry Secret Names
*/}}
{{- define "siebelOpenint.imagePullSecrets" -}}
{{- if .Values.imagePullSecrets -}}
imagePullSecrets:
{{- range .Values.imagePullSecrets }}
  - name: {{ . }}
{{- end -}}
{{- end -}}
{{- end -}}




