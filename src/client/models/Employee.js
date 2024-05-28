const { DataTypes } = require('sequelize');
const sequelize = require('../config/db');

const Employee = sequelize.define('Employee', {
    firstname: {
        type: DataTypes.STRING,
        allowNull: false
    },
    lastname: {
        type: DataTypes.STRING,
        allowNull: false
    }
});

module.exports = Employee;