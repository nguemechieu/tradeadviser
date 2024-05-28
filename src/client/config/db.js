const { Sequelize } = require('sequelize');

// Create a new Sequelize instance
const sequelize = new Sequelize('tradeadviser', 'root', 'password', {
    host: 'localhost',
    dialect: 'mysql'
});

module.exports = sequelize;
