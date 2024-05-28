const express = require('express');
const path = require('path');
const bodyParser = require('body-parser');
const userService = require('../client/services/userService/userService');
const employeeService = require('../client/services/employeeService/employeeService');

const API= require('./routes/root')

const app = express();
const port = process.env.PORT || 3000;

app.use(bodyParser.json());

// API routes
app.post('/users', async (req, res) => {
    const { username, password, roles, refreshToken } = req.body;

    try {
        const userId = await userService.addUser(username, password, roles, refreshToken);
        res.status(201).json({ userId });
    } catch (err) {
        res.status(500).json({ error: 'Failed to add user' });
    }
});

app.get('/users/:username', async (req, res) => {
    const { username } = req.params;

    try {
        const user = await userService.getUserByUsername(username);
        if (user) {
            res.json(user);
        } else {
            res.status(404).json({ error: 'User not found' });
        }
    } catch (err) {
        res.status(500).json({ error: 'Failed to get user' });
    }
});

app.post('/employees', async (req, res) => {
    const { firstname, lastname } = req.body;

    try {
        const employeeId = await employeeService.addEmployee(firstname, lastname);
        res.status(201).json({ employeeId });
    } catch (err) {
        res.status(500).json({ error: 'Failed to add employee' });
    }
});

app.get('/employees/:id', async (req, res) => {
    const { id } = req.params;

    try {
        const employee = await employeeService.getEmployeeById(id);
        if (employee) {
            res.json(employee);
        } else {
            res.status(404).json({ error: 'Employee not found' });
        }
    } catch (err) {
        res.status(500).json({ error: 'Failed to get employee' });
    }
});

// Serve static files from the React app
if (process.env.NODE_ENV === 'production') {
    app.use(express.static(path.join(__dirname, 'client/build')));

    app.get('*', (req, res) => {
        res.sendFile(path.join(__dirname, 'client/build', 'index.html'));
    });
    app.use('/',API)
}

module.exports = app;