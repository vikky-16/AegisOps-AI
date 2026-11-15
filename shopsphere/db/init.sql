-- ShopSphere E-Commerce Relational Schema
-- Real PostgreSQL database tables for Order, Inventory, Payment, and Notification services

CREATE TABLE IF NOT EXISTS inventory (
    sku VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    quantity INT NOT NULL DEFAULT 100,
    reserved INT NOT NULL DEFAULT 0,
    price NUMERIC(10, 2) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS orders (
    order_id VARCHAR(64) PRIMARY KEY,
    customer_id VARCHAR(64) NOT NULL,
    total_amount NUMERIC(10, 2) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'PENDING',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS order_items (
    id SERIAL PRIMARY KEY,
    order_id VARCHAR(64) REFERENCES orders(order_id) ON DELETE CASCADE,
    sku VARCHAR(64) REFERENCES inventory(sku),
    quantity INT NOT NULL,
    price NUMERIC(10, 2) NOT NULL
);

CREATE TABLE IF NOT EXISTS payments (
    payment_id VARCHAR(64) PRIMARY KEY,
    order_id VARCHAR(64) NOT NULL,
    amount NUMERIC(10, 2) NOT NULL,
    status VARCHAR(32) NOT NULL,
    transaction_ref VARCHAR(128) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS notifications (
    notification_id VARCHAR(64) PRIMARY KEY,
    order_id VARCHAR(64) NOT NULL,
    recipient VARCHAR(128) NOT NULL,
    channel VARCHAR(32) NOT NULL,
    status VARCHAR(32) NOT NULL,
    message TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Seed initial catalog items
INSERT INTO inventory (sku, name, quantity, reserved, price)
VALUES 
    ('SKU-LAPTOP-01', 'ProBook 16-inch M3', 500, 0, 1299.99),
    ('SKU-PHONE-02', 'AegisPhone Ultra 5G', 800, 0, 899.99),
    ('SKU-HEADSET-03', 'Studio Noise Cancelling Headphones', 1200, 0, 199.50),
    ('SKU-KEYBOARD-04', 'Mechanical Wireless Keyboard', 650, 0, 129.00),
    ('SKU-MONITOR-05', 'UltraWide 34-inch 144Hz Monitor', 300, 0, 499.00),
    ('SKU-MOUSE-06', 'Ergonomic Precision Mouse', 1500, 0, 69.99),
    ('SKU-SMARTWATCH-07', 'Fitness Smartwatch Pro', 750, 0, 249.99),
    ('SKU-CHARGER-08', '100W GaN Fast Charger', 2000, 0, 45.00),
    ('SKU-STAND-09', 'Aluminum Laptop Stand', 900, 0, 39.99),
    ('SKU-CABLE-10', 'Thunderbolt 4 Cable 2m', 2500, 0, 29.99)
ON CONFLICT (sku) DO NOTHING;
