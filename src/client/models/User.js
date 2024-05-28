const { DataTypes } = require('sequelize');
const sequelize = require('../config/db');

const User = sequelize.define('User', {
    username: {
        type: DataTypes.STRING,
        allowNull: false
    },
    roles: {
        type: DataTypes.JSON,
        defaultValue: { User: 2001 }
    },
    password: {
        type: DataTypes.STRING,
        allowNull: false
    },
    refreshToken: {
        type: DataTypes.JSON,
        defaultValue: []
    }
});

module.exports = User;
