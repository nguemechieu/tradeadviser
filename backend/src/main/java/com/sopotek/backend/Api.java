package com.sopotek.backend;

import com.sopotek.backend.entities.User;
import jakarta.transaction.SystemException;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.mail.SimpleMailMessage;
import org.springframework.mail.javamail.JavaMailSender;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Optional;

@RestController
@RequestMapping("/api/v1/users")
public class Api {

    @Autowired
    private UserService userService;

    //Post mapping routes


    @PostMapping("/api/v1/login/auth")
    public ResponseEntity<String> authenticateUser(@RequestBody User user) {

        // Validate user credentials
        if (userService.validateUser(user)) {
            return new ResponseEntity<>("User authenticated successfully", HttpStatus.OK);
        }
        else {
            return new ResponseEntity<>("Invalid username or password", HttpStatus.UNAUTHORIZED);
        }
    }

    @PostMapping("/api/v1/register/auth")
    public ResponseEntity<String> registerUser(@RequestBody User user) throws SystemException {
        // Validate user credentials
        if (userService.validateUser(user)) {
            userService.saveUser(user);
            return new ResponseEntity<>("User registered successfully", HttpStatus.CREATED);
        }
        else {
            return new ResponseEntity<>("Failed to register user", HttpStatus.INTERNAL_SERVER_ERROR);
        }
    }


    private JavaMailSender mailSender;

    @PostMapping("/api/v1/forgotpassword/auth")

    public ResponseEntity<String> forgotPassword(@RequestBody User user) {
        // Validate user credentials
        if (userService.validateUser(user)) {
            // Generate a password reset token or link (this could be a JWT or a UUID-based token)
            String resetToken = userService.generateResetToken(user);

            // Send email with the reset password link
            String resetLink = "https://yourapp.com/reset-password?token=" + resetToken;
            sendResetPasswordEmail(user.getEmail(), resetLink);

            return new ResponseEntity<>("Password reset link sent successfully", HttpStatus.OK);
        } else {
            return new ResponseEntity<>("Invalid username or email", HttpStatus.UNAUTHORIZED);
        }
    }

    private void sendResetPasswordEmail(String toEmail, String resetLink) {
        SimpleMailMessage message = new SimpleMailMessage();
        message.setTo(toEmail);
        message.setSubject("Password Reset Request");
        message.setText("To reset your password, click the following link: " + resetLink);
        mailSender.send(message);
    }
















    @GetMapping("/api/v1/users")
    public ResponseEntity<List<User>> getAllUsers() {
        List<User> users = userService.getAllUsers();
        return new ResponseEntity<>(users, HttpStatus.OK);
    }

    @GetMapping("/api/v1/users/{id}")
    public  ResponseEntity<User> getUserById(@PathVariable Integer id) {
        Optional<User> res = userService.getUserById(id);
        return res.map(ResponseEntity::ok).orElse(new ResponseEntity<>(HttpStatus.NOT_FOUND));

    }
    @PutMapping("/api/v1/users/{id}")
    public ResponseEntity<User> updateUser(@PathVariable Integer id, @RequestBody User updatedUser) throws SystemException {
        Optional<User> userOptional = userService.getUserById(id);
        if (userOptional.isPresent()) {
            User user = userOptional.get();
            user.setUsername(updatedUser.getUsername());
            user.setPassword(updatedUser.getPassword());
            return new ResponseEntity<>(userService.saveUser(user), HttpStatus.OK);
        } else {
            return new ResponseEntity<>(HttpStatus.NOT_FOUND);
        }
    }

    @DeleteMapping("/api/v1/users")
    public  ResponseEntity<String> deleteAllUsers() {
        userService.deleteAllUsers();
        return new ResponseEntity<>("All users have been deleted", HttpStatus.OK);
    }















    @PostMapping("/api/v1/users/{id}")
    public User createUser(@RequestBody User user) throws SystemException {
        return userService.saveUser(user);
    }

    @DeleteMapping("/api/v1/users/{id}")
    public void deleteUser(@PathVariable Integer id) throws SystemException {
        userService.deleteUser(id);
    }
}