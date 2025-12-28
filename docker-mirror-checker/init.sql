-- 创建镜像源检测记录表
CREATE TABLE IF NOT EXISTS mirror_test_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    mirror_url VARCHAR(255) NOT NULL,
    available BOOLEAN NOT NULL,
    status VARCHAR(100),
    status_code INT,
    response_time DECIMAL(10, 2),
    test_time DATETIME NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_mirror_url (mirror_url),
    INDEX idx_test_time (test_time),
    INDEX idx_available (available)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 创建镜像源统计表
CREATE TABLE IF NOT EXISTS mirror_statistics (
    id INT AUTO_INCREMENT PRIMARY KEY,
    mirror_url VARCHAR(255) NOT NULL UNIQUE,
    total_tests INT DEFAULT 0,
    success_count INT DEFAULT 0,
    fail_count INT DEFAULT 0,
    avg_response_time DECIMAL(10, 2),
    last_success_time DATETIME,
    last_fail_time DATETIME,
    current_status BOOLEAN,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_current_status (current_status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 创建检测批次表
CREATE TABLE IF NOT EXISTS test_batches (
    id INT AUTO_INCREMENT PRIMARY KEY,
    batch_time DATETIME NOT NULL,
    total_mirrors INT NOT NULL,
    available_count INT NOT NULL,
    unavailable_count INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_batch_time (batch_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;




