


-- Table for Bachatgats
CREATE TABLE gats (
    gat_id INT PRIMARY KEY AUTO_INCREMENT,
    gat_name VARCHAR(255) NOT NULL,
    member_count INT NOT NULL,
    address TEXT,
    contact_number VARCHAR(15) NOT NULL,
    email VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table for Transactions
CREATE TABLE transactions (
    transaction_id INT PRIMARY KEY AUTO_INCREMENT,
    gat_id INT,
    amount DECIMAL(10,2) NOT NULL,
    transaction_date DATE,
    description TEXT,
    FOREIGN KEY (gat_id) REFERENCES gats(gat_id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE members (
    member_id INT AUTO_INCREMENT PRIMARY KEY,
    gat_id INT,
    member_name VARCHAR(255) NOT NULL,
    member_email VARCHAR(255) NOT NULL,
    member_password VARCHAR(255) NOT NULL,
    member_address TEXT NOT NULL,
    member_mobile VARCHAR(15) NOT NULL,
    member_type ENUM('member', 'admin') NOT NULL,
    FOREIGN KEY (gat_id) REFERENCES gats(gat_id)
);

CREATE TABLE monthly_bachat (
    bachat_id INT AUTO_INCREMENT PRIMARY KEY,
    gat_id INT,
    member_id INT,
    bachat_date DATE,
    bachat_amount DECIMAL(10, 2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (gat_id) REFERENCES gats(gat_id),
    FOREIGN KEY (member_id) REFERENCES members(member_id)
);

CREATE TABLE total_bachat (
    total_bachat_id INT AUTO_INCREMENT PRIMARY KEY,
    gat_id INT,
    total_bachat_amount DECIMAL(10, 2),
    month_year DATE,
    FOREIGN KEY (gat_id) REFERENCES gats(gat_id)
);

-- SQL query to create the loan_requests table
CREATE TABLE IF NOT EXISTS loan_requests (
    request_id INT AUTO_INCREMENT PRIMARY KEY,
    gat_id INT NOT NULL,
    member_id INT NOT NULL,
    request_amount DECIMAL(10, 2) NOT NULL,
    interest_rate FLOAT NOT NULL,
    request_status ENUM('pending', 'approved', 'rejected') DEFAULT 'pending',
    request_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (gat_id) REFERENCES gats(gat_id),
    FOREIGN KEY (member_id) REFERENCES members(member_id)
);

CREATE TABLE interest_rate (
    interest_rate_id INT AUTO_INCREMENT PRIMARY KEY,
    gat_id INT,
    interest_rate FLOAT,
    start_date DATE,
    FOREIGN KEY (gat_id) REFERENCES gats(gat_id) ON DELETE CASCADE
);
