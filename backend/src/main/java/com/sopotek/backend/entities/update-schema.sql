CREATE TABLE users_tables
(
    id            INT AUTO_INCREMENT NOT NULL,
    username      VARCHAR(255)       NOT NULL,
    password      VARCHAR(255)       NOT NULL,
    email         VARCHAR(255)       NOT NULL,
    first_name    VARCHAR(255)       NULL,
    last_name     VARCHAR(255)       NULL,
    middle_name   VARCHAR(255)       NULL,
    phone         VARCHAR(255)       NULL,
    gender        VARCHAR(255)       NULL,
    address       VARCHAR(255)       NULL,
    date_of_birth date               NULL,
    country       VARCHAR(255)       NULL,
    state         VARCHAR(255)       NULL,
    city          VARCHAR(255)       NULL,
    CONSTRAINT pk_users_tables PRIMARY KEY (id)
);

ALTER TABLE users_tables
    ADD CONSTRAINT uc_users_tables_email UNIQUE (email);

ALTER TABLE users_tables
    ADD CONSTRAINT uc_users_tables_username UNIQUE (username);