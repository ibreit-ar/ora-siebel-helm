{{/*
Return the proper Apigen image
*/}}
{{- define "siebelOpenint.image" -}}
{{- $registryName := .Values.image.siebel_open_integration.registry -}}
{{- $repositoryName := .Values.image.siebel_open_integration.repository -}}
{{- $tag := .Values.image.siebel_open_integration.tag | toString -}}
{{- printf "%s/%s:%s" $registryName $repositoryName $tag -}}
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



