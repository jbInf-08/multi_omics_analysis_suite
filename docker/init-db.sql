-- Initialize Multi-Omics Analysis Suite Database

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "btree_gin";

-- Create schemas for organization
CREATE SCHEMA IF NOT EXISTS omics;
CREATE SCHEMA IF NOT EXISTS analysis;
CREATE SCHEMA IF NOT EXISTS ml;
CREATE SCHEMA IF NOT EXISTS audit;

-- Grant permissions
GRANT ALL PRIVILEGES ON SCHEMA omics TO omics;
GRANT ALL PRIVILEGES ON SCHEMA analysis TO omics;
GRANT ALL PRIVILEGES ON SCHEMA ml TO omics;
GRANT ALL PRIVILEGES ON SCHEMA audit TO omics;

-- Create audit log table
CREATE TABLE IF NOT EXISTS audit.activity_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID,
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(100),
    resource_id UUID,
    details JSONB,
    ip_address INET,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create index for faster queries
CREATE INDEX IF NOT EXISTS idx_activity_log_user ON audit.activity_log(user_id);
CREATE INDEX IF NOT EXISTS idx_activity_log_created ON audit.activity_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_activity_log_action ON audit.activity_log(action);

-- Log initialization
INSERT INTO audit.activity_log (action, details) 
VALUES ('database_initialized', '{"version": "1.0.0", "schemas": ["omics", "analysis", "ml", "audit"]}');
