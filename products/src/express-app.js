const express = require("express");
const cors = require("cors");
const path = require("path");
const { products, appEvents } = require("./api");
const client = require("prom-client");

const { CreateChannel } = require("./utils");

module.exports = async (app) => {
  app.use(express.json());
  app.use(cors());
  app.use(express.static(__dirname + "/public"));

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

  const channel = await CreateChannel();
  products(app, channel);

  // error handling
};
