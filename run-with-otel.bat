@echo off

set OTEL_SERVICE_NAME=spring-petclinic
set OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318

@REM set OTEL_TRACES_SAMPLER=traceidratio
@REM set OTEL_TRACES_SAMPLER_ARG=1.0

set OTEL_TRACES_SAMPLER=traceidratio
set OTEL_TRACES_SAMPLER_ARG=0.1    

@REM set OTEL_TRACES_SAMPLER=traceidratio
@REM set OTEL_TRACES_SAMPLER_ARG=0.01   

@REM set OTEL_TRACES_SAMPLER=always_off

set JAVA_TOOL_OPTIONS=-javaagent:otel\opentelemetry-javaagent.jar

mvn spring-boot:run

@REM @echo off

@REM REM ===========================================
@REM REM OpenTelemetry Configuration
@REM REM ===========================================

@REM set OTEL_SERVICE_NAME=spring-petclinic
@REM set OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318

@REM REM ---------- Sampling ----------

@REM set OTEL_TRACES_SAMPLER=traceidratio
@REM set OTEL_TRACES_SAMPLER_ARG=1.0

@REM @REM set OTEL_TRACES_SAMPLER=traceidratio
@REM @REM set OTEL_TRACES_SAMPLER_ARG=0.1

@REM @REM set OTEL_TRACES_SAMPLER=traceidratio
@REM @REM set OTEL_TRACES_SAMPLER_ARG=0.01

@REM @REM set OTEL_TRACES_SAMPLER=always_off

@REM REM ---------- Disable OTLP Metrics & Logs ----------

@REM set OTEL_METRICS_EXPORTER=none
@REM set OTEL_LOGS_EXPORTER=none

@REM REM ---------- Java Agent + JVM Memory ----------

@REM set JAVA_TOOL_OPTIONS=-javaagent:otel\opentelemetry-javaagent.jar -Xms2g -Xmx4g

@REM mvn spring-boot:run