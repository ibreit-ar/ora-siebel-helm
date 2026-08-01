{{- define "deploy.saiprofiles" -}}
{{- $root := first . -}}
{{- $saiservermap := first (rest .) -}}
{{- $profile := ( get $saiservermap "profile" ) -}}
{{- $replicas := ( get $saiservermap "replicas" ) -}}
{{- $affinity := ( get $saiservermap "affinity" ) -}}
{{- $envlist := ( get $saiservermap "envlist" ) -}}
#{{- println "%d" $replicas }}
{{- $saiserverPrefix := ( get $saiservermap "sai_prefix" ) | replace "-" "_" -}}
{{- if gt ($saiserverPrefix | len) 10 }}
## {{- println "   saiserverPrefix name length must not be greater than 10 , trimming to 10 " }}
{{- end }}
{{- $saiServer := $saiserverPrefix | trunc 10 | trimSuffix "-" }}
##{{- println "%s" $saiServer }}
{{- $autoscaling := ( get $saiservermap "autoscaling" ) -}}

#SAI HPA definition yaml
---
{{- if $autoscaling }}
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: {{ $saiServer }}-hpa
  namespace: {{ $root.Release.Namespace }}
  labels:
    {{- include "siebel.labels" $root  | nindent 4 }}
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: StatefulSet
    name: {{ $saiServer }}
{{- if hasKey $autoscaling "behavior" }}
{{ $behavior := ( get $autoscaling "behavior" ) }}
{{- if hasKey $behavior "scaleDown" }}
{{- $scaledown := ( get $behavior "scaleDown" ) -}}
{{- if hasKey $scaledown "policies" }}
{{- $_ := unset $scaledown "policies" -}}
{{- end }}
{{- if hasKey $scaledown "selectPolicy" }}
{{- $_ := set $scaledown "selectPolicy" "Disabled" -}}
{{- end }}
{{- else }}
{{- $scaledown := dict "selectPolicy" "Disabled" -}}
{{- $_ := set $behavior "scaleDown" $scaledown -}}
{{- end }}
{{- $autoscaling | toYaml | indent 2 }}
{{- else }}
{{ $autoscaling | toYaml | indent 2 }}
  behavior:
    scaleDown:
      selectPolicy: Disabled
{{- end }}
{{- end }}


#SAI kubernetes yaml
---
apiVersion: v1
kind: Service
metadata:
  name: {{ $saiServer }}
  namespace: {{ $root.Release.Namespace }}
  labels: {{- include "siebel.labels" $root  | nindent 4 }}
    app.kubernetes.io/component: {{ $saiServer }}
spec:
  ports:
  - name: tomcat-port
    port: 4430
    protocol: TCP
    targetPort: 4430
  {{- if $root.Values.monitoring.enableMonitoring }}
  - name: jmx-metrics
    port: 8088
    protocol: TCP
    targetPort: 8088
  {{- end }}
  clusterIP: None
  selector: {{- include "siebel.selectorLabels" $root  | nindent 4 }}
    app.siebel.tier: {{ $saiServer }}
---
apiVersion: apps/v1 # for versions before 1.9.0 use apps/v1beta2
kind: StatefulSet
metadata:
  name: {{ $saiServer }}
  labels: {{- include "siebel.labels" $root  | nindent 4 }}
spec:
  selector:
    matchLabels: {{- include "siebel.selectorLabels" $root  | nindent 6 }}
      app.siebel.tier: {{ $saiServer }}
  serviceName: {{ $saiServer }}
  replicas: {{ $replicas }}
  updateStrategy:
    type: RollingUpdate
  template:
    metadata:
      labels: {{- include "siebel.labels" $root  | nindent 8 }}
        app.siebel.tier: {{ $saiServer }}
    spec:
      serviceAccountName: {{ $root.Values.sai.serviceAccountName | default "sai-sa" }}
      {{- if $affinity }}
      affinity: {{ $affinity | toYaml | nindent 8 }}
      {{- end }}
      containers:
        - image: {{ template "siebel.image" $root }}
          imagePullPolicy: {{ $root.Values.image.siebel.imagePullPolicy | default "Always" }}
          name: sai
          ports:
          - containerPort: 4430
            name: tomcat-port
          {{- if $root.Values.monitoring.enableMonitoring }}
          - containerPort: 8088
            name: jmx-metrics
          {{- end }}
          volumeMounts:
          - name: persist-storage
            mountPath: /persistent
            subPath: {{ $root.Release.Namespace | upper }}/{{ $saiServer }}
{{- range $index, $val := $root.Values.storage }}
          - name: sfs-storage-{{ $index }}
            mountPath: /sfs{{ $index }}
            subPath: {{ $root.Release.Namespace | upper }}/FS
{{- end }}
          - name: migration-fs
            mountPath: /migration
            subPath: migration
          - name: gateway
            mountPath: /config/gateway.yaml
            subPath: gateway.yaml
          - name: enterprise
            mountPath: /config/enterprise.yaml
            subPath: enterprise.yaml
          - name: migration
            mountPath: /config/migration.yaml
            subPath: migration.yaml
          - mountPath: /config/sai_{{ $saiServer }}.yaml
            name: sai-{{ $saiServer }}
            subPath: sai_{{ $saiServer }}.yaml
          - name: keystore
            mountPath: /siebel/mde/applicationcontainer_external/siebelcerts/keystore.jks
            subPath: keystore.jks
          - name: keystore
            mountPath: /siebel/mde/applicationcontainer_external/siebelcerts/keystore_client.jks
            subPath: keystore_client.jks
          - name: keystore
            mountPath: /siebel/mde/applicationcontainer_external/siebelcerts/truststore.jks
            subPath: truststore.jks
          - name: keystore
            mountPath: /siebel/mde/tls_certs/ca.cert.pem
            subPath: ca.cert.pem
          - name: keystore
            mountPath: /siebel/mde/tls_certs/server_key.pem
            subPath: server_key.pem
          - name: keystore
            mountPath: /siebel/mde/tls_certs/server.pem
            subPath: server.pem
          {{- if $root.Values.monitoring.enableMonitoring }}
          - name: prometheus-jmx-config
            mountPath: /config/prometheus-jmx-config.yaml
            subPath: prometheus-jmx-config.yaml
          {{- end }}
          - mountPath: /var/run/secrets/kubernetes.io/serviceaccount
            name: kube-api-access
            readOnly: true
          env:
          {{- $defaults := list
            (dict "name" "SBL_HEAP_OPTS" "value" "-Xms500m -Xmx4G")
            (dict "name" "CATALINA_OPTS" "value" "-Djavax.net.ssl.keyStoreAlias=siebel")
            (dict "name" "Language" "value" "enu")
            (dict "name" "LogLevel" "value" "INFO")
          }}
          {{- $mergedEnv := list }}
          {{- $usedNames := dict }}
          {{- if $envlist }}
              {{- range $env := $envlist }}
                {{- $mergedEnv = append $mergedEnv $env }}
                {{- $_ := set $usedNames $env.name true }}
              {{- end }}
          {{- end }}
          {{- range $env := $defaults }}
            {{- if not (hasKey $usedNames $env.name) }}
              {{- $mergedEnv = append $mergedEnv $env }}
            {{- end }}
          {{- end }}
          {{- if $root.Values.monitoring.enableMonitoring }}
          - name: JMX_OPTS
            value: "-javaagent:/config/jmx_prometheus_javaagent-1.3.0.jar=8088:/config/prometheus-jmx-config.yaml"
          {{- end }}
          {{- if $mergedEnv }}
          {{ $mergedEnv | toYaml | nindent 10 }}
          {{- end }}
          - name: containerMode
            value: "SAI"
          - name: PROFILE
            value: {{ $profile | quote }}
          - name: ServerPort
            value: "4430"
          - name: SaiHost
            value: smc-0.smc.{{ $root.Release.Namespace }}.svc.cluster.local
          - name: SaiPort
            value: "4430"
          - name: autodeploy
            value: "true"
          - name: pod_name
            valueFrom:
              fieldRef:
                fieldPath: metadata.name
          - name: LogLocation
            value: /persistent/$(pod_name)/sai_$(pod_name).log
          livenessProbe: {{ $root.Values.saiLivenessProbe | toYaml | nindent 12 }}
          readinessProbe: {{ $root.Values.saiReadinessProbe | toYaml | nindent 12 }}
          resources: {{ $root.Values.saiResources | toYaml | nindent 12 }}
        {{ if $root.Values.logging.enableLogging }}
        - image: {{ template "loggingCollector.image" $root }}
          name: log-collector
          imagePullPolicy: {{ $root.Values.logging.image.imagePullPolicy | default "Always" }}
          securityContext:
            runAsGroup: 0
            runAsUser: {{ $root.Values.logging.securityContext.runAsUser }}
          terminationMessagePolicy: FallbackToLogsOnError
          env:
          - name: CONTAINER_TYPE
            value: "sai"
          - name: POD_NAME
            valueFrom:
              fieldRef:
                fieldPath: metadata.name
          - name: NODE_NAME
            valueFrom:
               fieldRef:
                 fieldPath: spec.nodeName
          - name: POD_NAMESPACE
            valueFrom:
              fieldRef:
                fieldPath: metadata.namespace
          - name: POD_IP
            valueFrom:
              fieldRef:
                fieldPath: status.podIP
          - name: POD_SERVICE_ACCOUNT
            valueFrom:
              fieldRef:
                fieldPath: spec.serviceAccountName
          - name: FLUENTD_ARGS
            value: "-c /etc/fluent/fluent.conf"
          - name:  FLUENT_FORWARD_HOST
            value: {{ $root.Values.logging.aggregatorInfo.svcName }}.{{ $root.Release.Namespace }}.svc.cluster.local
          - name:  FLUENT_FORWARD_PORT
            value: "{{ $root.Values.logging.aggregatorInfo.portNo }}"
          volumeMounts:
          {{- include "logging.logFormat1Volume" $root | nindent 10 }}
          {{- include "logging.logFormat2Volume" $root | nindent 10  }}
          {{- include "logging.logFormat3Volume" $root | nindent 10  }}
          {{- include "logging.logFormat4Volume" $root | nindent 10  }}
          {{- include "logging.logFilterVolume" $root | nindent 10  }}
          {{- include "logging.logForwarderVolume" $root | nindent 10  }}
          {{- include "logging.saiFluentdConfVolume" $root | nindent 10  }}
          - name: persist-storage
            mountPath: /persistent
            subPath: {{ $root.Release.Namespace | upper }}/{{ $saiServer }}
          resources: {{ $root.Values.logging.logCollectorResources | toYaml | nindent 12 }}
        {{ end }}
      initContainers:
        - name: persist-folders
          imagePullPolicy: {{ $root.Values.image.busybox.imagePullPolicy | default "Always" }}
          image: {{ template "busybox.image" $root }}
          command:
            - sh
            - -c
            - mkdir -p /work-dir/{{ $root.Release.Namespace | upper }}/{{ $saiServer }};
          volumeMounts:
          - name: persist-storage
            mountPath: "/work-dir"
        {{- if $root.Values.enableFixMount }}
        - name: fix-migration-mount
          imagePullPolicy: {{ $root.Values.image.busybox.imagePullPolicy | default "Always" }}
          image: {{ template "busybox.image" $root }}
          command:
            - sh
            - -c
            - |
              set -e
              mkdir -p /work-dir/migration
          volumeMounts:
          - name: migration-fs
            mountPath: "/work-dir"
        {{- end }}
        {{- if $root.Values.sai.wait4dbconn }}
        - name: wait4dbconn
          imagePullPolicy: {{ $root.Values.image.dbutils.imagePullPolicy | default "Always" }}
          image: {{ template "dbutils.image" $root }}
          env:
            - name: TNS_ADMIN
              value: "/tnsadmin"
            - name: dbUser
              valueFrom:
                configMapKeyRef:
                  name: siebel-common-config
                  key: DBUSER
            - name: dbPassword
              valueFrom:
                secretKeyRef:
                  name: siebel-secrets
                  key: DBUSERPASSWORD
            - name: tnsConnectString
              valueFrom:
                configMapKeyRef:
                  name: siebel-common-config
                  key: DBTNSALIAS
          volumeMounts:
            - name: tns-admin
              mountPath: /tnsadmin
        {{- end }}
        {{- if $root.Values.sai.wait4cgw }}
        - name: configcheck-cgw
          image: {{ template "utils.image" $root }}
          imagePullPolicy: {{ $root.Values.image.utils.imagePullPolicy | default "Always" }}
          volumeMounts:
          - name: keystore
            mountPath: /tmp/keystore_client.jks
            subPath: keystore_client.jks
          command: ["/bin/sh"]
          args:
            - -c
            - >
              PASSWORD=siebel;
              JRE_HOME=$(readlink -f /usr/bin/java | sed "s:bin/java::");
              ${JRE_HOME}/bin/keytool -importkeystore -srckeystore /tmp/keystore_client.jks  -destkeystore /tmp/siebelclientkeystore.p12 -srcstoretype JKS -deststoretype PKCS12 -deststorepass ${PASSWORD} -new ${PASSWORD} -srcstorepass ${PASSWORD};
              echo \"Running Curl\";
              i=0;
              end={{ $root.Values.cgw.replicas | int }};
               while [ "$i" -lt "$end" ]; do
                depstatusCode=0;
                while [[ $depstatusCode -ne 200 && $depstatusCode -ne 401 ]]; do
                  depstatusCode=$(curl -ks -o /dev/null -w '%{http_code}'  --cert-type P12 --cert /tmp/siebelclientkeystore.p12:$PASSWORD https://siebelcgw-$i.siebel-cgw.{{ $root.Release.Namespace }}.svc.cluster.local:4430/siebel/v1.0/cloudgateway/heartbeat);
                  echo \"depstatusCode = \" $depstatusCode;
                  sleep 10;
                done
                i=$((i + 1))
              done
        {{- end }}
      {{- include "siebel.imagePullSecrets" $root | nindent 6 }}
      volumes:
{{- range $index, $val := $root.Values.storage }}
        - name: sfs-storage-{{ $index }}
          persistentVolumeClaim:
            claimName: fsspvc-sfs-{{ $index }}
            readOnly: false
{{- end }}
        - name: migration-fs
          persistentVolumeClaim:
            claimName: migration-fs
            readOnly: false
        - name: persist-storage
          persistentVolumeClaim:
            claimName: fsspvc-persist
            readOnly: false
        - name: gateway
          configMap:
            name: gateway
        - name: enterprise
          configMap:
            name: enterprise
        - name: migration
          configMap:
            name: migration
        - name: sai-{{ $saiServer }}
          configMap:
            name: sai-{{ $saiServer }}
        - name: keystore
          secret:
            defaultMode: 420
            secretName: keystore
        {{ if $root.Values.logging.enableLogging }}
        - name: log-collector-config-volume
          configMap:
            name: log-collector-config
        {{ end }}
        {{- if $root.Values.monitoring.enableMonitoring }}
        - name: prometheus-jmx-config
          configMap:
            name: prometheus-jmx-config
        {{- end }}
        - name: tns-admin
          secret:
            defaultMode: 420
            secretName: tns-secret
        - name: kube-api-access
          projected:
            defaultMode: 420
            sources:
              - serviceAccountToken:
                  expirationSeconds: 3607
                  path: token
              - configMap:
                  items:
                    - key: ca.crt
                      path: ca.crt
                  name: kube-root-ca.crt
              - downwardAPI:
                  items:
                    - fieldRef:
                        apiVersion: v1
                        fieldPath: metadata.namespace
                      path: namespace
      securityContext:
        runAsUser: {{ $root.Values.securityContext.runAsUser }}
        runAsGroup: 0
        fsGroup: {{ $root.Values.securityContext.fsGroup }}

# Service for each replicas of statefulset
{{- $replicaCount := ($replicas | int) -}}
{{- range $i, $e := until $replicaCount }}
---
apiVersion: v1
kind: Service
metadata:
  name: {{ $saiServer }}-{{ $i }}
  namespace: {{ $root.Release.Namespace }}
  labels: {{- include "siebel.labels" $root  | nindent 4 }}
    app.kubernetes.io/component: {{ $saiServer }}-{{ $i }}
spec:
  ports:
  - name: tomcat-port
    port: 4430
    protocol: TCP
    targetPort: 4430
  {{- if $root.Values.monitoring.enableMonitoring }}
  - name: jmx-metrics
    port: 8088
    protocol: TCP
    targetPort: 8088
  {{ end }}
  selector:
    statefulset.kubernetes.io/pod-name: {{ $saiServer }}-{{ $i }}
{{- end }}
{{ end -}}
