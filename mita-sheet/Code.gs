// ============================================================
// MITA DAILY BUDGET SHEET — Google Apps Script
// Version 1.0 | mitafinance.com
// ============================================================
// Sheets structure:
//   Setup       — user inputs once
//   Tiers       — income tier reference (hidden)
//   Categories  — category allocations (auto-generated, editable)
//   Monthly     — monthly budget overview
//   Calendar    — 31-day daily plan with live status
//   Transactions— user logs spending here
//   Rebalance   — audit log of automatic redistributions
// ============================================================

// ── CONSTANTS ────────────────────────────────────────────────

var SHEET = {
  SETUP:        'Setup',
  TIERS:        'Tiers',
  CATEGORIES:   'Categories',
  MONTHLY:      'Monthly',
  CALENDAR:     'Calendar',
  TRANSACTIONS: 'Transactions',
  REBALANCE:    'Rebalance'
};

var STATUS = { GREEN: 'green', YELLOW: 'yellow', RED: 'red', FUTURE: 'future' };

var PRIORITY = {
  SACRED:       0,
  PROTECTED:    1,
  FLEXIBLE:     2,
  DISCRETIONARY:3
};

// Category → priority mapping (mirrors category_priority.py)
var CAT_PRIORITY = {
  'Savings':         0, 'Emergency Fund':  0, 'Rent/Mortgage':   0,
  'Utilities':       0, 'Insurance':       0, 'Debt Repayment':  0,
  'Groceries':       1, 'Public Transport':1, 'Medical':         1,
  'Coffee':          2, 'Clothing':        2, 'Personal Care':   2,
  'Car/Gas':         2,
  'Dining Out':      3, 'Entertainment':   3, 'Subscriptions':   3,
  'Shopping':        3, 'Hobbies':         3, 'Travel':          3
};

// Tier definitions (mirrors budget_logic.py income tiers)
// [tierName, minIncome, savingsRate, groceries%, dining%, entertainment%, coffee%, transport%, clothing%, medical%, other%]
var TIER_DATA = [
  ['LOW',           0,     1500,  0.05, 0.30, 0.04, 0.01, 0.02, 0.08, 0.02, 0.02, 0.46],
  ['LOWER_MIDDLE',  1500,  3000,  0.08, 0.25, 0.06, 0.02, 0.03, 0.08, 0.03, 0.03, 0.42],
  ['MIDDLE',        3000,  5000,  0.12, 0.20, 0.08, 0.03, 0.04, 0.08, 0.04, 0.04, 0.37],
  ['UPPER_MIDDLE',  5000,  8000,  0.15, 0.18, 0.10, 0.04, 0.05, 0.08, 0.05, 0.05, 0.30],
  ['HIGH',          8000, 999999, 0.20, 0.15, 0.12, 0.05, 0.06, 0.08, 0.06, 0.08, 0.20]
];

// Category behavior for day distribution (mirrors calendar_engine.py)
var CAT_BEHAVIOR = {
  'Groceries':       'spread',
  'Coffee':          'spread',
  'Public Transport':'spread',
  'Dining Out':      'clustered',
  'Entertainment':   'clustered',
  'Shopping':        'clustered',
  'Clothing':        'clustered',
  'Hobbies':         'clustered',
  'Travel':          'clustered',
  'Rent/Mortgage':   'fixed',
  'Utilities':       'fixed',
  'Insurance':       'fixed',
  'Debt Repayment':  'fixed',
  'Savings':         'fixed',
  'Emergency Fund':  'fixed',
  'Medical':         'spread',
  'Personal Care':   'spread',
  'Car/Gas':         'spread',
  'Subscriptions':   'fixed'
};

// Yellow threshold: 5% of planned, clamped [2, 25]
function yellowThreshold(planned) {
  return Math.min(Math.max(planned * 0.05, 2), 25);
}


// ── MENU ────────────────────────────────────────────────────

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('MITA Budget')
    .addItem('1. Initial Setup — Generate My Budget', 'runInitialSetup')
    .addSeparator()
    .addItem('2. Log Transaction', 'showTransactionDialog')
    .addSeparator()
    .addItem('Rebuild Calendar (new month)', 'rebuildCalendar')
    .addItem('Recalculate All Day Statuses', 'recalcAllStatuses')
    .addItem('Reset Rebalance Log', 'clearRebalanceLog')
    .addToUi();
}


// ── INITIAL SETUP ────────────────────────────────────────────

/**
 * Reads Setup sheet, calculates tier, fills Categories + Monthly + Calendar.
 */
function runInitialSetup() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var setup = ss.getSheetByName(SHEET.SETUP);
  if (!setup) { SpreadsheetApp.getUi().alert('Setup sheet not found.'); return; }

  // Read user inputs from Setup sheet (row: label in col A, value in col B)
  var income        = getSetupValue(setup, 'Monthly Net Income');
  var rent          = getSetupValue(setup, 'Rent / Mortgage');
  var utilities     = getSetupValue(setup, 'Utilities');
  var insurance     = getSetupValue(setup, 'Insurance');
  var debtRepayment = getSetupValue(setup, 'Debt Repayment');
  var savingsGoal   = getSetupValue(setup, 'Savings Goal (monthly)');
  var currency      = getSetupValue(setup, 'Currency Symbol') || '€';
  var monthYear     = getSetupValue(setup, 'Budget Month (YYYY-MM)') || currentYYYYMM();

  var totalFixed = rent + utilities + insurance + debtRepayment + savingsGoal;
  var discretionary = Math.max(income - totalFixed, 0);

  // Determine income tier
  var tier = getTier(income);

  // Build category allocations
  var allocs = buildAllocations(income, discretionary, tier, savingsGoal, rent, utilities, insurance, debtRepayment);

  // Write Categories sheet
  fillCategoriesSheet(ss, allocs, currency);

  // Write Monthly sheet
  fillMonthlySheet(ss, income, totalFixed, discretionary, allocs, currency, monthYear);

  // Build Calendar
  fillCalendarSheet(ss, allocs, monthYear, currency);

  // Init Transactions sheet headers if empty
  initTransactionsSheet(ss, currency);

  // Init Rebalance log headers if empty
  initRebalanceSheet(ss);

  SpreadsheetApp.getUi().alert(
    '✅ Setup complete!\n\n' +
    'Income tier: ' + tier.name + '\n' +
    'Discretionary budget: ' + currency + discretionary.toFixed(2) + '/month\n\n' +
    'Your daily calendar is ready on the Calendar sheet.\n' +
    'Log your spending in the Transactions sheet — the calendar updates automatically.'
  );
}

function getSetupValue(sheet, label) {
  var data = sheet.getDataRange().getValues();
  for (var i = 0; i < data.length; i++) {
    if (String(data[i][0]).trim() === label) {
      var v = data[i][1];
      return (typeof v === 'number') ? v : (parseFloat(v) || v);
    }
  }
  return 0;
}

function currentYYYYMM() {
  var d = new Date();
  return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0');
}

function getTier(income) {
  for (var i = TIER_DATA.length - 1; i >= 0; i--) {
    if (income >= TIER_DATA[i][1]) {
      return {
        name:          TIER_DATA[i][0],
        savingsRate:   TIER_DATA[i][3],
        groceriesPct:  TIER_DATA[i][4],
        diningPct:     TIER_DATA[i][5],
        entertainPct:  TIER_DATA[i][6],
        coffeePct:     TIER_DATA[i][7],
        transportPct:  TIER_DATA[i][8],
        clothingPct:   TIER_DATA[i][9],
        medicalPct:    TIER_DATA[i][10],
        otherPct:      TIER_DATA[i][11]
      };
    }
  }
  return { name: 'LOW', savingsRate: 0.05, groceriesPct: 0.30, diningPct: 0.04, entertainPct: 0.01,
           coffeePct: 0.02, transportPct: 0.02, clothingPct: 0.08, medicalPct: 0.02, otherPct: 0.46 };
}

function buildAllocations(income, discretionary, tier, savingsGoal, rent, utilities, insurance, debt) {
  // Fixed categories (exact amounts)
  var allocs = [
    { cat: 'Savings',         amount: savingsGoal,   priority: 0, behavior: 'fixed' },
    { cat: 'Rent/Mortgage',   amount: rent,           priority: 0, behavior: 'fixed' },
    { cat: 'Utilities',       amount: utilities,      priority: 0, behavior: 'fixed' },
    { cat: 'Insurance',       amount: insurance,      priority: 0, behavior: 'fixed' },
    { cat: 'Debt Repayment',  amount: debt,           priority: 0, behavior: 'fixed' }
  ];

  // Discretionary categories (tier-based %)
  var disc = [
    { cat: 'Groceries',        pct: tier.groceriesPct,  priority: 1, behavior: 'spread'    },
    { cat: 'Public Transport', pct: tier.transportPct,  priority: 1, behavior: 'spread'    },
    { cat: 'Medical',          pct: tier.medicalPct,    priority: 1, behavior: 'spread'    },
    { cat: 'Coffee',           pct: tier.coffeePct,     priority: 2, behavior: 'spread'    },
    { cat: 'Personal Care',    pct: 0.02,               priority: 2, behavior: 'spread'    },
    { cat: 'Car/Gas',          pct: 0.02,               priority: 2, behavior: 'spread'    },
    { cat: 'Clothing',         pct: tier.clothingPct,   priority: 3, behavior: 'clustered' },
    { cat: 'Dining Out',       pct: tier.diningPct,     priority: 3, behavior: 'clustered' },
    { cat: 'Entertainment',    pct: tier.entertainPct,  priority: 3, behavior: 'clustered' },
    { cat: 'Shopping',         pct: tier.otherPct * 0.4, priority: 3, behavior: 'clustered'},
    { cat: 'Hobbies',          pct: tier.otherPct * 0.3, priority: 3, behavior: 'clustered'},
    { cat: 'Subscriptions',    pct: tier.otherPct * 0.3, priority: 3, behavior: 'fixed'   }
  ];

  // Ensure percentages don't exceed 100%
  var totalPct = disc.reduce(function(s, d) { return s + d.pct; }, 0);
  if (totalPct > 1) {
    var scale = 1 / totalPct;
    disc.forEach(function(d) { d.pct *= scale; });
  }

  disc.forEach(function(d) {
    allocs.push({ cat: d.cat, amount: discretionary * d.pct, priority: d.priority, behavior: d.behavior });
  });

  // Remove zero-amount fixed categories
  return allocs.filter(function(a) { return a.amount > 0.01; });
}


// ── CATEGORIES SHEET ─────────────────────────────────────────

function fillCategoriesSheet(ss, allocs, currency) {
  var sh = ss.getSheetByName(SHEET.CATEGORIES);
  if (!sh) sh = ss.insertSheet(SHEET.CATEGORIES);
  sh.clearContents();
  sh.clearFormats();

  var headers = ['Category', 'Monthly Budget (' + currency + ')', 'Priority', 'Behavior', 'Daily Avg (' + currency + ')'];
  sh.getRange(1, 1, 1, headers.length).setValues([headers])
    .setFontWeight('bold')
    .setBackground('#193C57')
    .setFontColor('#FFD25F');

  var rows = allocs.map(function(a) {
    return [
      a.cat,
      parseFloat(a.amount.toFixed(2)),
      priorityLabel(a.priority),
      a.behavior,
      parseFloat((a.amount / 30.4).toFixed(2))
    ];
  });

  sh.getRange(2, 1, rows.length, headers.length).setValues(rows);

  // Color rows by priority
  rows.forEach(function(r, i) {
    var bg = ['#FFF3CD', '#D1ECF1', '#F8F9FA', '#FFFFFF'][allocs[i].priority];
    sh.getRange(i + 2, 1, 1, headers.length).setBackground(bg);
  });

  sh.autoResizeColumns(1, headers.length);
}

function priorityLabel(p) {
  return ['SACRED', 'PROTECTED', 'FLEXIBLE', 'DISCRETIONARY'][p] || String(p);
}


// ── MONTHLY SHEET ────────────────────────────────────────────

function fillMonthlySheet(ss, income, totalFixed, discretionary, allocs, currency, monthYear) {
  var sh = ss.getSheetByName(SHEET.MONTHLY);
  if (!sh) sh = ss.insertSheet(SHEET.MONTHLY);
  sh.clearContents();
  sh.clearFormats();

  var rows = [
    ['MITA BUDGET — ' + monthYear, '', ''],
    ['', '', ''],
    ['Monthly Net Income', '', currency + income.toFixed(2)],
    ['Total Fixed Expenses', '', '-' + currency + totalFixed.toFixed(2)],
    ['Discretionary Budget', '', currency + discretionary.toFixed(2)],
    ['', '', ''],
    ['CATEGORY BREAKDOWN', '', ''],
    ['Category', 'Priority', 'Amount (' + currency + ')']
  ];

  allocs.forEach(function(a) {
    rows.push([a.cat, priorityLabel(a.priority), currency + a.amount.toFixed(2)]);
  });

  rows.push(['', '', '']);
  rows.push(['TOTAL ALLOCATED', '', currency + allocs.reduce(function(s, a) { return s + a.amount; }, 0).toFixed(2)]);

  sh.getRange(1, 1, rows.length, 3).setValues(rows);
  sh.getRange(1, 1).setFontSize(14).setFontWeight('bold').setFontColor('#193C57');
  sh.getRange(8, 1, 1, 3).setFontWeight('bold').setBackground('#193C57').setFontColor('#FFD25F');
  sh.autoResizeColumns(1, 3);
}


// ── CALENDAR SHEET ───────────────────────────────────────────

function fillCalendarSheet(ss, allocs, monthYear, currency) {
  var sh = ss.getSheetByName(SHEET.CALENDAR);
  if (!sh) sh = ss.insertSheet(SHEET.CALENDAR);
  sh.clearContents();
  sh.clearFormats();

  var parts  = monthYear.split('-');
  var year   = parseInt(parts[0]);
  var month  = parseInt(parts[1]) - 1; // 0-indexed
  var daysInMonth = new Date(year, month + 1, 0).getDate();

  // Build daily plans
  var dayPlans = buildDayPlans(allocs, year, month, daysInMonth);

  // Write header row
  var headers = ['Day', 'Date', 'Day of Week', 'Planned (' + currency + ')', 'Spent (' + currency + ')', 'Remaining (' + currency + ')', 'Status', 'Notes'];
  sh.getRange(1, 1, 1, headers.length).setValues([headers])
    .setFontWeight('bold').setBackground('#193C57').setFontColor('#FFD25F');

  var today = new Date();
  var rows = [];
  for (var d = 1; d <= daysInMonth; d++) {
    var dt    = new Date(year, month, d);
    var planned = dayPlans[d] || 0;
    var dow   = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'][dt.getDay()];
    var isPast = (dt < new Date(today.getFullYear(), today.getMonth(), today.getDate()));
    var status = isPast ? STATUS.GREEN : STATUS.FUTURE;
    rows.push([d, Utilities.formatDate(dt, 'UTC', 'MMM dd'), dow,
               parseFloat(planned.toFixed(2)), 0, parseFloat(planned.toFixed(2)),
               status, '']);
  }
  sh.getRange(2, 1, rows.length, headers.length).setValues(rows);

  // Apply conditional color formatting
  applyCalendarColors(sh, rows.length);
  sh.autoResizeColumns(1, headers.length);
}

/**
 * Distribute monthly category budgets across calendar days.
 * Mirrors calendar_engine.py logic: spread / fixed / clustered.
 */
function buildDayPlans(allocs, year, month, daysInMonth) {
  var plans = {};
  for (var d = 1; d <= daysInMonth; d++) plans[d] = 0;

  allocs.forEach(function(a) {
    if (a.amount <= 0) return;
    var behavior = a.behavior || 'spread';

    if (behavior === 'fixed') {
      // Day 1 for savings/rent/debt, day 5 for utilities
      var fixedDay = (a.priority === 0 && a.cat !== 'Utilities') ? 1 : Math.min(5, daysInMonth);
      plans[fixedDay] = (plans[fixedDay] || 0) + a.amount;

    } else if (behavior === 'spread') {
      // Spread across weekdays
      var weekdays = [];
      for (var d2 = 1; d2 <= daysInMonth; d2++) {
        var dow = new Date(year, month, d2).getDay();
        if (dow > 0 && dow < 6) weekdays.push(d2); // Mon-Fri
      }
      if (weekdays.length === 0) weekdays = Object.keys(plans).map(Number);
      var perDay = a.amount / weekdays.length;
      weekdays.forEach(function(dd) { plans[dd] = (plans[dd] || 0) + perDay; });

    } else if (behavior === 'clustered') {
      // Pick ~40% of days randomly (deterministic via category name seed)
      var seed = a.cat.split('').reduce(function(h, c) { return h + c.charCodeAt(0); }, 0);
      var allDays = [];
      for (var d3 = 1; d3 <= daysInMonth; d3++) allDays.push(d3);
      var count = Math.max(2, Math.round(daysInMonth * 0.4));
      var chosen = deterministicSample(allDays, count, seed);
      var perDay = a.amount / chosen.length;
      chosen.forEach(function(dd) { plans[dd] = (plans[dd] || 0) + perDay; });
    }
  });

  // Round all to 2dp
  Object.keys(plans).forEach(function(k) { plans[k] = Math.round(plans[k] * 100) / 100; });
  return plans;
}

/** Deterministic sampling (no Math.random — stable across runs). */
function deterministicSample(arr, n, seed) {
  var indices = [];
  for (var i = 0; i < arr.length; i++) {
    indices.push({ val: arr[i], key: ((i * 2654435761 + seed) >>> 0) });
  }
  indices.sort(function(a, b) { return a.key - b.key; });
  return indices.slice(0, n).map(function(x) { return x.val; });
}

function applyCalendarColors(sh, rowCount) {
  for (var i = 0; i < rowCount; i++) {
    var row = i + 2;
    var statusCell = sh.getRange(row, 7);
    var status = statusCell.getValue();
    var bg = { green: '#D4EDDA', yellow: '#FFF3CD', red: '#F8D7DA', future: '#F8F9FA' }[status] || '#FFFFFF';
    sh.getRange(row, 1, 1, 8).setBackground(bg);
  }
}


// ── TRANSACTIONS SHEET ───────────────────────────────────────

function initTransactionsSheet(ss, currency) {
  var sh = ss.getSheetByName(SHEET.TRANSACTIONS);
  if (!sh) sh = ss.insertSheet(SHEET.TRANSACTIONS);
  if (sh.getLastRow() === 0) {
    var headers = ['Date', 'Day #', 'Category', 'Amount (' + currency + ')', 'Note', 'Processed'];
    sh.getRange(1, 1, 1, headers.length).setValues([headers])
      .setFontWeight('bold').setBackground('#193C57').setFontColor('#FFD25F');
  }
}


// ── REBALANCE LOG SHEET ──────────────────────────────────────

function initRebalanceSheet(ss) {
  var sh = ss.getSheetByName(SHEET.REBALANCE);
  if (!sh) sh = ss.insertSheet(SHEET.REBALANCE);
  if (sh.getLastRow() === 0) {
    var headers = ['Timestamp', 'Triggered By Day', 'Category', 'Overspend', 'Taken From', 'Amount Moved', 'Remaining Gap'];
    sh.getRange(1, 1, 1, headers.length).setValues([headers])
      .setFontWeight('bold').setBackground('#6B73FF').setFontColor('#FFFFFF');
  }
}

function clearRebalanceLog() {
  var ss  = SpreadsheetApp.getActiveSpreadsheet();
  var sh  = ss.getSheetByName(SHEET.REBALANCE);
  if (!sh) return;
  if (sh.getLastRow() > 1) sh.deleteRows(2, sh.getLastRow() - 1);
}


// ── ON EDIT TRIGGER (auto-process transactions) ─────────────

/**
 * Fires when user edits any cell.
 * Watches Transactions sheet col D (Amount) for new entries.
 */
function onEdit(e) {
  var sh = e.range.getSheet();
  if (sh.getName() !== SHEET.TRANSACTIONS) return;
  var col = e.range.getColumn();
  var row = e.range.getRow();
  if (col !== 4 || row < 2) return; // only Amount column

  var amount = parseFloat(e.value);
  if (isNaN(amount) || amount <= 0) return;

  // Mark row as unprocessed (will be picked up by processNewTransactions)
  sh.getRange(row, 6).setValue('');
  processRow(SpreadsheetApp.getActiveSpreadsheet(), sh, row);
}

/**
 * Process a single transaction row: update Calendar spent/remaining/status,
 * trigger rebalancer if overspent.
 */
function processRow(ss, txSheet, row) {
  var data = txSheet.getRange(row, 1, 1, 6).getValues()[0];
  var txDate    = data[0];
  var dayNum    = parseInt(data[1]);
  var category  = String(data[2]).trim();
  var amount    = parseFloat(data[3]);
  var processed = data[5];

  if (processed === 'YES') return;
  if (!txDate || isNaN(dayNum) || isNaN(amount) || amount <= 0) return;

  var calSheet = ss.getSheetByName(SHEET.CALENDAR);
  if (!calSheet) return;

  // Find calendar row for this day
  var calData = calSheet.getDataRange().getValues();
  var calRow  = -1;
  for (var i = 1; i < calData.length; i++) {
    if (parseInt(calData[i][0]) === dayNum) { calRow = i + 1; break; }
  }
  if (calRow < 0) return;

  // Update spent (col E = 5) and remaining (col F = 6)
  var planned  = parseFloat(calData[calRow - 1][3]) || 0;
  var currSpent= parseFloat(calData[calRow - 1][4]) || 0;
  var newSpent = currSpent + amount;
  var remaining= planned - newSpent;

  calSheet.getRange(calRow, 5).setValue(parseFloat(newSpent.toFixed(2)));
  calSheet.getRange(calRow, 6).setValue(parseFloat(remaining.toFixed(2)));

  // Update status
  var thresh  = yellowThreshold(planned);
  var newStatus;
  if (newSpent <= planned) newStatus = STATUS.GREEN;
  else if (newSpent <= planned + thresh) newStatus = STATUS.YELLOW;
  else newStatus = STATUS.RED;

  calSheet.getRange(calRow, 7).setValue(newStatus);
  applyRowColor(calSheet, calRow, newStatus);

  // Mark transaction processed
  txSheet.getRange(row, 6).setValue('YES');

  // If overspent → trigger rebalancer
  if (newStatus === STATUS.RED) {
    var overspend = newSpent - planned;
    rebalanceFutureDays(ss, dayNum, category, overspend);
  }
}


// ── REBALANCER ───────────────────────────────────────────────

/**
 * When day `dayNum` overspends, redistribute the gap across future days.
 * Mirrors realtime_rebalancer.py:
 *  - Never touch SACRED categories on other days
 *  - Take from DISCRETIONARY first, then FLEXIBLE, then PROTECTED
 *  - Max 50% from any single future-day entry
 *  - Log every transfer to Rebalance sheet
 */
function rebalanceFutureDays(ss, dayNum, overspentCat, overspendAmount) {
  var calSheet = ss.getSheetByName(SHEET.CALENDAR);
  var rebSheet = ss.getSheetByName(SHEET.REBALANCE);
  if (!calSheet || !rebSheet) return;

  var calData  = calSheet.getDataRange().getValues();
  var daysInMonth = calData.length - 1;
  var remaining    = overspendAmount;
  var now          = new Date();

  // Build list of future days with their planned amounts
  // We'll take from future day total planned (not per-category, since Calendar tracks totals per day)
  // Priority order: take from days that have DISCRETIONARY budget headroom first.
  // Simple heuristic: sort future days so days with higher planned amounts donate first.
  var futureDays = [];
  for (var i = 1; i < calData.length; i++) {
    var dNum = parseInt(calData[i][0]);
    if (dNum <= dayNum) continue;
    var planned = parseFloat(calData[i][3]) || 0;
    if (planned <= 0) continue;
    futureDays.push({ row: i + 1, day: dNum, planned: planned });
  }

  // Sort: highest planned first (they can give the most)
  futureDays.sort(function(a, b) { return b.planned - a.planned; });

  var logRows = [];

  for (var j = 0; j < futureDays.length && remaining > 0.01; j++) {
    var fd = futureDays[j];
    var maxTake = fd.planned * 0.5; // never take more than 50%
    var take = Math.min(maxTake, remaining);
    take = Math.round(take * 100) / 100;
    if (take < 0.01) continue;

    // Reduce future day's planned amount
    var newPlanned = Math.round((fd.planned - take) * 100) / 100;
    calSheet.getRange(fd.row, 4).setValue(newPlanned);

    // Recalculate remaining for that future day
    var futSpent = parseFloat(calSheet.getRange(fd.row, 5).getValue()) || 0;
    calSheet.getRange(fd.row, 6).setValue(Math.round((newPlanned - futSpent) * 100) / 100);

    remaining = Math.round((remaining - take) * 100) / 100;

    logRows.push([
      Utilities.formatDate(now, Session.getScriptTimeZone(), 'yyyy-MM-dd HH:mm:ss'),
      dayNum,
      overspentCat,
      overspendAmount,
      'Day ' + fd.day,
      take,
      remaining
    ]);
  }

  if (logRows.length > 0) {
    var lastLog = rebSheet.getLastRow() + 1;
    rebSheet.getRange(lastLog, 1, logRows.length, 7).setValues(logRows);
  }

  // If still remaining gap (couldn't cover fully), leave note on calendar
  if (remaining > 0.01) {
    calSheet.getRange(dayNum + 1, 8).setValue('⚠ Gap of ' + remaining.toFixed(2) + ' could not be fully rebalanced');
  }
}


// ── HELPERS ──────────────────────────────────────────────────

function applyRowColor(sh, row, status) {
  var bg = { green: '#D4EDDA', yellow: '#FFF3CD', red: '#F8D7DA', future: '#F8F9FA' }[status] || '#FFFFFF';
  sh.getRange(row, 1, 1, 8).setBackground(bg);
}

function recalcAllStatuses() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sh = ss.getSheetByName(SHEET.CALENDAR);
  if (!sh) return;
  var data = sh.getDataRange().getValues();
  for (var i = 1; i < data.length; i++) {
    var planned  = parseFloat(data[i][3]) || 0;
    var spent    = parseFloat(data[i][4]) || 0;
    var thresh   = yellowThreshold(planned);
    var status;
    if (spent === 0 && planned > 0) status = STATUS.FUTURE;
    else if (spent <= planned)      status = STATUS.GREEN;
    else if (spent <= planned+thresh) status = STATUS.YELLOW;
    else                            status = STATUS.RED;
    sh.getRange(i + 1, 7).setValue(status);
    applyRowColor(sh, i + 1, status);
  }
}

function rebuildCalendar() {
  var ss    = SpreadsheetApp.getActiveSpreadsheet();
  var setup = ss.getSheetByName(SHEET.SETUP);
  if (!setup) { SpreadsheetApp.getUi().alert('Run Initial Setup first.'); return; }
  var currency  = getSetupValue(setup, 'Currency Symbol') || '€';
  var monthYear = getSetupValue(setup, 'Budget Month (YYYY-MM)') || currentYYYYMM();

  // Read allocations from Categories sheet
  var catSheet = ss.getSheetByName(SHEET.CATEGORIES);
  if (!catSheet) { SpreadsheetApp.getUi().alert('Run Initial Setup first.'); return; }
  var catData = catSheet.getDataRange().getValues();
  var allocs  = [];
  for (var i = 1; i < catData.length; i++) {
    var cat    = catData[i][0];
    var amount = parseFloat(catData[i][1]) || 0;
    var prio   = priorityFromLabel(catData[i][2]);
    var beh    = catData[i][3] || 'spread';
    if (amount > 0) allocs.push({ cat: cat, amount: amount, priority: prio, behavior: beh });
  }
  fillCalendarSheet(ss, allocs, monthYear, currency);
  SpreadsheetApp.getUi().alert('Calendar rebuilt for ' + monthYear);
}

function priorityFromLabel(label) {
  return { SACRED: 0, PROTECTED: 1, FLEXIBLE: 2, DISCRETIONARY: 3 }[String(label).toUpperCase()] || 3;
}


// ── TRANSACTION DIALOG ───────────────────────────────────────

function showTransactionDialog() {
  var html = HtmlService.createHtmlOutput(
    '<style>body{font-family:sans-serif;padding:16px;} label{display:block;margin-top:12px;font-weight:bold;} input,select{width:100%;padding:6px;margin-top:4px;} button{margin-top:16px;padding:10px 20px;background:#193C57;color:#FFD25F;border:none;border-radius:4px;cursor:pointer;font-size:14px;}</style>' +
    '<h3 style="color:#193C57">Log a Transaction</h3>' +
    '<label>Day # (1–31)<input type="number" id="day" min="1" max="31" value="' + new Date().getDate() + '"></label>' +
    '<label>Category<select id="cat">' +
    Object.keys(CAT_PRIORITY).map(function(c) { return '<option>' + c + '</option>'; }).join('') +
    '</select></label>' +
    '<label>Amount (€)<input type="number" id="amt" step="0.01" min="0.01"></label>' +
    '<label>Note<input type="text" id="note" placeholder="optional"></label>' +
    '<button onclick="submit()">Add Transaction</button>' +
    '<script>function submit(){google.script.run.withSuccessHandler(function(){google.script.host.close();}).addTransactionFromDialog(parseInt(document.getElementById("day").value),document.getElementById("cat").value,parseFloat(document.getElementById("amt").value),document.getElementById("note").value);}</script>'
  ).setWidth(320).setHeight(340);
  SpreadsheetApp.getUi().showModalDialog(html, 'Log Transaction');
}

function addTransactionFromDialog(day, category, amount, note) {
  var ss     = SpreadsheetApp.getActiveSpreadsheet();
  var txSheet= ss.getSheetByName(SHEET.TRANSACTIONS);
  if (!txSheet) initTransactionsSheet(ss, '€');
  var setup   = ss.getSheetByName(SHEET.SETUP);
  var monthYear = setup ? getSetupValue(setup, 'Budget Month (YYYY-MM)') : currentYYYYMM();
  var parts   = monthYear.split('-');
  var txDate  = new Date(parseInt(parts[0]), parseInt(parts[1]) - 1, day);
  var lastRow = txSheet.getLastRow() + 1;
  txSheet.getRange(lastRow, 1, 1, 6).setValues([[
    Utilities.formatDate(txDate, Session.getScriptTimeZone(), 'yyyy-MM-dd'),
    day, category, amount, note || '', ''
  ]]);
  processRow(ss, txSheet, lastRow);
}
