const Employee = require('../../models/Employee');

// Function to add a new employee
async function addEmployee(firstname, lastname) {
    try {
        const employee = await Employee.create({
            firstname,
            lastname
        });
        return employee.id;
    } catch (err) {
        console.error('Error adding employee:', err);
        throw err;
    }
}

// Function to get an employee by ID
async function getEmployeeById(id) {
    try {
        return await Employee.findByPk(id);
    } catch (err) {
        console.error('Error getting employee by ID:', err);
        throw err;
    }
}

module.exports = {
    addEmployee,
    getEmployeeById
};
