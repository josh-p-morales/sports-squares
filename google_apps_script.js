/**
 * ==============================================================================
 * College Basketball Sports Squares - Google Apps Script Webhook
 * ==============================================================================
 * 
 * SETUP INSTRUCTIONS (Takes ~1 minute, ZERO Google Cloud required):
 * 1. Open your Google Spreadsheet:
 *    https://docs.google.com/spreadsheets/d/1oRC1NXID8JvBRqE5WUcjJWMNtv7AN5iCpEKQESLS6vo/edit
 * 2. In the top menu, click: Extensions > Apps Script
 * 3. Delete any default code in Code.gs, and paste THIS ENTIRE FILE into it.
 * 4. Click the "Save" (disk) icon.
 * 5. Click "Deploy" (top right) > "New deployment" (or "Manage deployments" -> Edit -> New version).
 * 6. Click the gear icon next to "Select type" and choose "Web app".
 * 7. Fill in:
 *    - Description: Sports Squares Sync & Game Board
 *    - Execute as: Me (<your email>)
 *    - Who has access: Anyone
 * 8. Click "Deploy".
 *    (Google will ask for authorization: Click "Advanced" -> "Go to (unsafe)" -> "Allow").
 * 9. Copy the "Web app URL" (starts with https://script.google.com/macros/s/.../exec).
 * 10. Paste it into your .env file:
 *     GOOGLE_WEBHOOK_URL=https://script.google.com/macros/s/YOUR_URL_HERE/exec
 * ==============================================================================
 */

const GAMES_LOG_TAB = "Games Log";
const SQUARES_TRACKER_TAB = "Squares Tracker";
const GAME_BOARD_TAB = "Game Board";
const PAYOUTS_TAB = "Payouts";

const GAMES_LOG_HEADERS = [
  "Game ID", "Date", "Time", "Status", "Round / Region",
  "Away Team", "Away 1H/Q1", "Away 2H/Q2", "Away Q3", "Away Q4", "Away OT", "Away Total",
  "Home Team", "Home 1H/Q1", "Home 2H/Q2", "Home Q3", "Home Q4", "Home OT", "Home Total",
  "Final Square (Away-Home)", "Winning Cell", "Last Updated (UTC)"
];

const SQUARES_TRACKER_HEADERS = [
  "Game ID", "Matchup", "Round / Region", "Status",
  "Away Final Score", "Home Final Score", "Away Digit", "Home Digit",
  "Winning Square Key", "Winning Cell", "Winner (Player)", "Last Updated (UTC)"
];

/**
 * Automatically adds a custom menu to Google Sheets upon opening.
 */
function onOpen() {
  try {
    SpreadsheetApp.getUi()
      .createMenu("🏀 Sports Squares")
      .addItem("Setup Game Board (if missing)", "setupGameBoard")
      .addItem("Setup Payouts Sheet (if missing)", "setupPayouts")
      // .addItem("Regenerate Game Board (New Random Digits)", "regenerateGameBoard")
      .addToUi();
  } catch (e) {
    // onOpen might run in restricted context in some triggers
  }
}

/**
 * Health check endpoint: GET request to verify the Web App is running.
 */
function doGet(e) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const boardSheet = ss.getSheetByName(GAME_BOARD_TAB) || ss.getSheetByName("Game Board");

  return ContentService.createTextOutput(JSON.stringify({
    status: "ok",
    message: "Sports Squares Webhook is online and ready!",
    spreadsheetTitle: ss.getName(),
    gameBoardExists: !!boardSheet
  })).setMimeType(ContentService.MimeType.JSON);
}

/**
 * Main webhook endpoint: receives game scores, board creation requests, and updates sheets.
 */
function doPost(e) {
  try {
    const rawData = e.postData.contents;
    const payload = JSON.parse(rawData);
    const ss = SpreadsheetApp.getActiveSpreadsheet();

    // 1. Handle explicit Game Board Creation Action
    if (payload.action === "create_board") {
      const boardResult = createGameBoard(ss, payload.homeDigits, payload.awayDigits, !!payload.force);
      return ContentService.createTextOutput(JSON.stringify({
        status: "success",
        boardResult: boardResult,
        timestamp: new Date().toISOString()
      })).setMimeType(ContentService.MimeType.JSON);
    }

    // 1b. Handle explicit Payouts Creation Action
    if (payload.action === "create_payouts") {
      const payoutsResult = createPayoutsSheet(ss, !!payload.force);
      return ContentService.createTextOutput(JSON.stringify({
        status: "success",
        payoutsResult: payoutsResult,
        timestamp: new Date().toISOString()
      })).setMimeType(ContentService.MimeType.JSON);
    }

    // 2. Automatically ensure Game Board & Payouts exist if they don't already
    ensureGameBoardExists(ss);

    // 3. Process Games Log and Squares Tracker
    const gamesTab = getOrCreateSheet(ss, GAMES_LOG_TAB, GAMES_LOG_HEADERS, "#1a365d");
    const squaresTab = getOrCreateSheet(ss, SQUARES_TRACKER_TAB, SQUARES_TRACKER_HEADERS, "#1c4532");

    let gamesUpdated = 0;
    let squaresUpdated = 0;

    if (payload.games && Array.isArray(payload.games)) {
      gamesUpdated = updateGamesLog(gamesTab, payload.games);
    }

    if (payload.squares && Array.isArray(payload.squares)) {
      squaresUpdated = updateSquaresTracker(squaresTab, payload.squares);
    }

    return ContentService.createTextOutput(JSON.stringify({
      status: "success",
      gamesUpdated: gamesUpdated,
      squaresUpdated: squaresUpdated,
      timestamp: new Date().toISOString()
    })).setMimeType(ContentService.MimeType.JSON);

  } catch (error) {
    return ContentService.createTextOutput(JSON.stringify({
      status: "error",
      message: error.toString()
    })).setMimeType(ContentService.MimeType.JSON);
  }
}

function getUserInput(round) {
  const ui = SpreadsheetApp.getUi();
  const response = ui.prompt(
    'User Input Required',           // Dialog Title
    "Provide dollar amount for " + round + " (e.g., 20): ",       // Dialog Message / Prompt
    ui.ButtonSet.OK_CANCEL           // Button options (OK and Cancel)
  );
  const clickedButton = response.getSelectedButton();

  if (clickedButton === ui.Button.OK) {
    const userInput = response.getResponseText();
    return userInput;
  } else if (clickedButton === ui.Button.CANCEL) {
    ui.alert("Cancelled", "You cancelled the request.", ui.ButtonSet.OK);
    return '0';
  } else {
    ui.alert("Closed", "You closed the window.", ui.ButtonSet.OK);
    return '0';
  }
}

/**
 * Generates an array of unique random digits between 0 and 9 (Fisher-Yates shuffle).
 */
function getRandomUniqueDigits() {
  const digits = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9];
  /*
  for (let i = digits.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    const temp = digits[i];
    digits[i] = digits[j];
    digits[j] = temp;
  }
  */
  return digits;
}

/**
 * Checks if the "game board" tab exists, and if not, creates it.
 */
function ensureGameBoardExists(ss) {
  let sheet = ss.getSheetByName(GAME_BOARD_TAB) || ss.getSheetByName("Game Board");
  if (!sheet) {
    createGameBoard(ss, null, null, false);
  }
  createPayoutsSheet(ss, false);
  return { status: "exists", message: "Game board and payouts verified." };
}

/**
 * Creates or configures the "game board" tab matching the sports squares grid layout:
 * - "HOME TEAM" merged header above 10 columns
 * - "AWAY TEAM" vertically merged header to the left of 10 rows
 * - Solid black corner cell
 * - 0-9 unique random numbers for Away Team & Home Team
 * - 10x10 squares grid with alternating grey-blue shading and crisp borders
 */
function createGameBoard(ss, homeDigits, awayDigits, force) {
  let sheet = ss.getSheetByName(GAME_BOARD_TAB);
  if (!sheet) {
    sheet = ss.getSheetByName("Game Board");
  }

  if (sheet && !force) {
    return {
      status: "exists",
      message: "Sheet '" + sheet.getName() + "' already exists. Preserving existing board."
    };
  }

  if (!sheet) {
    sheet = ss.insertSheet(GAME_BOARD_TAB);
  } else {
    sheet.clear();
  }

  const rounds = ["1st Rnd", "2nd Rnd", "Sweet 16", "Elite 8", "Final 4", "Championship", "Buy In"];
  const dollarAmounts = [];
  rounds.forEach(round => {
    const amount = getUserInput(round);
    dollarAmounts.push(amount);
  });

  // 1. Prepare digits (unique and random 0-9)
  if (!homeDigits || !Array.isArray(homeDigits) || homeDigits.length !== 10) {
    homeDigits = getRandomUniqueDigits();
  }
  if (!awayDigits || !Array.isArray(awayDigits) || awayDigits.length !== 10) {
    awayDigits = getRandomUniqueDigits();
  }

  // Ensure minimum grid bounds
  if (sheet.getMaxRows() < 15) {
    sheet.insertRowsAfter(sheet.getMaxRows(), 15 - sheet.getMaxRows());
  }
  if (sheet.getMaxColumns() < 15) {
    sheet.insertColumnsAfter(sheet.getMaxColumns(), 15 - sheet.getMaxColumns());
  }

  // --- 2. HOME TEAM HEADER (Row 1, Columns C:L) ---
  const homeHeaderRange = sheet.getRange("C7:L7");
  homeHeaderRange.merge();
  homeHeaderRange.setValue("HOME TEAM");
  homeHeaderRange.setFontWeight("bold");
  homeHeaderRange.setFontSize(24);
  homeHeaderRange.setHorizontalAlignment("center");
  homeHeaderRange.setVerticalAlignment("middle");

  // --- 3. AWAY TEAM HEADER (Column A, Rows 3:12) ---
  const awayHeaderRange = sheet.getRange("A9:A18");
  awayHeaderRange.merge();
  awayHeaderRange.setValue("AWAY TEAM");
  awayHeaderRange.setFontWeight("bold");
  awayHeaderRange.setFontSize(24);
  awayHeaderRange.setHorizontalAlignment("center");
  awayHeaderRange.setVerticalAlignment("middle");
  try {
    awayHeaderRange.setTextRotation(90); // Rotates text vertically upward (90 degrees)
  } catch (e) {
    // In case environment restricts rotation
  }

  // --- 4. CORNER CELL (Row 2, Column B) ---
  const cornerCell = sheet.getRange("B8");
  cornerCell.setBackground("#000000");

  // --- 5. HOME TEAM DIGITS (Row 2, Columns C:L) ---
  const homeDigitsRange = sheet.getRange(8, 3, 1, 10);
  homeDigitsRange.setValues([homeDigits]);
  homeDigitsRange.setFontWeight("bold");
  homeDigitsRange.setFontSize(18);
  homeDigitsRange.setHorizontalAlignment("center");
  homeDigitsRange.setVerticalAlignment("middle");
  homeDigitsRange.setBackground("#D9E1F2"); // Soft light blue / periwinkle

  // --- 6. AWAY TEAM DIGITS (Column B, Rows 3:12) ---
  const awayValues = awayDigits.map(d => [d]);
  const awayDigitsRange = sheet.getRange(9, 2, 10, 1);
  awayDigitsRange.setValues(awayValues);
  awayDigitsRange.setFontWeight("bold");
  awayDigitsRange.setFontSize(18);
  awayDigitsRange.setHorizontalAlignment("center");
  awayDigitsRange.setVerticalAlignment("middle");
  awayDigitsRange.setBackground("#D9E1F2"); // Soft light blue / periwinkle

  // --- 7. INTERIOR 10x10 SQUARES GRID (Rows 3:12, Columns C:L) ---
  // Alternating row colors matching screenshot
  // Row 3 (1st grid row): darker grey-blue (#B4C6E7)
  // Row 4 (2nd grid row): lighter tint (#EDF2F8)
  for (let r = 9; r <= 18; r++) {
    const rowRange = sheet.getRange(r, 3, 1, 10);
    const bgColor = (r % 2 === 1) ? "#B4C6E7" : "#EDF2F8";
    rowRange.setBackground(bgColor);
    rowRange.setHorizontalAlignment("center");
    rowRange.setVerticalAlignment("middle");
    rowRange.setFontSize(12);
  }

  // --- 8. CELL BORDERS ---
  // Solid borders around entire grid structure (B2:L12)
  const fullGrid = sheet.getRange("B8:L18");
  fullGrid.setBorder(true, true, true, true, true, true, "#000000", SpreadsheetApp.BorderStyle.SOLID);

  // --- 9. ROW HEIGHTS & COLUMN WIDTHS ---
  sheet.setColumnWidth(1, 65); // Column A: AWAY TEAM label
  sheet.setColumnWidth(2, 55); // Column B: Away digits
  for (let c = 3; c <= 12; c++) {
    sheet.setColumnWidth(c, 100); // Columns C-L: 10 grid columns
  }

  sheet.setRowHeight(7, 65); // Row 1: HOME TEAM title
  sheet.setRowHeight(8, 55); // Row 2: Home digits
  for (let r = 9; r <= 18; r++) {
    sheet.setRowHeight(r, 100); // Rows 3-12: Squares grid rows
  }

  // --- 10. PAYOUT & BUYIN AMOUNTS
  const roundsRange = sheet.getRange(3, 4, 1, 7)
  roundsRange.setValues([rounds]);
  roundsRange.setFontWeight("bold");
  roundsRange.setFontSize(14);
  roundsRange.setHorizontalAlignment("center");
  roundsRange.setVerticalAlignment("middle");
  roundsRange.setBackground("rgba(219, 186, 0, 1)"); //Gold

  const payoutsRange = sheet.getRange(4, 4, 1, 7)
  payoutsRange.setValues([dollarAmounts]);
  payoutsRange.setFontWeight("bold");
  payoutsRange.setFontSize(14);
  payoutsRange.setHorizontalAlignment("center");
  payoutsRange.setVerticalAlignment("middle");
  payoutsRange.setNumberFormat("$#,##0.00;$(#,##0.00);$0.00");
  payoutsRange.setBackground("rgba(219, 186, 0, 1)"); //Gold

  // Automatically ensure Payouts sheet exists (only created if one does not already exist)
  createPayoutsSheet(ss, false);

  return {
    status: "created",
    message: "Game board created successfully!",
    homeDigits: homeDigits,
    awayDigits: awayDigits
  };
}

/**
 * Standalone runner for the script editor or menu.
 */
function setupGameBoard() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const res = createGameBoard(ss, null, null, false);
  try {
    SpreadsheetApp.getActiveSpreadsheet().toast(res.message, "Game Board", 5);
  } catch (e) { }
  return res;
}

/**
 * Regenerates game board with new randomized digits.
 */
function regenerateGameBoard() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const res = createGameBoard(ss, null, null, true);
  try {
    SpreadsheetApp.getActiveSpreadsheet().toast("Game board regenerated with new random digits!", "Game Board", 5);
  } catch (e) { }
  return res;
}

/**
 * Helper to get or initialize a sheet with styled headers.
 */
function getOrCreateSheet(ss, name, headers, headerColor) {
  let sheet = ss.getSheetByName(name);
  if (!sheet) {
    sheet = ss.insertSheet(name);
  }

  if (sheet.getLastRow() === 0) {
    sheet.appendRow(headers);
    const headerRange = sheet.getRange(1, 1, 1, headers.length);
    headerRange.setBackground(headerColor);
    headerRange.setFontColor("#FFFFFF");
    headerRange.setFontWeight("bold");
    headerRange.setHorizontalAlignment("center");
    sheet.setFrozenRows(1);
  } else {
    const lastCol = sheet.getLastColumn();
    const existingHeaders = sheet.getRange(1, 1, 1, Math.max(lastCol, 1)).getValues()[0];
    if (existingHeaders.length !== headers.length) {
      sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
      const headerRange = sheet.getRange(1, 1, 1, headers.length);
      headerRange.setBackground(headerColor);
      headerRange.setFontColor("#FFFFFF");
      headerRange.setFontWeight("bold");
      headerRange.setHorizontalAlignment("center");
    }
  }
  return sheet;
}

/**
 * Upserts games in the Games Log tab by matching Game ID (Column A).
 */
function updateGamesLog(sheet, games) {
  if (games.length === 0) return 0;

  const data = sheet.getDataRange().getValues();
  const idToRow = {};
  for (let i = 1; i < data.length; i++) {
    const id = String(data[i][0]).trim();
    if (id) {
      idToRow[id] = i + 1; // 1-indexed row number
    }
  }

  let count = 0;
  for (let g of games) {
    const gid = String(g[0]).trim();
    if (idToRow[gid]) {
      const rowNum = idToRow[gid];
      sheet.getRange(rowNum, 1, 1, g.length).setValues([g]);
    } else {
      sheet.appendRow(g);
      idToRow[gid] = sheet.getLastRow();
    }
    count++;
  }
  return count;
}

/**
 * Calculates the winning cell coordinate on the Game Board (e.g. A0-H0 -> C9, A0-H9 -> L9, A9-H0 -> C18).
 * Checks the 'Game Board' tab layout dynamically, falling back to standard grid mapping (Home 0-9 -> C-L, Away 0-9 -> 9-18).
 */
function getWinningCell(ss, awayDigit, homeDigit) {
  const colLetters = ["C", "D", "E", "F", "G", "H", "I", "J", "K", "L"];
  const aNum = Number(awayDigit);
  const hNum = Number(homeDigit);

  if (ss) {
    const boardSheet = ss.getSheetByName(GAME_BOARD_TAB) || ss.getSheetByName("Game Board") || ss.getSheetByName("game board");
    if (boardSheet) {
      try {
        // Row 8 contains Home digits across columns C to L (cols 3 to 12)
        const homeRowValues = boardSheet.getRange(8, 3, 1, 10).getValues()[0];
        const hIdx = homeRowValues.indexOf(hNum);

        // Column B (col 2) contains Away digits across rows 9 to 18
        const awayColValues = boardSheet.getRange(9, 2, 10, 1).getValues().map(r => r[0]);
        const aIdx = awayColValues.indexOf(aNum);

        if (hIdx !== -1 && aIdx !== -1) {
          return colLetters[hIdx] + (9 + aIdx);
        }
      } catch (e) {}
    }
  }

  // Standard grid layout formula (Home 0-9 => C-L, Away 0-9 => 9-18)
  const col = colLetters[hNum % 10];
  const row = 9 + (aNum % 10);
  return col + row;
}

/**
 * Upserts squares events by matching Game ID (Column A).
 */
function updateSquaresTracker(sheet, squares) {
  if (squares.length === 0) return 0;

  const ss = sheet.getParent();
  const data = sheet.getDataRange().getValues();
  const idToRow = {};
  for (let i = 1; i < data.length; i++) {
    const gid = String(data[i][0]).trim();
    if (gid) {
      idToRow[gid] = i + 1; // 1-indexed row number
    }
  }

  let count = 0;
  for (let sq of squares) {
    const gid = String(sq[0]).trim();
    
    // Ensure winning cell and winner formula are present (target length 12)
    if (sq.length === 10) {
      const awayDig = sq[6];
      const homeDig = sq[7];
      const winCell = getWinningCell(ss, awayDig, homeDig);
      const winnerFormula = '=IFERROR(INDIRECT("\'Game Board\'!" & J' + (idToRow[gid] || (sheet.getLastRow() + 1)) + '), "")';
      // Insert winCell and winnerFormula before timestamp
      sq.splice(9, 0, winCell, winnerFormula);
    } else if (sq.length === 11) {
      const winCell = sq[9];
      const winnerFormula = '=IFERROR(INDIRECT("\'Game Board\'!' + winCell + '"), "")';
      sq.splice(10, 0, winnerFormula);
    }

    if (idToRow[gid]) {
      const rowNum = idToRow[gid];
      sheet.getRange(rowNum, 1, 1, sq.length).setValues([sq]);
    } else {
      sheet.appendRow(sq);
      idToRow[gid] = sheet.getLastRow();
    }
    count++;
  }
  return count;
}

/**
 * Creates or configures the "Payouts" sheet mimicking the provided layout:
 * - Creates only if one does not already exist (unless forced)
 * - Room for 100 unique players (Rows 3 to 102)
 * - Column A: 'People playing' deduplicated and sorted dynamically from 'Game Board' C9:L18
 * - Column B: '# of squares' counting occurrences on 'Game Board'
 * - Column C: 'Board Cells' displaying in which cells on 'Game Board' player exists (e.g. C9, L9, C18)
 * - Columns D-I: Round payouts (1st Rnd, 2nd Rnd, Sweet 16, Elite 8, Final 4, FINALS)
 * - Column J: 'Total Won' summing winnings across rounds (SUM(D:I))
 * - Banner in Row 1: "Payouts" with Gold background #F6CE47
 * - Soft pink #FCE4D6 default background for round cells, conditional green #70AD47 for wins (>0)
 * - Bold Total Won formatted as $#,##0
 */
function createPayoutsSheet(ss, force) {
  let sheet = ss.getSheetByName(PAYOUTS_TAB);
  if (!sheet) {
    sheet = ss.getSheetByName("Payouts");
  }

  if (sheet && !force) {
    return {
      status: "exists",
      message: "Sheet '" + sheet.getName() + "' already exists. Preserving existing sheet."
    };
  }

  if (!sheet) {
    sheet = ss.insertSheet(PAYOUTS_TAB);
  } else {
    sheet.clear();
    sheet.clearConditionalFormatRules();
  }

  // Ensure minimum dimensions (105 rows x 12 columns)
  if (sheet.getMaxRows() < 105) {
    sheet.insertRowsAfter(sheet.getMaxRows(), 105 - sheet.getMaxRows());
  }
  if (sheet.getMaxColumns() < 12) {
    sheet.insertColumnsAfter(sheet.getMaxColumns(), 12 - sheet.getMaxColumns());
  }

  // Freeze top 2 rows (Banner and Headers)
  sheet.setFrozenRows(2);

  // --- 1. BANNER (Row 1, Columns A:J) ---
  const bannerRange = sheet.getRange("A1:J1");
  bannerRange.merge();
  bannerRange.setValue("Payouts");
  bannerRange.setFontWeight("bold");
  bannerRange.setFontSize(26);
  bannerRange.setHorizontalAlignment("center");
  bannerRange.setVerticalAlignment("middle");
  bannerRange.setBackground("#F6CE47"); // Gold fill matching screenshot
  sheet.setRowHeight(1, 55);

  // --- 2. HEADERS (Row 2, Columns A:J) ---
  const headers = [
    "People playing",
    "# of squares",
    "Board Cells",
    "1st Rnd",
    "2nd Rnd",
    "Sweet 16",
    "Elite 8",
    "Final 4",
    "FINALS",
    "Total Won"
  ];
  const headerRange = sheet.getRange(2, 1, 1, 10);
  headerRange.setValues([headers]);
  headerRange.setFontWeight("bold");
  headerRange.setFontSize(11);
  headerRange.setHorizontalAlignment("center");
  headerRange.setVerticalAlignment("middle");
  headerRange.setWrap(true);
  headerRange.setBackground("#FFFFFF");
  sheet.setRowHeight(2, 35);

  // Set column widths matching screenshot proportions
  sheet.setColumnWidth(1, 160); // A: People playing
  sheet.setColumnWidth(2, 85);  // B: # of squares
  sheet.setColumnWidth(3, 130); // C: Board Cells
  sheet.setColumnWidth(4, 75);  // D: 1st Rnd
  sheet.setColumnWidth(5, 75);  // E: 2nd Rnd
  sheet.setColumnWidth(6, 80);  // F: Sweet 16
  sheet.setColumnWidth(7, 75);  // G: Elite 8
  sheet.setColumnWidth(8, 75);  // H: Final 4
  sheet.setColumnWidth(9, 75);  // I: FINALS
  sheet.setColumnWidth(10, 100); // J: Total Won

  // --- 3. DYNAMIC PLAYER LIST (Cell A3) ---
  // Pulls unique non-empty player names from 'Game Board' C9:L18 and sorts them
  sheet.getRange("A3").setFormula("=IFERROR(SORT(UNIQUE(TOCOL('Game Board'!$C$9:$L$18, 1))), \"\")");

  // --- 4. POPULATE FORMULAS FOR 100 PLAYERS (Rows 3 to 102) ---
  const bColFormulas = [];
  const cColFormulas = [];
  const roundsFormulas = [];
  const totalFormulas = [];

  for (let r = 3; r <= 102; r++) {
    sheet.setRowHeight(r, 26);

    // Col B: Count number of times each player appears on Game Board
    bColFormulas.push([`=IF(A${r}="", "", COUNTIF('Game Board'!$C$9:$L$18, A${r}))`]);

    // Col C: List cell coordinates on Game Board where player exists
    cColFormulas.push([`=IF(A${r}="", "", TEXTJOIN(", ", TRUE, ARRAYFORMULA(IF(TRIM('Game Board'!$C$9:$L$18)=TRIM(A${r}), ADDRESS(ROW('Game Board'!$C$9:$L$18), COLUMN('Game Board'!$C$9:$L$18), 4), ""))))`]);

    // Cols D to I: Round payouts calculated from Squares Tracker and Game Board round payout amounts
    const f1st = `=IF(A${r}="", "", IF(COUNTIFS('Squares Tracker'!$K$2:$K$100, A${r}, 'Squares Tracker'!$C$2:$C$100, "*1st*") + COUNTIFS('Squares Tracker'!$K$2:$K$100, A${r}, 'Squares Tracker'!$C$2:$C$100, "*First*") > 0, (COUNTIFS('Squares Tracker'!$K$2:$K$100, A${r}, 'Squares Tracker'!$C$2:$C$100, "*1st*") + COUNTIFS('Squares Tracker'!$K$2:$K$100, A${r}, 'Squares Tracker'!$C$2:$C$100, "*First*")) * 'Game Board'!$D$4, ""))`;
    const f2nd = `=IF(A${r}="", "", IF(COUNTIFS('Squares Tracker'!$K$2:$K$100, A${r}, 'Squares Tracker'!$C$2:$C$100, "*2nd*") + COUNTIFS('Squares Tracker'!$K$2:$K$100, A${r}, 'Squares Tracker'!$C$2:$C$100, "*Second*") > 0, (COUNTIFS('Squares Tracker'!$K$2:$K$100, A${r}, 'Squares Tracker'!$C$2:$C$100, "*2nd*") + COUNTIFS('Squares Tracker'!$K$2:$K$100, A${r}, 'Squares Tracker'!$C$2:$C$100, "*Second*")) * 'Game Board'!$E$4, ""))`;
    const fSweet16 = `=IF(A${r}="", "", IF(COUNTIFS('Squares Tracker'!$K$2:$K$100, A${r}, 'Squares Tracker'!$C$2:$C$100, "*Sweet 16*") + COUNTIFS('Squares Tracker'!$K$2:$K$100, A${r}, 'Squares Tracker'!$C$2:$C$100, "*Sweet Sixteen*") > 0, (COUNTIFS('Squares Tracker'!$K$2:$K$100, A${r}, 'Squares Tracker'!$C$2:$C$100, "*Sweet 16*") + COUNTIFS('Squares Tracker'!$K$2:$K$100, A${r}, 'Squares Tracker'!$C$2:$C$100, "*Sweet Sixteen*")) * 'Game Board'!$F$4, ""))`;
    const fElite8 = `=IF(A${r}="", "", IF(COUNTIFS('Squares Tracker'!$K$2:$K$100, A${r}, 'Squares Tracker'!$C$2:$C$100, "*Elite 8*") + COUNTIFS('Squares Tracker'!$K$2:$K$100, A${r}, 'Squares Tracker'!$C$2:$C$100, "*Elite Eight*") > 0, (COUNTIFS('Squares Tracker'!$K$2:$K$100, A${r}, 'Squares Tracker'!$C$2:$C$100, "*Elite 8*") + COUNTIFS('Squares Tracker'!$K$2:$K$100, A${r}, 'Squares Tracker'!$C$2:$C$100, "*Elite Eight*")) * 'Game Board'!$G$4, ""))`;
    const fFinal4 = `=IF(A${r}="", "", IF(COUNTIFS('Squares Tracker'!$K$2:$K$100, A${r}, 'Squares Tracker'!$C$2:$C$100, "*Final 4*") + COUNTIFS('Squares Tracker'!$K$2:$K$100, A${r}, 'Squares Tracker'!$C$2:$C$100, "*Final Four*") > 0, (COUNTIFS('Squares Tracker'!$K$2:$K$100, A${r}, 'Squares Tracker'!$C$2:$C$100, "*Final 4*") + COUNTIFS('Squares Tracker'!$K$2:$K$100, A${r}, 'Squares Tracker'!$C$2:$C$100, "*Final Four*")) * 'Game Board'!$H$4, ""))`;
    const fFinals = `=IF(A${r}="", "", IF(COUNTIFS('Squares Tracker'!$K$2:$K$100, A${r}, 'Squares Tracker'!$C$2:$C$100, "*Final*") + COUNTIFS('Squares Tracker'!$K$2:$K$100, A${r}, 'Squares Tracker'!$C$2:$C$100, "*Championship*") - COUNTIFS('Squares Tracker'!$K$2:$K$100, A${r}, 'Squares Tracker'!$C$2:$C$100, "*Final 4*") - COUNTIFS('Squares Tracker'!$K$2:$K$100, A${r}, 'Squares Tracker'!$C$2:$C$100, "*Final Four*") > 0, (COUNTIFS('Squares Tracker'!$K$2:$K$100, A${r}, 'Squares Tracker'!$C$2:$C$100, "*Final*") + COUNTIFS('Squares Tracker'!$K$2:$K$100, A${r}, 'Squares Tracker'!$C$2:$C$100, "*Championship*") - COUNTIFS('Squares Tracker'!$K$2:$K$100, A${r}, 'Squares Tracker'!$C$2:$C$100, "*Final 4*") - COUNTIFS('Squares Tracker'!$K$2:$K$100, A${r}, 'Squares Tracker'!$C$2:$C$100, "*Final Four*")) * 'Game Board'!$I$4, ""))`;

    roundsFormulas.push([f1st, f2nd, fSweet16, fElite8, fFinal4, fFinals]);

    // Col J: Total Won
    totalFormulas.push([`=IF(A${r}="", "", IF(SUM(D${r}:I${r})>0, SUM(D${r}:I${r}), ""))`]);
  }

  // Set formulas in bulk
  sheet.getRange(3, 2, 100, 1).setFormulas(bColFormulas);
  sheet.getRange(3, 3, 100, 1).setFormulas(cColFormulas);
  sheet.getRange(3, 4, 100, 6).setFormulas(roundsFormulas);
  sheet.getRange(3, 10, 100, 1).setFormulas(totalFormulas);

  // --- 5. STYLING & CELL FORMATTING ---
  // Column A: Soft periwinkle/light blue fill
  const colARange = sheet.getRange(3, 1, 100, 1);
  colARange.setBackground("#EBF1F5");
  colARange.setFontSize(11);
  colARange.setHorizontalAlignment("left");
  colARange.setVerticalAlignment("middle");

  // Column B: Centered square count
  const colBRange = sheet.getRange(3, 2, 100, 1);
  colBRange.setHorizontalAlignment("center");
  colBRange.setVerticalAlignment("middle");
  colBRange.setFontSize(11);

  // Column C: Centered Board Cells
  const colCRange = sheet.getRange(3, 3, 100, 1);
  colCRange.setHorizontalAlignment("center");
  colCRange.setVerticalAlignment("middle");
  colCRange.setFontSize(10);
  colCRange.setWrap(true);

  // Columns D-I: Round Payouts with soft pink background
  const roundsRange = sheet.getRange(3, 4, 100, 6);
  roundsRange.setNumberFormat("$#,##0");
  roundsRange.setHorizontalAlignment("center");
  roundsRange.setVerticalAlignment("middle");
  roundsRange.setFontSize(11);
  roundsRange.setBackground("#FCE4D6"); // Soft pastel pink default

  // Column J: Total Won (Bold, large font, $#,##0)
  const totalRange = sheet.getRange(3, 10, 100, 1);
  totalRange.setNumberFormat("$#,##0");
  totalRange.setFontWeight("bold");
  totalRange.setFontSize(13);
  totalRange.setHorizontalAlignment("center");
  totalRange.setVerticalAlignment("middle");

  // --- 6. CONDITIONAL FORMATTING (Green when won > 0) ---
  const greenRule = SpreadsheetApp.newConditionalFormatRule()
    .whenNumberGreaterThan(0)
    .setBackground("#70AD47") // Vibrant green matching screenshot
    .setFontColor("#000000")
    .setRanges([roundsRange])
    .build();

  sheet.setConditionalFormatRules([greenRule]);

  // --- 7. CRISP BORDERS ---
  const entireTable = sheet.getRange(1, 1, 102, 10);
  entireTable.setBorder(true, true, true, true, true, true, "#000000", SpreadsheetApp.BorderStyle.SOLID);

  return {
    status: "created",
    message: "Payouts sheet created successfully with room for 100 unique players!"
  };
}

/**
 * Standalone runner for Payouts setup from menu or script editor.
 */
function setupPayouts() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const res = createPayoutsSheet(ss, false);
  try {
    SpreadsheetApp.getActiveSpreadsheet().toast(res.message, "Payouts", 5);
  } catch (e) { }
  return res;
}

