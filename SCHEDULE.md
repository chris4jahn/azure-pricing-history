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

- ✅ 2025-12-26 (Manual execution - testing)
- 📅 2026-01-01 at 01:30 UTC
- 📅 2026-04-01 at 01:30 UTC
- 📅 2026-07-01 at 01:30 UTC
- 📅 2026-10-01 at 01:30 UTC

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

## Testing

To manually trigger the function for testing:
```bash
az functionapp function show --name func-pricing-dev-gwc \
  --resource-group rg-pricing-dev-gwc \
  --function-name PriceSnapshot
```
