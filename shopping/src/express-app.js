const express = require('express');
const cors  = require('cors');
const path = require('path');
const { shopping, appEvents } = require('./api');
const { CreateChannel } = require('./utils');
const client = require("prom-client");

module.exports = async (app) => {

    app.use(express.json());
    app.use(cors());
    app.use(express.static(__dirname + '/public'))

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
 
    //api
    // appEvents(app);

    const channel = await CreateChannel()

    shopping(app, channel);
    // error handling
    
}
