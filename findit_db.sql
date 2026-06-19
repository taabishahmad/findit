-- ============================================================
--  FindIt v2 – Community Lost & Found Board
--  Run this ENTIRE file in phpMyAdmin → SQL tab
-- ============================================================

CREATE DATABASE IF NOT EXISTS findit_db;
USE findit_db;

-- ── Users ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    name          VARCHAR(100) NOT NULL,
    email         VARCHAR(150) NOT NULL UNIQUE,
    phone         VARCHAR(20)  NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    profile_pic   VARCHAR(255) DEFAULT NULL,
    is_verified   TINYINT(1)   DEFAULT 0,
    created_at    DATETIME     DEFAULT CURRENT_TIMESTAMP
);

-- If upgrading from v1: run this line to add profile_pic to existing table
-- ALTER TABLE users ADD COLUMN profile_pic VARCHAR(255) DEFAULT NULL;

-- ── OTP Tokens ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS otp_tokens (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    email      VARCHAR(150) NOT NULL,
    otp        VARCHAR(10)  NOT NULL,
    purpose    ENUM('verify','reset') DEFAULT 'verify',
    expires_at DATETIME NOT NULL,
    used       TINYINT(1) DEFAULT 0
);

-- ── Posts ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS posts (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    user_id     INT          DEFAULT NULL,
    title       VARCHAR(150) NOT NULL,
    description TEXT         NOT NULL,
    location    VARCHAR(200) NOT NULL,
    type        ENUM('lost','found') NOT NULL,
    contact     VARCHAR(100) NOT NULL,
    date_lost   DATE,
    photo       VARCHAR(255) DEFAULT NULL,
    status      ENUM('active','resolved') DEFAULT 'active',
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);

-- ── AI Chat History ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS chat_history (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    user_id    INT          DEFAULT NULL,
    session_id VARCHAR(64)  NOT NULL,
    role       ENUM('user','assistant') NOT NULL,
    message    TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ── Sample demo user (password = Demo@1234) ───────────────────
-- bcrypt hash of Demo@1234
INSERT IGNORE INTO users (name, email, phone, password_hash, is_verified) VALUES
('Demo User', 'demo@findit.pk', '03001234567',
 '$2b$12$KIXnBvFq/g5gY3MFn8XNiOemME0R2yVLMFbBsmNhKQm3Kx/5TYXtO', 1);

-- ── Sample posts tied to demo user ───────────────────────────
INSERT IGNORE INTO posts (user_id, title, description, location, type, contact, date_lost, status) VALUES
(1, 'Black Leather Wallet',
 'Contains NIC card and some cash. No money needed, just want my ID back.',
 'IIUI Main Cafeteria', 'lost', '03001234567', '2026-05-10', 'active'),
(1, 'Found: Blue Water Bottle',
 'Hydro Flask, blue colour, found near the library entrance.',
 'IIUI Central Library', 'found', '03219876543', '2026-05-12', 'active'),
(1, 'Lost Earphones (white)',
 'Apple EarPods in a small case. Lost somewhere between Block-C and the parking.',
 'Block-C Parking Lot', 'lost', '03115556677', '2026-05-14', 'active');
