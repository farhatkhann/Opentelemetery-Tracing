const express = require('express');
const cors  = require('cors');
const { customer, appEvents } = require('./api');
const { CreateChannel, SubscribeMessage } = require('./utils');
const client = require("prom-client");

module.exports = async (app) => {

    app.use(express.json()); 
    app.use(cors());
    app.use(express.static(__dirname + '/public'))

    //api
    // appEvents(app);

    const channel = await CreateChannel()

    // ------------------------------------------------------
    // Prometheus Metrics
    // ------------------------------------------------------

    client.collectDefaultMetrics();

    app.get("/metrics", async (req, res) => {
        try {
            res.set("Content-Type", client.register.contentType);
            res.end(await client.register.metrics());
        } catch (err) {
            res.status(500).end(err);
        }
    });
    
    customer(app, channel);
    // error handling
    
}
