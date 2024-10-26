package com.sopotek.backend;


import com.sopotek.backend.entities.User;
import jakarta.persistence.EntityManager;
import jakarta.persistence.EntityManagerFactory;
import jakarta.transaction.HeuristicMixedException;
import jakarta.transaction.HeuristicRollbackException;
import jakarta.transaction.RollbackException;
import jakarta.transaction.SystemException;
import jakarta.persistence.*;

import static jakarta.persistence.Persistence.createEntityManagerFactory;

import org.jetbrains.annotations.NotNull;
import org.springframework.stereotype.Component;

import java.util.List;

import java.util.Properties;
import java.util.logging.Logger;

@Component
public class Db {

    private static final Logger LOG = Logger.getLogger(Db.class.getName());


    EntityManager entityManager;
    EntityManagerFactory entityManagerFactory;

    // Initialize Hibernate SessionFactory
    public Db() {
        // Initialize EntityManagerFactory with necessary properties
       this. entityManagerFactory = createEntityManagerFactory(
                "com.sopotek.backend.entities.User",
                new Properties() {{
                    put("hibernate.dialect", "org.hibernate.dialect.MySQLDialect");
                    put("hibernate.hbm2ddl.auto", "update");
                    put("hibernate.show_sql", "true");
                }}
        );
       this. entityManager = entityManagerFactory.createEntityManager();

        //try {

          //  enableSQLiteForeignKeys(entityManager);
            // dropTables();
            // Create users' table
//            entityManager.createNativeQuery(
//                    "CREATE TABLE IF NOT EXISTS users (" +
//                            "id INTEGER PRIMARY KEY AUTOINCREMENT ," +
//                            "username VARCHAR(255) NOT NULL UNIQUE," +
//                            "password VARCHAR(255) NOT NULL," +
//                            "email VARCHAR(255) NOT NULL UNIQUE" +
//                            "firstname VARCHAR(255) NOT NULL" +
//                            "lastname VARCHAR(255) NOT NULL," +
//                            "middlename VARCHAR(255)," +
//                            "phone VARCHAR(255)," +
//                            "gender VARCHAR(10)," +
//                            "address VARCHAR(255)," +
//                            "date_of_birth DATE," +
//                            "country VARCHAR(255)," +
//                            "state VARCHAR(255)," +
//                            "city VARCHAR(255)" +
//
//                            ")"
//            ).executeUpdate();
//
//            // Create currency table
//            entityManager.createNativeQuery(
//                    "CREATE TABLE IF NOT EXISTS currencies (" +
//                            "currency_id INTEGER PRIMARY KEY AUTOINCREMENT ," +
//                            "currencyType VARCHAR(255) NOT NULL," +
//                            "fullDisplayName VARCHAR(255) NOT NULL," +
//                            "shortDisplayName VARCHAR(255)," +
//                            "code VARCHAR(5) NOT NULL," +
//                            "fractionalDigits INTEGER NOT NULL," +
//                            "symbol VARCHAR(10) NOT NULL," +
//                            "image VARCHAR(255) NOT NULL" +
//                            ")"
//            ).executeUpdate();
//
//
//            // Create portfolio_items table
//            entityManager.createNativeQuery(
//                    "CREATE TABLE IF NOT EXISTS portfolio_items (" +
//                            "id INTEGER PRIMARY KEY AUTOINCREMENT  NOT NULL," +
//                            "user_id INTEGER NOT NULL," +
//                            "currency_id INTEGER NOT NULL," +
//                            "amount DECIMAL(10, 2) NOT NULL," +
//                            "FOREIGN KEY (user_id) REFERENCES users(id)," +
//                            "FOREIGN KEY (currency_id) REFERENCES currencies(id)" +
//                            ")"
//            ).executeUpdate();
//
//            // Create trade table
//            entityManager.createNativeQuery(
//                    "CREATE TABLE IF NOT EXISTS trades (" +
//                            "id INTEGER PRIMARY KEY AUTOINCREMENT," +
//                            "user_id INTEGER NOT NULL," +
//                            "currency_id INTEGER NOT NULL," +
//                            "price DECIMAL(10, 2) NOT NULL," +
//                            "volume DECIMAL(10, 2) NOT NULL," +
//                            "timestamp DATETIME NOT NULL," +
//                            "FOREIGN KEY (user_id) REFERENCES users(id)," +
//                            "FOREIGN KEY (currency_id) REFERENCES currencies(id)" +
//                            ")"
//            ).executeUpdate();
//
//            // Create portfolio_history table
//            entityManager.createNativeQuery(
//                    "CREATE TABLE IF NOT EXISTS portfolio_history (" +
//                            "id INTEGER PRIMARY KEY AUTOINCREMENT  NOT NULL," +
//                            "user_id INTEGER NOT NULL," +
//                            "currency_id INTEGER NOT NULL," +
//                            "amount DECIMAL(10, 2) NOT NULL," +
//                            "timestamp DATETIME NOT NULL," +
//                            "FOREIGN KEY (user_id) REFERENCES users(id)," +
//                            "FOREIGN KEY (currency_id) REFERENCES currencies(id)" +
//                            ")"
//            ).executeUpdate();
//
//            // Create account table
//            entityManager.createNativeQuery(
//                    "CREATE TABLE IF NOT EXISTS accounts (" +
//                            "id INTEGER PRIMARY KEY AUTOINCREMENT  NOT NULL," +
//                            "user_id INTEGER NOT NULL," +
//                            "currency_id INTEGER NOT NULL," +
//                            "balance DECIMAL(10, 2) NOT NULL," +
//                            "FOREIGN KEY (user_id) REFERENCES users(id)," +
//                            "FOREIGN KEY (currency_id) REFERENCES currencies(id)" +
//                            ")"
//            ).executeUpdate();
//
//            // Create candle_data table
//            entityManager.createNativeQuery(
//                    "CREATE TABLE IF NOT EXISTS candle_data (" +
//                            "id INTEGER PRIMARY KEY AUTOINCREMENT  NOT NULL," +
//                            "timestamp DATETIME NOT NULL," +
//                            "open DECIMAL(10, 2) NOT NULL," +
//                            "high DECIMAL(10, 2) NOT NULL," +
//                            "low DECIMAL(10, 2) NOT NULL," +
//                            "close DECIMAL(10, 2) NOT NULL," +
//                            "volume DECIMAL(10, 2) NOT NULL," +
//                            "currency_id INTEGER NOT NULL," +
//                            "FOREIGN KEY (currency_id) REFERENCES currencies(id)" +
//                            ")"
//            ).executeUpdate();
//
//            entityManager.getTransaction().commit();
//            LOG.info("All tables created successfully");
//
//        } catch (Exception e) {
//            LOG.severe("Error during table creation"+ e);
//            if (entityManager.getTransaction().isActive()) {
//                entityManager.getTransaction().rollback();
//            }
//        }

            }

    private void enableSQLiteForeignKeys(@NotNull EntityManager entityManager) {
        entityManager.getTransaction().begin();
        Query query = entityManager.createNativeQuery("PRAGMA foreign_keys = ON;");
        query.executeUpdate();
        entityManager.getTransaction().commit();

    }

    public List<User> queryUsers() {

        try {
            return entityManager.createQuery("FROM User", User.class).getResultList();
        } catch (Exception e) {
            LOG.severe("Error during querying users: " + e);
            throw new RuntimeException(e);
        }
    }



    public boolean updateUserDetails(int userId, String username, String password, String email, String firstName, String lastName,
                                     String middleName, String phone, String gender, String address, String dateOfBirth,
                                     String country, String state, String city) throws SystemException, HeuristicRollbackException, HeuristicMixedException, RollbackException {


             entityManager.getTransaction().begin();
            User user =
                    (User) entityManager.createQuery("FROM User WHERE id = :userId")
                           .setParameter("userId", userId)
                           .getSingleResult();
            if (user != null) {
                user.setUsername(username);
                user.setPassword(password);
                user.setEmail(email);
                user.setFirstName(firstName);
                user.setLastName(lastName);
                user.setMiddleName(middleName);
                user.setPhone(phone);
                user.setGender(gender);
                user.setAddress(address);
                user.setDateOfBirth(dateOfBirth);
                user.setCountry(country);
                user.setState(state);
                user.setCity(city);
                entityManager.getTransaction().commit();
                return true;
            }

        return false;
    }

    // Close the SessionFactory when application ends
    public void close() {

        if (entityManager!= null) {
            entityManager.close();
        }
    }

    public Object findOne(String query, String value) {

        return entityManager.createQuery(query).setParameter(1, value).getSingleResult();
    }



    public void insertUser(User user) throws SystemException {

        try {
            entityManager.getTransaction().begin();
            entityManager.persist(user);
            entityManager.getTransaction().commit();
        } catch (Exception e) {
            LOG.severe("Error during inserting user: " + e);
            if (entityManager.getTransaction().isActive()) {
                entityManager.getTransaction().rollback();
            }
        }

    }

    public void deleteUser(Integer id) {
        try {
            entityManager.getTransaction().begin();
            User user = entityManager.find(User.class, id);
            if (user!= null) {
                entityManager.remove(user);
            }
            entityManager.getTransaction().commit();
        } catch (Exception e) {
            LOG.severe("Error during deleting user with id: " + id + ", error: " + e);
            if (entityManager.getTransaction().isActive()) {
                entityManager.getTransaction().rollback();
            }
        }
    }

    public void deleteAllUsers() {
        try {
            entityManager.getTransaction().begin();
            entityManager.createQuery("DELETE FROM User").executeUpdate();
            entityManager.getTransaction().commit();
        } catch (Exception e) {
            LOG.severe("Error during deleting all users, error: " + e);
            if (entityManager.getTransaction().isActive()) {
                entityManager.getTransaction().rollback();
            }
        }
    }
}
