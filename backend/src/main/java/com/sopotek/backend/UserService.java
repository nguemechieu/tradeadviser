package com.sopotek.backend;

import com.sopotek.backend.entities.User;
import com.sopotek.backend.repositories.UserRepository;
import jakarta.transaction.SystemException;

import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Optional;

@Service
public class UserService {

    private final UserRepository userRepository;
    // Constructor injection is preferred for dependency injection in Spring
    public UserService() {
        this.userRepository = new UserRepository();
    }

    public List<User> getAllUsers() {
        return userRepository.findAll();
    }

    public Optional<User> getUserById(Integer id) {
        return userRepository.findById(id);
    }

    public User saveUser(User user) throws SystemException {
        return userRepository.save(user);
    }

    public void deleteUser(Integer id) throws SystemException {
        userRepository.deleteById(id);
    }

    public boolean validateUser(User user) {
        return userRepository.validate(user);    }

    public void deleteAllUsers() {
        userRepository.deleteAll();
    }

    public String generateResetToken(User user) {
        return userRepository.generateResetToken(user);
    }
}
