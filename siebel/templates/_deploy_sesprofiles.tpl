{{- define "deploy.sesprofiles" -}}
{{- $root := first . -}}
{{- $siebservermap := first (rest .) -}}
{{- $profile := ( get $siebservermap "profile" ) -}}
{{- $replicas := ( get $siebservermap "replicas" ) -}}
{{- $sesResources := ( get $siebservermap "sesResources" ) -}}
{{- $affinity := ( get $siebservermap "affinity" ) -}}
{{- $envlist := ( get $siebservermap "envlist" ) -}}

#{{- println "%d" $replicas }}
{{- $siebserverPrefix := ( get $siebservermap "siebsrvr_prefix" ) | replace "-" "_" -}}
{{- if gt ($siebserverPrefix | len) 10 }}
## {{- println "    siebserverPrefix name length must not be greater than 10 , trimming to 10 " }}
{{- end }}
{{- $siebServer := $siebserverPrefix | trunc 10 | trimSuffix "-" }}
##{{- println "%s" $siebServer }}
{{- $autoscaling := ( get $siebservermap "autoscaling" ) -}}

#keyfilebin-check
{{- $keyfilepath := printf "%s/keyfile.bin" $root.Values.encryptionKey.path }}
{{- $keyfilepath := $root.Files.Glob $keyfilepath }}

#SES HPA definition yaml
---
{{- if $autoscaling }}
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: {{ $siebServer }}-hpa
  namespace: {{ $root.Release.Namespace }}
  labels:
    {{- include "siebel.labels" $root  | nindent 4 }}
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: StatefulSet
    name: {{ $siebServer }}
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


#SES kubernetes yaml
---
apiVersion: v1
kind: Service
metadata:
  name: {{ $siebServer }}
  namespace: {{ $root.Release.Namespace }}
  labels: {{- include "siebel.labels" $root  | nindent 4 }}
    app.kubernetes.io/component: {{ $siebServer }}
spec:
  ports:
  - name: tomcat-port
    port: 4430
    protocol: TCP
    targetPort: 4430
  - name: scb-port
    port: 2321
    protocol: TCP
    targetPort: 2321
  - name: syncmgr-port
    port: 40400
    protocol: TCP
    targetPort: 40400
  - name: srbroker-port
    port: 50000
    protocol: TCP
    targetPort: 50000
  - name: siebsess-port
    port: 50001
    protocol: TCP
    targetPort: 50001
  {{- if $root.Values.monitoring.enableMonitoring }}
  - name: jmx-metrics
    port: 8088
    protocol: TCP
    targetPort: 8088
  {{- end }}
  clusterIP: None
  selector: {{- include "siebel.selectorLabels" $root  | nindent 4 }}
    app.siebel.tier: {{ $siebServer }}
---
apiVersion: apps/v1 # for versions before 1.9.0 use apps/v1beta2
kind: StatefulSet
metadata:
  name: {{ $siebServer }}
  labels: {{- include "siebel.labels" $root  | nindent 4 }}
spec:
  selector:
    matchLabels: {{- include "siebel.selectorLabels" $root  | nindent 6 }}
      app.siebel.tier: {{ $siebServer }}
  serviceName: {{ $siebServer }}
  replicas: {{ $replicas }}
  updateStrategy:
    type: RollingUpdate
  template:
    metadata:
      labels: {{- include "siebel.labels" $root  | nindent 8 }}
        app.siebel.tier: {{ $siebServer }}
    spec:
      serviceAccountName: {{ $root.Values.ses.serviceAccountName | default "ses-sa" }}
      {{- if $affinity }}
      affinity: {{ $affinity | toYaml | nindent 8 }}
      {{- end }}
      containers:
        - image: {{ template "siebel.image" $root }}
          imagePullPolicy: {{ $root.Values.image.siebel.imagePullPolicy | default "Always" }}
          name: ses
          ports:
          - containerPort: 4430
            name: tomcat-port
          - containerPort: 2321
            name: scb-port
          - containerPort: 40400
            name: syncmgr-port
          - containerPort: 50000
            name: srbroker-port
          - containerPort: 50001
            name: siebsess-port
          {{- if $root.Values.monitoring.enableMonitoring }}
          - containerPort: 8088
            name: jmx-metrics
          {{- end }}
          volumeMounts:
          - name: migration-fs
            mountPath: /migration
            subPath: migration
          - name: persist-storage
            mountPath: /persistent
            subPath: {{ $root.Release.Namespace | upper }}/{{ $siebServer }}
        {{- range $index, $val := $root.Values.storage }}
          - name: sfs-storage-{{ $index }}
            mountPath: /sfs{{ $index }}
            subPath: {{ $root.Release.Namespace | upper }}/FS
        {{- end }}
          - name: tns-admin
            mountPath: /tnsadmin
          {{- if $keyfilepath }}
          - name: keyfile-bin
            mountPath: /siebel/mde/siebsrvr/admin/keyfile.bin
            subPath: keyfile.bin
          {{- end }}
          - name: gateway
            mountPath: /config/gateway.yaml
            subPath: gateway.yaml
          - name: comp-definitions
            mountPath: /config/comp_definitions.yaml
            subPath: comp_definitions.yaml
          - name: enterprise
            mountPath: /config/enterprise.yaml
            subPath: enterprise.yaml
          - mountPath: /config/server_{{ $siebServer }}.yaml
            name: server-{{ $siebServer }}
            subPath: server_{{ $siebServer }}.yaml
          - name: keystore
            mountPath: /siebel/mde/applicationcontainer_internal/siebelcerts/keystore.jks
            subPath: keystore.jks
          - name: keystore
            mountPath: /siebel/mde/applicationcontainer_internal/siebelcerts/keystore_client.jks
            subPath: keystore_client.jks
          - name: keystore
            mountPath: /siebel/mde/applicationcontainer_internal/siebelcerts/truststore.jks
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
          {{- if $root.Values.ldap.enable_ssl }}
          - name: ldap-wallet
            mountPath: /siebel/mde/applicationcontainer_internal/siebelcerts/ewallet.p12
            subPath: ewallet.p12
          {{- end }}
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
            (dict "name" "TNS_ADMIN" "value" "/tnsadmin")
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
            value: "SES"
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
            value: /persistent/$(pod_name)/ses_$(pod_name).log
          startupProbe: {{ $root.Values.sesTomcatStartupProbe | toYaml | nindent 12 }}
          {{- if $sesResources }}
          resources: {{ $sesResources | toYaml | nindent 12 }}
          {{- else }}
          resources: {{ $root.Values.sesResources | toYaml | nindent 12 }}
          {{- end }}
       {{ if $root.Values.logging.enableLogging }}
        - image: {{ template "loggingCollector.image" $root }}
          name: log-collector
          imagePullPolicy: {{ $root.Values.logging.image.imagePullPolicy | default "Always" }}
          securityContext:
            runAsGroup: 0
            runAsUser: {{ $root.Values.logging.securityContext.runAsUser }}
          terminationMessagePolicy: FallbackToLogsOnError
          env:
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
          resources: {{ $root.Values.logging.logCollectorResources | toYaml | nindent 12 }}
          volumeMounts:
          {{- include "logging.sesFluentdConfVolume" $root | nindent 10 }}
          {{- include "logging.logFormat1Volume" $root | nindent 10 }}
          {{- include "logging.logFormat2Volume" $root | nindent 10 }}
          {{- include "logging.logFormat3Volume" $root | nindent 10 }}
          {{- include "logging.logFormat4Volume" $root | nindent 10 }}
          {{- include "logging.cfgToolsFormatVolume" $root | nindent 10 }}
          {{- include "logging.sesOMLogFormat" $root | nindent 10 }}
          {{- include "logging.siebSrvrServiceLogs" $root | nindent 10 }}
          {{- include "logging.logFilterVolume" $root | nindent 10 }}
          {{- include "logging.logForwarderVolume" $root | nindent 10 }}
          {{- include "logging.omLogFilterVolume" $root | nindent 10 }}
          - name: persist-storage
            mountPath: /persistent
            subPath: {{ $root.Release.Namespace | upper }}/{{ $siebServer }}
      {{ end }}
      initContainers:
        - name: persist-fix
          imagePullPolicy: {{ $root.Values.image.busybox.imagePullPolicy | default "Always" }}
          image: {{ template "busybox.image" $root }}
          command:
            - sh
            - -c
            - mkdir -p /work-dir/{{ $root.Release.Namespace | upper }}/{{ $siebServer }};
          volumeMounts:
          - name: persist-storage
            mountPath: "/work-dir"
        {{- if $root.Values.ses.wait4dbconn }}
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
        {{- if $root.Values.ses.wait4cgw }}
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
        - name: migration-fs
          persistentVolumeClaim:
            claimName: migration-fs
            readOnly: false
{{- range $index, $val := $root.Values.storage }}
        - name: sfs-storage-{{ $index }}
          persistentVolumeClaim:
            claimName: fsspvc-sfs-{{ $index }}
            readOnly: false
{{- end }}
        - name: persist-storage
          persistentVolumeClaim:
            claimName: fsspvc-persist
            readOnly: false
        {{- if $keyfilepath }}
        - name: keyfile-bin
          secret:
            defaultMode: 420
            secretName: keyfile-secret
        {{- end }}
        - name: tns-admin
          secret:
            defaultMode: 420
            secretName: tns-secret
        - name: gateway
          configMap:
            name: gateway
        - name: comp-definitions
          configMap:
            name: comp-definitions
        - name: enterprise
          configMap:
            name: enterprise
        - name: server-{{ $siebServer }}
          configMap:
            name: server-{{ $siebServer }}
        - name: keystore
          secret:
            defaultMode: 420
            secretName: keystore
        {{- if $root.Values.ldap.enable_ssl }}
        - name: ldap-wallet
          secret:
            defaultMode: 420
            secretName: ldap-wallet
        {{- end }}
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
  name: {{ $siebServer }}-{{ $i }}
  namespace: {{ $root.Release.Namespace }}
  labels: {{- include "siebel.labels" $root  | nindent 4 }}
    app.kubernetes.io/component: {{ $siebServer }}-{{ $i }}
spec:
  ports:
  - name: tomcat-port
    port: 4430
    protocol: TCP
    targetPort: 4430
  - name: scb-port
    port: 2321
    protocol: TCP
    targetPort: 2321
  - name: syncmgr-port
    port: 40400
    protocol: TCP
    targetPort: 40400
  - name: srbroker-port
    port: 50000
    protocol: TCP
    targetPort: 50000
  - name: siebsess-port
    port: 50001
    protocol: TCP
    targetPort: 50001
  {{- $portrange := untilStep 49150 49253 1 -}}
  {{- range $index, $value := $portrange }}
  - name: dynamic-{{ $index }}
    port: {{ $value }}
    targetPort: {{ $value }}
  {{- end }}  
  {{- if $root.Values.monitoring.enableMonitoring }}
  - name: jmx-metrics
    port: 8088
    protocol: TCP
    targetPort: 8088
  {{- end }}
  selector:
    statefulset.kubernetes.io/pod-name: {{ $siebServer }}-{{ $i }}
{{- end }}
{{ end -}}
