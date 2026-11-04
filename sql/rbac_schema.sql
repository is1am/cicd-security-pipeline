-- rbac_schema.sql
-- Схема RBAC для PostgreSQL (шаг 1 методических указаний ПР5).
-- Демонстрационный сервис использует ту же схему в SQLite (app/db.py).

DROP TABLE IF EXISTS role_permissions, user_roles, permissions, roles, users CASCADE;

CREATE TABLE users (
    id            SERIAL PRIMARY KEY,
    username      VARCHAR(50)  NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    is_active     BOOLEAN      NOT NULL DEFAULT TRUE
);

CREATE TABLE roles (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(50) NOT NULL UNIQUE,
    description TEXT
);

CREATE TABLE permissions (
    id       SERIAL PRIMARY KEY,
    name     VARCHAR(50) NOT NULL UNIQUE,
    resource VARCHAR(50) NOT NULL,
    action   VARCHAR(20) NOT NULL,
    UNIQUE (resource, action)
);

-- Связь многие-ко-многим: пользователь <-> роль
CREATE TABLE user_roles (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE ON UPDATE CASCADE,
    role_id INTEGER NOT NULL REFERENCES roles(id) ON DELETE CASCADE ON UPDATE CASCADE,
    PRIMARY KEY (user_id, role_id)
);

-- Связь многие-ко-многим: роль <-> разрешение
CREATE TABLE role_permissions (
    role_id       INTEGER NOT NULL REFERENCES roles(id)       ON DELETE CASCADE ON UPDATE CASCADE,
    permission_id INTEGER NOT NULL REFERENCES permissions(id) ON DELETE CASCADE ON UPDATE CASCADE,
    PRIMARY KEY (role_id, permission_id)
);

CREATE INDEX idx_user_roles_role ON user_roles(role_id);
CREATE INDEX idx_role_permissions_perm ON role_permissions(permission_id);

-- Начальные данные
INSERT INTO roles (name, description) VALUES
    ('ADMIN',     'Администратор: управление пользователями и аудитом'),
    ('MODERATOR', 'Модератор: просмотр журнала аудита'),
    ('USER',      'Рядовой сотрудник: только общие ресурсы');

INSERT INTO permissions (name, resource, action) VALUES
    ('READ_PUBLIC',  'public', 'read'),
    ('VIEW_AUDIT',   'audit',  'read'),
    ('EXPORT_AUDIT', 'audit',  'export'),
    ('MANAGE_USERS', 'users',  'write');

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id FROM roles r JOIN permissions p ON
       (r.name = 'ADMIN')
    OR (r.name = 'MODERATOR' AND p.name IN ('READ_PUBLIC', 'VIEW_AUDIT'))
    OR (r.name = 'USER'      AND p.name = 'READ_PUBLIC');

-- Все права пользователя (запрос, который выполняет middleware при каждом обращении)
-- SELECT DISTINCT p.name
-- FROM permissions p
-- JOIN role_permissions rp ON rp.permission_id = p.id
-- JOIN user_roles ur       ON ur.role_id = rp.role_id
-- WHERE ur.user_id = :user_id;
