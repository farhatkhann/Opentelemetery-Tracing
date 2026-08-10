const express = require('express');
const { PORT } = require('./config');
const { databaseConnection } = require('./database');
const expressApp = require('./express-app');
const { CreateChannel } = require('./utils')

const StartServer = async() => {
    console.log("Checking here....");
  console.log("PORT_prod: ",process.env.PORT);
    const app = express();
    console.log("Port index: ",PORT);
    await databaseConnection();

    const channel = await CreateChannel()

    await expressApp(app, channel);
    

    app.listen(PORT, () => {
          console.log(`listening to port ${PORT}`);
    })
    .on('error', (err) => {
        console.log(err);
        process.exit();
    })
    .on('close', () => {
        channel.close();
    })
    

}

StartServer();
