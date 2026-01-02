-- Temporary diagnostics table for Azure Function connectivity
CREATE TABLE dbo.FunctionDiagnostics (
    id INT IDENTITY(1,1) PRIMARY KEY,
    functionName NVARCHAR(100),
    message NVARCHAR(4000),
    createdUtc DATETIME2 DEFAULT SYSUTCDATETIME()
);
