CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS enterprise_telemetry (
    id SERIAL PRIMARY KEY,
    device_id VARCHAR(50) NOT NULL,
    subsystem VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL,
    temperature_c NUMERIC(5, 2),
    vibration_hz NUMERIC(5, 2),
    load_pct NUMERIC(5, 2),
    last_inspected TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO enterprise_telemetry (device_id, subsystem, status, temperature_c, vibration_hz, load_pct)
VALUES
('TURBINE-001', 'Compressor-A', 'OPTIMAL', 68.4, 23.1, 74.0),
('TURBINE-002', 'Bearing-Hub', 'WARNING', 92.1, 58.7, 89.5),
('TURBINE-003', 'Exhaust-Vent', 'CRITICAL', 114.3, 71.2, 94.2),
('PUMP-104', 'Hydraulic-Loop', 'OPTIMAL', 52.0, 12.4, 45.0);
