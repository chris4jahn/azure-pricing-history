# Azure Pricing Snapshot Schedule

## Current Configuration

**Schedule**: Quarterly data collection  
**Cron Expression**: `0 30 1 1 1,4,7,10 *`

## Execution Times

The Azure Function runs at **01:30 UTC** on the following dates:

| Quarter | Month    | Date          | UTC Time |
|---------|----------|---------------|----------|
| Q1      | January  | January 1     | 01:30    |
| Q2      | April    | April 1       | 01:30    |
| Q3      | July     | July 1        | 01:30    |
| Q4      | October  | October 1     | 01:30    |

## Cron Expression Breakdown

```
0 30 1 1 1,4,7,10 *
│ │  │ │ │        │
│ │  │ │ │        └─ Day of week (any)
│ │  │ │ └────────── Months (1=Jan, 4=Apr, 7=Jul, 10=Oct)
│ │  │ └──────────── Day of month (1st)
│ │  └────────────── Hour (01:00)
│ └───────────────── Minute (30)
└─────────────────── Second (0)
```

## Next Execution Dates (2025-2026)

- ✅ 2025-12-26 at 15:50 UTC (Manual - stuck, marked FAILED)
- ✅ 2025-12-28 at 17:56 UTC (Manual - via ManualTrigger HTTP function)
- 📅 2026-01-01 at 01:30 UTC
- 📅 2026-04-01 at 01:30 UTC
- 📅 2026-07-01 at 01:30 UTC
- 📅 2026-10-01 at 01:30 UTC

## Manual Execution

### ManualTrigger HTTP Function

A dedicated HTTP-triggered function allows manual data collection anytime:

```bash
# Using master key (works for all functions)
curl -X POST "https://func-pricing-dev-gwc.azurewebsites.net/api/manualtrigger?code=<MASTER_KEY>"

# Get master key
az functionapp keys list --name func-pricing-dev-gwc \
  --resource-group rg-pricing-dev-gwc \
  --query "masterKey" -o tsv
```

**Response**: HTTP 200 with execution summary on success, HTTP 500 on error

**Execution Time**: 10-15 minutes for full data collection

### Function Characteristics

- **Idempotent**: Can safely re-run for same month
- **Auto-cleanup**: Marks hung snapshots (>2 hours) as FAILED
- **Error Handling**: Failed snapshots marked in database
- **Async Execution**: Returns immediately, processes in background

## Modification

To change the schedule, edit:
```
src/functions-python/PriceSnapshot/function.json
```

Then redeploy:
```bash
cd src/functions-python
func azure functionapp publish func-pricing-dev-gwc --python
```
