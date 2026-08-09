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

// ------------------------------------------------------
// Sampling Configuration
// ------------------------------------------------------

const sampling = "off"; // "off", "0.01", "0.1", "1.0"

let sampler;

if (sampling === "off") {
    sampler = new AlwaysOffSampler();
} else {
    sampler = new TraceIdRatioBasedSampler(parseFloat(sampling));
}

const sdk = new NodeSDK({

    resource: resourceFromAttributes({
        [SemanticResourceAttributes.SERVICE_NAME]: 'grocery-monolith',
        [SemanticResourceAttributes.DEPLOYMENT_ENVIRONMENT]: 'development',
    }),

    traceExporter: new OTLPTraceExporter({
        url: 'http://localhost:4318/v1/traces',
        timeoutMillis: 30000, // give large-but-legitimate batches more room, default is often 10s
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
                dbStatementSerializer: () => undefined, // don't serialize full query/statement
            },
        })
    ],
});

sdk.start();

console.log('✅ OpenTelemetry initialized (grocery-monolith)');

process.on('SIGTERM', async () => {
    await sdk.shutdown();
    console.log('🛑 OpenTelemetry shutdown complete');
    process.exit(0);
});




























