package com.sopotek.backend.repositories;

import com.sopotek.backend.Db;
import com.sopotek.backend.entities.User;
import jakarta.transaction.SystemException;
import org.jetbrains.annotations.NotNull;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

public class UserRepository {


    private final Db db = new Db();

    public List<User> findAll() {

        return db.queryUsers();
    }

    public Optional<User> findById(Integer id) {

        Object res = db.findOne(
                "SELECT * FROM users WHERE id =?",
                Integer.toString(id)
        );
        if (res == null) {
            return Optional.empty();
        }
        return   Optional.of((User) res);
    }

    public User save(User user) throws SystemException {
        db.insertUser(user);
        return user;


    }

    public void deleteById(Integer id) throws SystemException {

        db.deleteUser(id);
    }

    public boolean existsById(Integer id) {

        Object res = db.findOne(
                "SELECT COUNT(*) FROM users WHERE id =?",
                Integer.toString(id)
        );
        return (Integer) res > 0;
    }


    public boolean validate(@NotNull User user) {
        return user.getUsername()!= null && user.getPassword()!= null && user.getEmail()!= null;
    }

    public void deleteAll() {
        db.deleteAllUsers();
    }

    public String generateResetToken(@NotNull User user) {
        return UUID.fromString(user.toString()).toString();
    }
}
