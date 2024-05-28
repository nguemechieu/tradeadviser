const User = require('../../models/User');

// Function to add a new user
async function addUser(username, password, roles = { User: 2001 }, refreshToken = []) {
    try {
        const user = await User.create({
            username,
            password,
            roles,
            refreshToken
        });
        return user.id;
    } catch (err) {
        console.error('Error adding user:', err);
        throw err;
    }
}

// Function to get a user by username
async function getUserByUsername(username) {
    try {
        return await User.findOne({where: {username:username}});
    } catch (err) {
        console.error('Error getting user by username:', err);
        throw err;
    }
}

module.exports = {
    addUser,
    getUserByUsername
};