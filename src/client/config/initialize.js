const sequelize = require('../config/db');
const User = require('../models/User');
const Employee = require('../models/Employee');

async function initialize() {
    try {
        // Sync all defined models to the DB
        await sequelize.sync();

        console.log('Database & tables created or already exist.');
    } catch (err) {
        console.error('Error initializing the database:', err);
    }
}

initialize().then(() => {
    console.log('Database initialized');
}).catch((e) => {
    console.log("Database error: " + e);
});

module.exports = { sequelize, User, Employee };