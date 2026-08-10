'use strict';

const { diag, DiagConsoleLogger, DiagLogLevel } = require('@opentelemetry/api');
diag.setLogger(new DiagConsoleLogger(), DiagLogLevel.DEBUG);

const { NodeSDK } = require('@opentelemetry/sdk-node');
const { getNodeAutoInstrumentations } = require('@opentelemetry/auto-instrumentations-node');
const { resourceFromAttributes } = require('@opentelemetry/resources');
const { SemanticResourceAttributes } = require('@opentelemetry/semantic-conventions');
const { OTLPTraceExporter } = require('@opentelemetry/exporter-trace-otlp-http');

const {
    AlwaysOffSampler,
    TraceIdRatioBasedSampler,
    ParentBasedSampler
} = require('@opentelemetry/sdk-trace-base');

const sampling = process.env.OTEL_SAMPLING_RATIO || "off";

let sampler;
if (sampling === "off") {
    sampler = new AlwaysOffSampler();
} else {
    sampler = new TraceIdRatioBasedSampler(parseFloat(sampling));
}

const serviceName = process.env.OTEL_SERVICE_NAME || 'unknown-service';

const exporterUrl = process.env.OTEL_EXPORTER_OTLP_ENDPOINT
    ? `${process.env.OTEL_EXPORTER_OTLP_ENDPOINT}/v1/traces`
    : 'http://jaeger:4318/v1/traces';

const sdk = new NodeSDK({
    resource: resourceFromAttributes({
        [SemanticResourceAttributes.SERVICE_NAME]: serviceName,
        [SemanticResourceAttributes.DEPLOYMENT_ENVIRONMENT]: process.env.NODE_ENV || 'development',
    }),

    traceExporter: new OTLPTraceExporter({
        url: exporterUrl,
        timeoutMillis: 30000,
    }),

    sampler: new ParentBasedSampler({
        root: sampler,
    }),

    instrumentations: [
        getNodeAutoInstrumentations({
            '@opentelemetry/instrumentation-mongodb': {
                enhancedDatabaseReporting: false,
            },
            '@opentelemetry/instrumentation-mongoose': {
                dbStatementSerializer: () => undefined,
            },
        })
    ],
});

sdk.start();

console.log(`✅ OpenTelemetry initialized (${serviceName}) — sampling=${sampling}, exporting to ${exporterUrl}`);

process.on('SIGTERM', async () => {
    await sdk.shutdown();
    console.log('🛑 OpenTelemetry shutdown complete');
    process.exit(0);
});