# MITA Daily Budget Sheet — Setup Instructions

## What you get
A Google Sheets file that:
- Calculates your daily spending limit based on income + fixed expenses
- Automatically redistributes your budget when you overspend (the MITA engine)
- Colors each day green / yellow / red in real time
- Logs every automatic redistribution so you can see exactly where money moved

---

## Step 1 — Make your own copy

Open the shared link → **File → Make a copy** → save to your Google Drive.
Never edit the original — always work on your own copy.

---

## Step 2 — Fill in the Setup sheet

Open the **Setup** sheet and fill in column B:

| Field | Example |
|---|---|
| Monthly Net Income | 3200 |
| Rent / Mortgage | 800 |
| Utilities | 120 |
| Insurance | 60 |
| Debt Repayment | 150 |
| Savings Goal (monthly) | 300 |
| Currency Symbol | € |
| Budget Month (YYYY-MM) | 2026-05 |

> **Tip:** "Monthly Net Income" = what lands in your bank account after taxes.
> "Savings Goal" is sacred — the engine will never touch it when rebalancing.

---

## Step 3 — Generate your budget

Go to **MITA Budget → 1. Initial Setup — Generate My Budget**

This takes ~5 seconds and creates:
- **Categories** sheet — your monthly budget by category
- **Monthly** sheet — full breakdown summary
- **Calendar** sheet — 31-day plan with daily spending limits

---

## Step 4 — Log your spending

**Option A (recommended): Use the dialog**
Go to **MITA Budget → 2. Log Transaction**, fill in day/category/amount, click Add.

**Option B: Type directly in the Transactions sheet**
Add a row: Date | Day # | Category | Amount | Note
Leave column F (Processed) empty — the system fills it automatically.

As soon as you log a transaction, the Calendar updates instantly:
- The day's Spent column increases
- The Remaining column decreases
- The day turns green / yellow / red
- If you went over → the engine automatically reduces future days to compensate

---

## Understanding the Calendar colors

| Color | Meaning |
|---|---|
| Green | On track — spent ≤ planned |
| Yellow | Slight overspend (within 5% buffer) |
| Red | Overspent — future days will be reduced |
| Light gray | Future day — not yet reached |

---

## Understanding the Rebalance Log

Every time you overspend a day, MITA records exactly what happened:
- Which day triggered the rebalance
- Which future days had their budget reduced
- How much was moved

This is your financial transparency record. You can always see where the money came from.

---

## Priority system (why some categories are protected)

| Level | Name | Examples | Can be reduced? |
|---|---|---|---|
| 0 | SACRED | Savings, Rent, Debt | Never |
| 1 | PROTECTED | Groceries, Transport, Medical | Last resort |
| 2 | FLEXIBLE | Coffee, Personal Care | Yes |
| 3 | DISCRETIONARY | Dining Out, Entertainment | First to give |

When you overspend, the engine takes from DISCRETIONARY days first, then FLEXIBLE.
Your savings and rent are always untouched.

---

## Editing your budget

You can change any amount in the **Categories** sheet manually.
After editing, go to **MITA Budget → Rebuild Calendar (new month)** to recalculate the daily plan.

---

## New month

1. Update **Budget Month** in the Setup sheet (e.g. `2026-06`)
2. Clear the **Transactions** sheet (keep the header row)
3. Go to **MITA Budget → Rebuild Calendar (new month)**
4. Optionally: **MITA Budget → Reset Rebalance Log**

---

## Troubleshooting

**Calendar not updating after I type in Transactions?**
Make sure the `onEdit` trigger is installed:
Extensions → Apps Script → Triggers → Add trigger → `onEdit` → From spreadsheet → On edit

**"Run Initial Setup first" error on Rebuild Calendar?**
The Setup and Categories sheets need to exist. Run Initial Setup once first.

**Amounts look wrong?**
Check that your Monthly Net Income is after-tax take-home pay, not gross salary.
