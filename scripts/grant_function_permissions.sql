-- ========================================
-- Grant Function App Database Permissions
-- The function app needs WRITE access to insert pricing data
-- ========================================

-- Create user for Function App managed identity
IF NOT EXISTS (SELECT * FROM sys.database_principals WHERE name = 'func-pricing-dev-gwc')
BEGIN
    CREATE USER [func-pricing-dev-gwc] FROM EXTERNAL PROVIDER;
    PRINT '✓ Created user [func-pricing-dev-gwc]';
END
ELSE
BEGIN
    PRINT '  User [func-pricing-dev-gwc] already exists';
END

-- Grant db_datareader role (for reading data)
IF IS_ROLEMEMBER('db_datareader', 'func-pricing-dev-gwc') = 0
BEGIN
    ALTER ROLE db_datareader ADD MEMBER [func-pricing-dev-gwc];
    PRINT '✓ Granted db_datareader role to [func-pricing-dev-gwc]';
END
ELSE
BEGIN
    PRINT '  [func-pricing-dev-gwc] already has db_datareader role';
END

-- Grant db_datawriter role (for inserting pricing data)
IF IS_ROLEMEMBER('db_datawriter', 'func-pricing-dev-gwc') = 0
BEGIN
    ALTER ROLE db_datawriter ADD MEMBER [func-pricing-dev-gwc];
    PRINT '✓ Granted db_datawriter role to [func-pricing-dev-gwc]';
END
ELSE
BEGIN
    PRINT '  [func-pricing-dev-gwc] already has db_datawriter role';
END

PRINT '';
PRINT '==========================================';
PRINT '✓ FUNCTION APP PERMISSIONS GRANTED!';
PRINT '==========================================';
PRINT 'The function app can now:';
PRINT '  - Read from all tables (db_datareader)';
PRINT '  - Write to all tables (db_datawriter)';
PRINT '';
PRINT 'Retry triggering the function now.';
