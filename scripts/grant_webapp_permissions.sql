-- Grant database permissions to the Web App managed identity
-- Run this in Azure Portal Query Editor

-- Create the user for the web app's managed identity
IF NOT EXISTS (SELECT * FROM sys.database_principals WHERE name = 'webapp-pricing-dev-gwc')
BEGIN
    CREATE USER [webapp-pricing-dev-gwc] FROM EXTERNAL PROVIDER;
    PRINT '✓ Created user [webapp-pricing-dev-gwc]';
END
ELSE
BEGIN
    PRINT '  User [webapp-pricing-dev-gwc] already exists';
END

-- Grant db_datareader role
IF IS_ROLEMEMBER('db_datareader', 'webapp-pricing-dev-gwc') = 0
BEGIN
    ALTER ROLE db_datareader ADD MEMBER [webapp-pricing-dev-gwc];
    PRINT '✓ Granted db_datareader role to [webapp-pricing-dev-gwc]';
END
ELSE
BEGIN
    PRINT '  [webapp-pricing-dev-gwc] already has db_datareader role';
END

PRINT '';
PRINT '✓ Web App permissions granted!';
PRINT 'The web app can now read pricing data from the database.';
