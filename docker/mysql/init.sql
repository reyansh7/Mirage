-- Acme Technologies corporate schema (Phase 2)

CREATE TABLE IF NOT EXISTS departments (
  id INT PRIMARY KEY,
  name VARCHAR(80) NOT NULL,
  head VARCHAR(100),
  budget INT
);

CREATE TABLE IF NOT EXISTS employees (
  id INT PRIMARY KEY,
  name VARCHAR(100) NOT NULL,
  email VARCHAR(150),
  department VARCHAR(80),
  title VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS projects (
  id INT PRIMARY KEY,
  name VARCHAR(100) NOT NULL,
  status VARCHAR(40),
  owner VARCHAR(100),
  repo VARCHAR(255)
);

CREATE TABLE IF NOT EXISTS servers (
  id INT PRIMARY KEY,
  hostname VARCHAR(100) NOT NULL,
  ip VARCHAR(64),
  role VARCHAR(80),
  env VARCHAR(40)
);

INSERT INTO departments (id, name, head, budget) VALUES
  (1, 'Engineering', 'Bob Smith', 2400000),
  (2, 'DevOps', 'Alice Johnson', 980000),
  (3, 'Finance', 'Maria Garcia', 450000),
  (4, 'HR', 'Chris Patel', 320000),
  (5, 'Security', 'David Lee', 610000)
ON DUPLICATE KEY UPDATE name = VALUES(name);

INSERT INTO employees (id, name, email, department, title) VALUES
  (1, 'Alice Johnson', 'alice.johnson@acme-tech.internal', 'DevOps', 'Senior DevOps Engineer'),
  (2, 'Bob Smith', 'bob.smith@acme-tech.internal', 'Engineering', 'Backend Engineer'),
  (3, 'David Lee', 'david.lee@acme-tech.internal', 'Security', 'Security Analyst'),
  (4, 'Maria Garcia', 'maria.garcia@acme-tech.internal', 'Finance', 'Finance Manager'),
  (5, 'Chris Patel', 'chris.patel@acme-tech.internal', 'HR', 'HR Business Partner'),
  (6, 'Sam Rivera', 'sam.rivera@acme-tech.internal', 'Engineering', 'Frontend Engineer'),
  (7, 'Jordan Kim', 'jordan.kim@acme-tech.internal', 'DevOps', 'Platform Engineer')
ON DUPLICATE KEY UPDATE name = VALUES(name);

INSERT INTO projects (id, name, status, owner, repo) VALUES
  (1, 'atlas-api', 'active', 'Bob Smith', 'git@git.acme-tech.internal:platform/atlas-api.git'),
  (2, 'edge-gateway', 'active', 'Alice Johnson', 'git@git.acme-tech.internal:infra/edge-gateway.git'),
  (3, 'payroll-sync', 'maintenance', 'Maria Garcia', 'git@git.acme-tech.internal:finance/payroll-sync.git'),
  (4, 'zero-trust-vpn', 'planning', 'David Lee', 'git@git.acme-tech.internal:security/zero-trust-vpn.git')
ON DUPLICATE KEY UPDATE name = VALUES(name);

INSERT INTO servers (id, hostname, ip, role, env) VALUES
  (1, 'build-server-01', '10.0.5.18', 'ci-build', 'prod'),
  (2, 'db-primary-01', '10.0.5.40', 'mysql-primary', 'prod'),
  (3, 'web-portal-01', '10.0.5.22', 'employee-portal', 'prod'),
  (4, 'jenkins-01', '10.0.5.30', 'ci', 'prod'),
  (5, 'redis-cache-01', '10.0.5.55', 'cache', 'prod')
ON DUPLICATE KEY UPDATE hostname = VALUES(hostname);

-- Convenience login still works: admin / admin123
