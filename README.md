# Economy Analytics

> ## How to properly open this README
>
> `README.md` is a **Markdown file**. It is meant to be viewed as a formatted page, not just as raw text in Notepad.
>
> **If you are viewing this repository on GitHub:**  
> You do not need to download or open the README separately. GitHub automatically renders `README.md` as the formatted page shown underneath the repository files.
>
> **If you downloaded the repository to your computer:**  
> The easiest options are:
>
> 1. Open the project folder in **Visual Studio**.
> 2. Open `README.md`.
> 3. Use Visual Studio's Markdown preview if available so headings, code blocks, links, and formatting are displayed properly.
>
> You can also open `README.md` in **Visual Studio Code** and press:
>
> ```text
> Ctrl + Shift + V
> ```
>
> to open the formatted Markdown preview.
>
> Opening the file in Notepad is not wrong, but it will show the Markdown symbols such as `#`, `**`, and backticks instead of rendering them as headings, bold text, and code blocks.
>
> If you only want to read the instructions, the **GitHub page itself is the simplest and recommended way to view this README**.


A desktop analytics, visualization, and simulation tool for **UnbelievaBoat Discord economy data** exported into a Discord History Tracker `.dht` database.

The program reads UnbelievaBoat balance-change embeds from the database and turns them into easier-to-understand statistics about:

- how much money users gain and lose
- which games and commands affect the economy the most
- how active individual users are
- natural activity groups such as Very Casual, Casual, Regular, Active, and Very Active
- historical game averages inside each activity group
- how users may perform over a 30-day period
- how proposed UnbelievaBoat game-setting changes could affect players
- relationships and trends that can be explored with custom plots
- what the numbers actually mean in plain language

The current application also includes:

- a **Game Simulator**
- an **activity-group target optimizer**
- **individual user analysis**
- **24-hour and 30-day projections**
- a flexible **Plots** page with bar, line, scatter, and histogram charts
- direct **Copy Plot Image** support for pasting charts into Discord
- Discord-friendly **Copy Discord** buttons for tables
- copy buttons for explanation and simulator text
- **CSV export**
- **light/dark mode**
- automatic **username lookup** from the DHT database when available
- a packaged-EXE-friendly database locator

---

## Contents

- [What the program does](#what-the-program-does)
- [Requirements](#requirements)
- [Running the packaged EXE](#running-the-packaged-exe)
- [1. Download the project from GitHub](#1-download-the-project-from-github)
- [2. Install Python](#2-install-python)
- [3. Install Visual Studio](#3-install-visual-studio)
- [4. Get the Discord messages with Discord History Tracker](#4-get-the-discord-messages-with-discord-history-tracker)
- [5. Prepare the database](#5-prepare-the-database)
- [6. Open and run the source version](#6-open-and-run-the-source-version)
- [Using the program](#using-the-program)
- [Understanding each page](#understanding-each-page)
- [Activity Groups](#activity-groups)
- [Plots](#plots)
- [Copying data to Discord](#copying-data-to-discord)
- [Using the Game Simulator](#using-the-game-simulator)
- [Activity-group optimizer](#activity-group-optimizer)
- [How simulation scaling works](#how-simulation-scaling-works)
- [Important limitations](#important-limitations)
- [Troubleshooting](#troubleshooting)
- [Privacy](#privacy)

---

# What the program does

Economy Analytics reads a Discord History Tracker SQLite database and looks for UnbelievaBoat `Balance updated` embeds.

It automatically reads information such as:

- Discord user ID
- username, when the DHT database contains a usable user record
- Cash change
- Bank change
- total balance change
- reason for the change
- timestamp

It then groups related events together.

Examples:

- `roulette won` and `roulette bet` are treated as **Roulette**
- `slot-machine won` and `slot-machine lost` are treated as **Slot Machine**
- `higher-lower win` and `higher-lower bet` are treated as **Higher or Lower**
- `cockfight won` and `cockfight bet` are treated as **Cock Fight**
- chicken purchases can be counted as part of Cock Fight
- Animal Race bets, wins, animals, and provisions are handled as **Animal Race**
- purchase reasons can be grouped under **Buy**
- role income is grouped under **Role Income**

The program builds fast lookup indexes after loading the database so repeated filtering, table views, simulator runs, activity-group calculations, and optimizer checks do not need to rescan the entire database from scratch every time.

The goal is to make a large Discord economy history easier to inspect, compare, visualize, and balance without manually reading thousands of audit-log messages.

---

# Requirements

There are two ways to use Economy Analytics.

### If you have a packaged `.exe`

You only need:

- Windows
- `EconomyAnalytics.exe`
- your `.dht` database

Python and Visual Studio are **not required** just to run the packaged EXE.

### If you want to run or edit the Python source

You need:

- Windows
- Python 3
- Visual Studio with Python support, or another Python editor
- the project files from this GitHub repository
- your `.dht` database

The application itself uses the Python standard library only.

**You do not need to install extra Python packages with `pip`.**

The main libraries used by the program include Tkinter, SQLite, JSON, CSV, statistics, datetime, pathlib, and Windows APIs that are available through Python's standard library.

---

# Running the packaged EXE

If you received a release ZIP containing `EconomyAnalytics.exe`, extract the ZIP before opening the program.

Recommended folder layout:

```text
EconomyAnalytics/
├── EconomyAnalytics.exe
└── economy-stats.dht
```

Do **not** run the EXE directly from inside the ZIP. Windows may start it from a temporary location, which can prevent the program from finding a database that appears to be beside it inside the archive.

At startup the packaged app:

1. looks for `economy-stats.dht` beside `EconomyAnalytics.exe`
2. if that exact filename is missing but there is exactly one `.dht` file beside the EXE, it uses that file
3. otherwise it opens the normal **Choose Database** dialog

The packaged version is built as a windowed application, so a normal release should not open a separate Command Prompt window.

---

# 1. Download the project from GitHub

There are two easy ways to get the project.

## Option A: Download ZIP

This is the easiest method if you do not use Git.

1. Open this GitHub repository.
2. Click the green **Code** button.
3. Click **Download ZIP**.
4. Wait for the ZIP file to download.
5. Right-click the downloaded ZIP file.
6. Choose **Extract All**.
7. Open the extracted folder.

GitHub's official instructions for downloading a repository are available here:

https://docs.github.com/en/repositories/working-with-files/using-files/downloading-files-from-github

## Option B: Clone with Git

If you already have Git installed, you can clone the repository instead:

```bash
git clone <REPOSITORY-URL>
```

Then open the newly created folder.

If you are completely new to GitHub, **Download ZIP is perfectly fine**.

---

# 2. Install Python

The application needs Python to run.

## Download Python

1. Go to the official Python download page:

   https://www.python.org/downloads/windows/

2. Download a current **64-bit Python 3 release** for Windows.
3. Run the installer.

A modern Python 3 version is recommended. Python 3.11 or newer is a good choice.

## Important installation option

During installation, if the installer gives you an option similar to:

```text
Add Python to PATH
```

enable it.

Then continue with the normal installation.

## Check that Python works

After installation:

1. Press `Win + R`.
2. Type:

```text
cmd
```

3. Press Enter.
4. Run:

```bash
python --version
```

If that does not work, try:

```bash
py --version
```

You should see a Python 3 version.

Example:

```text
Python 3.14.7
```

If you see a Python version, Python is installed correctly.

---

# 3. Install Visual Studio

This guide uses **Visual Studio Community**, not Visual Studio Code.

Visual Studio Community is free for individual developers, students, open-source development, and many other non-enterprise uses.

## Download Visual Studio

Go to:

https://visualstudio.microsoft.com/

Download **Visual Studio Community**.

## Install Python support

1. Open the Visual Studio Installer.
2. Find the list of workloads.
3. Enable:

```text
Python development
```

4. Install Visual Studio.

Microsoft's official Python setup instructions are here:

https://learn.microsoft.com/en-us/visualstudio/python/installing-python-support-in-visual-studio

If Visual Studio is already installed:

1. Open Visual Studio.
2. Go to **Tools**.
3. Choose **Get Tools and Features**.
4. The Visual Studio Installer will open.
5. Enable **Python development**.
6. Apply the changes.

---

# 4. Get the Discord messages with Discord History Tracker

Economy Analytics does not connect directly to Discord.

First, use **Discord History Tracker (DHT)** to save the Discord messages into a local `.dht` SQLite database. Economy Analytics then reads that database.

For this project, you normally only need to save the channel or channels that contain the **UnbelievaBoat `Balance updated` embeds**.

Official Discord History Tracker website:

https://dht.chylex.com/

Official source code and releases:

https://github.com/chylex/Discord-History-Tracker

## Download Discord History Tracker

1. Open:

   https://dht.chylex.com/

2. Download the latest **Windows 64-bit** desktop version.
3. Extract the downloaded archive.
4. Open `DiscordHistoryTracker.exe`.

Use the official website or the official `chylex/Discord-History-Tracker` GitHub repository rather than downloading copies from random websites.

## Create or open the economy database

When Discord History Tracker opens, first check whether you already have an older economy database.

### If an older database already exists

Open the existing `.dht` database instead of creating a new one.

For example:

```text
economy-stats.dht
```

Using the old database is recommended because Discord History Tracker can continue adding newer messages to the same file. This lets you keep all previously downloaded history and only collect the messages that are missing.

### If no database exists yet

Create a **new database** and save it as:

```text
economy-stats.dht
```

You can save it directly inside the Economy Analytics project folder if you want.

For example:

```text
EconomyAnalytics/
│
├── economy-stats.dht
├── economy_analytics.py
└── README.md
```

Discord History Tracker saves messages into this database as it tracks them.

## Open the Discord channel you want to save

For the economy analyzer, go to the Discord channel containing UnbelievaBoat economy logs.

The messages should look similar to:

```text
Balance updated

User: @example
Amount: Cash: -300 | Bank: 0
Reason: animal-race bet
```

and:

```text
Balance updated

User: @example
Amount: Cash: +600 | Bank: 0
Reason: animal race won
```

The analyzer uses these balance-change embeds to determine who gained or lost money and why.

You do **not** need to download unrelated channels unless you also want those messages in the database.

## Recommended method: use the DHT browser userscript

Recent versions of Discord History Tracker include a browser userscript option. This avoids having to paste the full tracking script into the browser console.

The DHT userscript adds a **DHT** button to Discord's top bar.

The general process is:

1. Open Discord History Tracker.
2. Open its **Tracking** tab.
3. Use the option in DHT to install the browser userscript.
4. Open Discord in your web browser:

   https://discord.com/app

5. Open the server and the channel containing the UnbelievaBoat balance logs.
6. Click the **DHT** button added to Discord.
7. Discord History Tracker will ask for a **connection code**.
8. Copy the connection code from the Discord History Tracker desktop app.
9. Paste that connection code into the DHT prompt in Discord.
10. Start tracking the channel.

The connection code connects the browser userscript to the Discord History Tracker program running on your own computer.

**Do not enter or share your Discord account token.** The DHT connection code is not your Discord account token.

## Alternative method: Copy Tracking Script

Discord History Tracker also provides a **Copy Tracking Script** button in the **Tracking** tab.

This generates the tracking script that connects Discord to the desktop app.

If you use this method:

1. Open Discord in a supported browser.
2. Go to the channel you want to save.
3. Open Discord History Tracker.
4. Open the **Tracking** tab.
5. Click **Copy Tracking Script**.
6. Follow Discord History Tracker's instructions for running that script in Discord.
7. The first time it runs, DHT will show its tracking settings.

The userscript method above is generally easier for a new user because you do not need to repeatedly paste the full tracking script into developer tools.

## Let DHT automatically load the history

By default, Discord History Tracker can **automatically scroll upward through the channel** to load older messages.

This is the useful "auto-scroller" part.

You generally do not need to sit there manually scrolling through thousands of Discord messages.

Once tracking is active:

1. Keep Discord open on the channel being tracked.
2. Let DHT automatically scroll upward.
3. DHT reads the messages as they are loaded.
4. The desktop app saves them into `economy-stats.dht`.
5. Leave it running until it has reached as far back as you want.

By default, DHT can also stop or pause when it reaches a message that was already saved. This is useful when you update the same database later because it avoids downloading the same history unnecessarily.

## Tracking several economy-log channels

If your server stores UnbelievaBoat balance logs in more than one channel, track each relevant channel into the **same `economy-stats.dht` database**.

For example:

```text
#economy-logs
#old-economy-logs
#staff-economy-logs
```

Only include channels whose data you actually want Economy Analytics to analyze.

## Updating the database later

You do not need to start from scratch every time you want newer statistics.

To update your existing database:

1. Open Discord History Tracker.
2. Choose **Open Database** and select your existing `economy-stats.dht`.
3. Do **not** create a new database if you want to keep the history you already collected.
4. Open the relevant Discord log channel.
5. Connect DHT again.
6. Start tracking.
7. Let it collect the newer messages.
8. When it reaches messages already stored in the database, it can stop instead of reloading the entire channel.

Then reopen Economy Analytics or press:

```text
Reload
```

to analyze the updated database.

## When is the database ready?

Once the messages you want have been saved into the `.dht` database, you can use it with Economy Analytics.

It is a good idea to let Discord History Tracker finish writing before moving or copying the database file.

If you saved `economy-stats.dht` somewhere else, copy it into the same folder as the Economy Analytics Python file.

## Important privacy note

A Discord History Tracker database can contain:

- Discord user IDs
- usernames and message contents
- channel information
- embeds
- timestamps
- other server history

Treat the `.dht` file as private data.

**Do not upload `economy-stats.dht` to GitHub.**

Only archive messages that you are allowed to access, and follow the rules that apply to the server and data you are handling.

---

# 5. Prepare the database

The preferred database filename is:

```text
economy-stats.dht
```

For the source version, place it beside the main Python file.

For the packaged version, place it beside `EconomyAnalytics.exe`.

Example source folder:

```text
EconomyAnalytics/
├── economy-stats.dht
├── economy-stats.py
└── README.md
```

Example packaged folder:

```text
EconomyAnalytics/
├── EconomyAnalytics.exe
└── economy-stats.dht
```

The program uses the folder containing the Python script when running from source, and the folder containing the actual EXE when running as a PyInstaller build.

If `economy-stats.dht` is not found, the program also checks for another `.dht` file in the app folder. If exactly one is present, it uses that database automatically. Otherwise you can select a database manually with **Choose Database**.

## What kind of database is expected?

The `.dht` file is an SQLite database produced by Discord History Tracker.

The program expects a table called:

```text
message_embeds
```

It automatically searches that table for the JSON column containing Discord embed information.

The balance-change embeds need information similar to:

```text
User: <Discord user>
Amount: Cash: +29 | Bank: 0
Reason: chat money
```

plus a timestamp.

The program also performs a best-effort search of user-related DHT tables to map Discord IDs to usernames. Different DHT versions can store user information slightly differently, so username lookup is deliberately flexible.

If no username can be resolved for a user, the raw Discord user ID is shown instead.

## Important

Economy Analytics itself does **not** download Discord messages.

Use Discord History Tracker to create or update the `.dht` database, then open that database in Economy Analytics.

---

# 6. Open and run the source version

## Open the project in Visual Studio

1. Start Visual Studio.
2. Choose **Open a local folder** or use:

```text
File > Open > Folder
```

3. Select the folder containing the project.
4. Open the main `.py` file.
5. If Visual Studio asks for an interpreter, select your installed Python 3 interpreter.

You can also view interpreters through Visual Studio's **Python Environments** window.

## Run the program

With the main Python file open:

- press `F5` to run with debugging, or
- press `Ctrl + F5` to run without debugging

Depending on the Visual Studio setup, you may also need to right-click the main Python file and choose **Set as Startup File**.

## Run without Visual Studio

Open Command Prompt inside the project folder and run:

```bash
python economy-stats.py
```

If the source file has another name, replace `economy-stats.py` with the actual filename.

If `python` does not work but `py` does, use:

```bash
py economy-stats.py
```

---

# Using the program

When the application starts, it automatically tries to load a `.dht` database.

The preferred filename is:

```text
economy-stats.dht
```

When running from source, it looks beside the Python file.

When running as a packaged EXE, it looks beside `EconomyAnalytics.exe`.

If that exact file is missing but exactly one `.dht` file is present in the app folder, the program uses that file automatically. Otherwise it opens **Choose Database**.

If the database loads successfully, the top of the application shows information about the selected dataset and available date range.

The main interface is built around:

- global analysis filters
- searchable and sortable tables
- plain-English explanation cards
- natural activity groups
- custom plots
- the Game Simulator
- Discord-friendly copy tools

## Analysis filters

The filter area controls what data is included in the analysis.

### Exclude

The **Exclude** menu lets you remove specific categories from the analysis.

Examples include:

- Add Money
- Remove Money
- Buy
- Role Income
- individual games

You can select multiple categories.

### Chicken purchases

Chicken purchases can be treated as:

```text
Chicken -> cockfight
```

or:

```text
Chicken -> buy
```

Counting chickens as Cock Fight is useful when you want Cock Fight results to include the cost of replacing chickens.

### Time range

Available quick ranges include:

- All time
- Last 1 hour
- Last 6 hours
- Last 12 hours
- Last 24 hours
- Last 48 hours
- Last 7 days
- Last 14 days
- Last 30 days
- Custom

Quick ranges are based on the newest transaction in the database, not the current wall-clock time.

This means an older saved database can still be analyzed correctly.

### Custom dates

Supported examples include:

```text
2026-08-20 08:30
2026-08-20
20-08-2026 08:30
20-08-2026
```

Leaving one side blank makes that side unrestricted.

### Apply button

Changing filters does **not** immediately rerun the analysis.

After choosing filters, press:

```text
Apply
```

The status indicator shows when changes are still waiting to be applied.

---

# Understanding each page

The program contains several pages in the left sidebar.

Most pages contain a plain-English explanation generated from the actual numbers currently being shown.

Tables are designed to avoid vertical scrolling inside the table itself. Small result sets expand to show their rows, while larger result sets use pagination. Horizontal scrolling is still available when a table contains many columns.

---

## Overview

The Overview page gives the fastest summary of the entire selected period.

It shows information such as:

- when the selected period starts
- when it ends
- how long the period is
- number of balance changes
- number of active users
- estimated combined user activity
- overall balance change
- money added to users
- money removed from users
- average balance change per hour
- estimated result if the same pace continued for 30 days

The explanation underneath interprets these numbers for you.

For example, instead of only showing:

```text
Net economy change: -784,451
```

the program explains that users collectively ended the selected period about `784,451` poorer.

---

## Users

The Users page gives one row per user.

When the DHT database contains a resolvable username, the app shows the username instead of the raw Discord ID. If no username is available, it falls back to the user ID.

This page is useful for quickly comparing everyone without opening each user separately.

Important values include:

### Net Profit

How much the user's balance changed overall during the selected period.

Positive values mean the user became richer. Negative values mean the user became poorer.

### 30d Net

An estimate of what the user's result would look like over 30 days if the behavior seen in the selected period continued at the same average pace.

This is a projection, not a guarantee.

### Gross Earned

All positive balance changes added together.

### Gross Lost

All negative balance changes added together as a positive loss amount.

### Estimated Active Hours

An estimate of how much time the user spent actively using the economy.

Activity is estimated using 5-minute activity windows. Several transactions inside the same 5-minute block count as one active block instead of several separate periods of playtime.

### Activity %

How much of the selected period the user appears to have spent actively using the economy.

### Sessions

An estimate of separate periods of economy activity.

A new session starts when the gap from the previous activity is large enough to be treated as a separate period of use.

### Active Days

How many different days the user used the economy.

### Top Income Source

The source with the largest **positive net contribution** to that user.

### Double-click a user

Double-click a row in the Users table to open that person in **User Breakdown**.

---

## User Breakdown

This page lets you inspect one user in detail.

Choose a username from the selector and press:

```text
View user
```

If a username could not be resolved from the DHT database, the selector shows the raw Discord ID instead.

The page shows:

- whether the user gained or lost money overall
- estimated activity
- 30-day projection
- where their money came from
- where their money disappeared
- every individual transaction included in the analysis

This is useful when a user looks unusual in the Users table and you want to understand why.

---

## Income Sources

This page compares games and economy commands.

For each source you can see things such as:

- how much users gained
- how much users lost
- the final result
- how often the source was used
- how many different users used it

The explanation box interprets which sources are adding the most money and which are removing the most money.

---

## Hourly

The Hourly page groups the economy by clock hour.

Use it to see:

- which hours gave users the most money
- which hours removed the most money
- which hours were busiest
- how many users were active

This is useful for spotting short periods where something unusual happened.

---

## Daily

The Daily page gives the same idea as Hourly, but groups the data by day.

Use it to compare:

- good days for users
- bad days for users
- busy days
- quiet days

---

## User Hours

This page combines user and hour.

Each row represents one specific user's activity during one hour.

It is useful for finding cases such as:

- one user making a very large amount in a short period
- one user losing a large amount in one hour
- unusually intense periods of play

---

## Transactions

This page shows the individual balance changes used by the program.

It includes:

- timestamp
- username when available, otherwise user ID
- Cash change
- Bank change
- total change
- grouped reason
- original reason from the database

Use this page when you want to inspect the raw event behind a statistic.

---

# Searching and sorting tables

Most tables have a search box.

You can search for values such as:

- username
- user ID when shown
- game
- reason
- date
- numeric value

Click a table heading to sort by that column.

Large tables use pagination instead of an internal vertical scrollbar. Horizontal scrolling is available when the table is wider than the window.

---

# Copying data to Discord

Tables support normal row/cell copying and a Discord-friendly formatted copy mode.

You can:

- select a row and press `Ctrl + C`
- right-click and choose **Copy row**
- right-click a cell and choose **Copy cell**
- press **Copy Discord** to copy the current page as a compact monospace Discord table
- right-click a table and choose **Copy current page for Discord**

The Discord formatter:

- wraps the table in a Discord code block
- shortens long headings where useful
- aligns columns
- compacts large numbers
- tries to stay below Discord's normal message length
- reports when rows had to be omitted from the copied page

Explanation cards also include **Copy** buttons so their text can be pasted directly into Discord.

Simulator summaries and optimizer result text also have copy buttons.

On the **Plots** page, **Copy Plot Image** copies the rendered chart itself to the Windows clipboard so it can be pasted directly into Discord with `Ctrl + V`.

---

# Exporting data

Use the **Export** button in the top-right corner to export the currently relevant table as a CSV file.

CSV files can be opened in programs such as:

- Microsoft Excel
- Google Sheets
- LibreOffice Calc
- Python
- R

---

# Light and dark mode

Use the button in the top-right corner to switch between:

```text
Light mode
```

and:

```text
Dark mode
```

The application rebuilds its interface with the new theme while keeping the current analysis and simulator state.

---

# Activity Groups

The Activity Groups page groups users by **natural activity levels** rather than forcing exactly 20% of users into each group.

The available labels are:

- Very Casual
- Casual
- Regular
- Active
- Very Active

Depending on the data, groups can have very different sizes and a group can even be empty.

You can group users by:

- **Combined activity**
- **Estimated active hours**
- **Transactions**

Combined activity uses both estimated active time and transaction activity.

The main table shows group-level averages such as:

- members
- average active hours per day
- average transactions per day
- average active days per 30 days
- average 24-hour result
- average 30-day result

## Detailed activity-group view

Choose a group in the **Detailed group** selector, or double-click a group in the main table.

The detailed explanation summarizes what a typical member of that group looks like.

The **Historical game averages** table lets you compare the games used by that group.

Useful columns include:

- **Users Played**
- **Participation %**
- **Avg Plays / Player / Day**
- **Avg Bet**
- **Net / Play**
- **Avg 24h Net / Member**
- **Avg 30d Net / Member**

`Avg Plays / Player / Day` averages only across members who actually played that game.

The detailed page also contains a **Group members** table. Usernames are shown when they can be resolved from the DHT database, and double-clicking a member opens their full User Breakdown.

### Important distinction

The detailed activity-group game table is **descriptive history**.

It tells you what members of that group actually did in the selected database period.

Those historical game-play counts are **not** used to decide how frequently games are played inside the fixed-frequency Game Simulator.

---

# Plots

The Plots page lets you build charts from the data already calculated by the application.

Supported chart types include:

- **Bar**
- **Line**
- **Scatter**
- **Histogram**

You can choose:

- data source
- X value
- Y value
- optional second Y value when supported
- aggregation
- sorting
- maximum number of plotted points

Available sources can include:

- Users
- Activity Groups
- Activity Group Games
- Income Sources
- Hourly
- Daily
- User Hours
- Transactions
- Game Simulation

Useful examples include:

- active hours vs 30-day user result
- transactions per day vs 30-day result
- income-source net result
- hourly economy trend
- daily economy trend
- activity-group 30-day result
- game profitability by activity group
- current vs proposed simulator results

Scatter plots can also calculate a Pearson correlation value to describe the strength and direction of a linear relationship.

Correlation does **not** prove that one variable causes the other.

## Copy Plot Image

After creating a plot, press:

```text
Copy Plot Image
```

The app copies the rendered chart directly to the Windows clipboard.

You can then paste it directly into Discord, Paint, an image editor, or another application with:

```text
Ctrl + V
```

No extra plotting package is required. The charts are rendered by the application itself.

---

# Using the Game Simulator

The Game Simulator lets you test proposed economy changes without immediately changing the Discord server.

The simulator uses historical data for two main things:

1. estimating how much active economy time users have
2. estimating the economics and betting behavior of each game

It does **not** use each user's historical game popularity to decide how many times that user plays each game.

Instead, play frequency is controlled by the fixed **plays of each game per 5 active minutes** setting.

The simulator supports:

- current and proposed plays of **each game** per 5 active minutes
- game bet limits
- Blackjack deck count
- Cock Fight starting win chance
- Cock Fight maximum win chance
- chicken price
- Slot Machine symbol count
- Slot Machine multiplier
- individual-user simulation
- activity-group targets and optimization
- copy-paste UnbelievaBoat command generation

Games analyzed by the simulator include:

- Blackjack
- Cock Fight
- Roulette
- Russian Roulette
- Slot Machine
- Higher or Lower
- Animal Race

Animal Race is treated differently from normal bet-limit games because animal/provision purchases are not assumed to happen once per race. A reusable horse or other animal can participate in many races, so purchase costs are kept separate from the race-count multiplier.

---

## Current vs Proposed

Each configurable setting has a current value and a proposed value.

Example:

```text
Blackjack

Current Min: 75
Current Max: 750

Proposed Min: 75
Proposed Max: 500
```

This asks:

> What would the results look like if Blackjack kept the same minimum bet but used a lower maximum bet?

---

## Run Simulation

After changing simulator settings, press:

```text
Run Simulation
```

The simulator recalculates the current and proposed outcomes.

Changing a field does not automatically overwrite the previous simulation. This prevents partially edited settings from immediately replacing the last result.

---

# 24-hour simulation results

Simulation results are shown as a **typical 24-hour period**.

This makes different selected timeframes easier to compare.

For example:

If you select 48 hours of history, the program divides that activity down to approximately one day.

If you select 12 hours, it scales that activity up to approximately one day.

This means the simulator does not simply show the raw result from the selected period.

It answers a question closer to:

> If activity continued at the same average pace, what would a normal 24-hour day look like?

---

# Individual user simulation

The simulator also lets you inspect one user.

The user's historical data is used to estimate their active economy time.

The simulator then applies the same fixed play-frequency assumption used everywhere else: each included game is played the configured number of times per five active minutes.

You can inspect:

- estimated active time
- current game result
- proposed game result
- change between current and proposed settings
- game-by-game effects

Usernames are shown when they can be resolved from the DHT database.

Double-clicking a user in a simulator table opens their individual simulation details.

---

# How bet scaling works

The simulator does not assume everyone suddenly bets the same amount.

Instead, it looks at where each historical bet sits between the current minimum and maximum.

It then places that bet at approximately the same position inside the proposed range.

Example:

Current limits:

```text
100 to 500
```

A user bets:

```text
300
```

That bet is halfway between the minimum and maximum.

If the new range is:

```text
50 to 250
```

the simulator maps the same betting behavior to roughly:

```text
150
```

This is intended to preserve the user's relative betting style while testing a different allowed range.

---

# Games per 5 minutes

The simulator uses:

```text
Current plays of EACH game / 5 active min
```

and:

```text
Proposed plays of EACH game / 5 active min
```

This setting is intentionally **not** a total number of games shared between all game types.

If the value is:

```text
2
```

then for each five active minutes the simulator assumes:

- 2 Blackjack plays
- 2 Cock Fight plays
- 2 Roulette plays
- 2 Russian Roulette plays
- 2 Slot Machine plays
- 2 Higher or Lower plays
- 2 Animal Race plays

The approximate daily play count for each game is based on:

```text
active hours per day × 12 × plays of each game per 5 active minutes
```

This means activity groups differ mainly because they spend different amounts of time actively using the economy, not because the simulator copies the historical game preferences of each group.

---

# Slot Machine simulation

Slot Machine has additional settings:

- number of symbols
- multiplier

The win probability depends on the number of symbols.

The simulator uses those settings to estimate how the Slot Machine would behave under the proposed configuration.

For example, changing:

```text
2 symbols
4.1x
```

to:

```text
2 symbols
4.3x
```

keeps the same symbol count while increasing the payout when a user wins.

---

# Cock Fight simulation

Cock Fight supports:

- starting win chance
- maximum win chance
- chicken price
- bet limits

Chicken purchases can be included as part of Cock Fight so the analysis includes the cost of replacing chickens.

This is important because looking only at fight winnings can make Cock Fight appear more profitable than it really is if chicken costs are ignored.

---

# Blackjack decks

The program lets you record a proposed Blackjack deck-count change and generate the corresponding setting change.

However, changing the number of decks is **not treated as a precise mathematical change to Blackjack profit inside the simulator**.

The program does not pretend to know an exact new Blackjack expected value solely from changing the deck count.

Bet-limit and activity changes are still applied.

---

# Roulette, Russian Roulette and Higher or Lower

For these games, the program mainly uses:

- historical results
- changed bet ranges
- changed game frequency

Game-defined payout rules are not replaced with made-up custom payout settings.

---

# Copy-paste UnbelievaBoat commands

After running the simulator, the command section generates commands for the settings you changed.

**Only changed settings are included.**

For example, if the only changes are:

- Blackjack max: `750 -> 500`
- Roulette max: `300 -> 125`
- Higher or Lower min: `75 -> 25`

the command box will contain only the commands needed for those changes.

You can press:

```text
Copy Commands
```

and paste them into Discord.

If nothing changed, the program tells you that there are no commands to generate.

---

## Slot Machine commands

Slot Machine multipliers are attached to symbols.

If you change the Slot Machine symbol count or multiplier, enter the exact slot symbols in the **Slot symbols for commands** field.

The program needs the same number of symbols as the proposed symbol count before it can create a complete copy-paste command set.

---

# Activity-group optimizer

The Game Simulator includes an optimizer that can search for proposed settings intended to move selected activity groups toward chosen 30-day earnings targets.

You can set separate targets for multiple groups, such as:

```text
Very Casual: +5,000 / 30d
Regular: +12,000 / 30d
Very Active: +25,000 / 30d
```

The optimizer evaluates the same simulator assumptions used by the normal simulation rather than using historical game popularity as the play-volume model.

Settings can be locked so the optimizer is not allowed to change them.

Lockable values include:

- global play rate
- individual game minimum and maximum bets
- Slot Machine symbol count
- Slot Machine multiplier
- Cock Fight starting chance
- Cock Fight maximum chance
- chicken price

The optimizer also attempts to avoid making one configurable game overwhelmingly better than every other game.

Russian Roulette is intentionally excluded from the normal "make games broadly beneficial" balancing objective.

Blackjack deck count can be recorded and included in generated commands, but it is not automatically treated as a precisely optimizable expected-value parameter.

Optimizer output is still an estimate. Always compare the result with the normal simulator, review the generated settings, and use judgment before applying changes on Discord.

---

# 30-day projections

The Users page contains 30-day projections.

These are based on the selected timeframe.

Example:

If a user gained:

```text
10,000
```

during a 5-day selected period, continuing at exactly the same pace would correspond to approximately:

```text
60,000
```

over 30 days.

The projection assumes the selected period is representative.

It does **not** mean the user is guaranteed to gain that amount.

---

# Estimated user activity

The application cannot directly know how long someone was sitting at their computer.

Instead, it estimates economy activity from transactions.

The selected period is divided into 5-minute blocks.

If a user performs economy actions inside one of those blocks, that block is counted as active.

For example:

```text
12:00:15
12:01:40
12:03:10
```

may all count as the same approximately 5-minute activity block.

This prevents several rapid commands from being incorrectly treated as several separate periods of activity.

## Combined activity can exceed the selected period

Suppose the selected history covers:

```text
24 hours
```

and ten users each appear active for:

```text
2 hours
```

The combined estimated user activity would be:

```text
20 user-hours
```

If many users are active at the same time, combined activity can therefore be much larger than the amount of clock time covered by the dataset.

---

# Plain-English explanations

Most pages contain an explanation box.

These explanations are generated using the numbers currently shown on the page.

Explanation cards also include a **Copy** button so the interpretation can be pasted directly into Discord.

The application attempts to answer questions such as:

- Did users become richer or poorer?
- By how much?
- Which game affected balances the most?
- How often was a game played?
- Who was the most active user?
- Which day was the busiest?
- What would the proposed simulator settings mean for an average day?
- Which proposed game change has the largest effect?

The goal is to make the program useful even if you are not familiar with statistical terminology.

---

# Important limitations

The results should be treated as analysis and estimates, not guaranteed future outcomes.

## Historical behavior may change

The simulator assumes historical active-time estimates and game economics remain reasonably representative. Play frequency itself is controlled by the configured fixed plays-per-game rate rather than copying each user's historical game mix.

Real users may change their behavior after:

- bet limits change
- payouts change
- game difficulty changes
- prices change
- new features are added
- users gain or lose large amounts of money

## Short timeframes can be misleading

A one-hour sample can be heavily affected by luck.

A longer period usually gives a more stable picture of normal server activity.

For balancing decisions, compare several different time ranges rather than relying on a single short period.

## Random games are random

Historical wins and losses contain luck.

A user having an unusually profitable day does not mean they will continue winning at that rate.

## Activity is estimated

Estimated activity is based on transaction timestamps.

It is not an exact measurement of how long someone was online or looking at Discord.

## 30-day projections are extrapolations

They answer:

> What would happen if this exact average pace continued?

They do not predict changes in player count, behavior, popularity, or luck.

---

# Recommended workflow for balancing the economy

A simple workflow is:

1. Load your latest `economy-stats.dht`.
2. Start with a reasonably long timeframe.
3. Check **Overview** to see whether user balances are growing or shrinking.
4. Open **Income Sources** to see which systems are responsible.
5. Check **Users** to see whether a small group of users is driving the result.
6. Open suspicious users in **User Breakdown**.
7. Open **Game Simulator**.
8. Enter your current settings correctly.
9. Enter the settings you are considering.
10. Run the simulation.
11. Read the plain-English explanation.
12. Check the game-by-game results.
13. Check the individual-user results.
14. Try several possible configurations.
15. Copy only the final changed commands when you are satisfied.
16. After applying changes on Discord, collect more history and compare the new results later.

---

# Reloading the database

If you replace or update `economy-stats.dht` while the program is open, press:

```text
Reload
```

The program will read the database again.

---

# Database location

The application uses a relative database location.

### Source version

When running the `.py` file, the program looks beside the Python script.

### Packaged EXE

When running a PyInstaller build, the program uses the actual folder containing `EconomyAnalytics.exe`, not PyInstaller's temporary extraction directory.

The preferred filename is:

```text
economy-stats.dht
```

If that exact file does not exist but there is exactly one `.dht` file beside the app, the program uses that file automatically.

If it cannot choose a database unambiguously, it opens **Choose Database**.

This means you should not need to hard-code paths such as:

```text
C:\Users\YourName\Downloads\...
```

inside the source.

---

# Troubleshooting

## Error: database file not found

For the source version, use:

```text
Project Folder/
├── economy-stats.dht
├── economy-stats.py
└── README.md
```

For the packaged version, use:

```text
EconomyAnalytics/
├── EconomyAnalytics.exe
└── economy-stats.dht
```

If you received a ZIP, **extract it before running the EXE**.

Do not run the EXE directly from inside the compressed archive.

If `economy-stats.dht` is not present but exactly one other `.dht` file is beside the app, the current version can use that file automatically.

If there are several `.dht` files, use **Choose Database** and select the correct one.

---

## The program opens and immediately shows a database error

Possible causes:

- the `.dht` file is missing
- the wrong `.dht` file was copied into the folder
- the database does not contain `message_embeds`
- the file does not contain compatible UnbelievaBoat balance embeds
- the database is damaged

---

## Visual Studio cannot find Python

First check Command Prompt:

```bash
python --version
```

or:

```bash
py --version
```

If neither works, reinstall Python.

If Python works in Command Prompt but Visual Studio cannot see it:

1. Open Visual Studio.
2. Open the Python Environments window.
3. Check whether your installed Python interpreter appears.
4. Make sure the **Python development** workload is installed through Visual Studio Installer.

---

## Usernames are not showing

Username display is best-effort.

The program searches user-related tables in the DHT database and attempts to map Discord IDs to usernames.

If a particular username cannot be found, the app intentionally falls back to the raw Discord user ID.

Possible reasons include:

- the DHT database does not contain that user's record
- the DHT version stored user information differently
- the user record was not captured in the archived history
- duplicate historical usernames require the app to include an ID for disambiguation

The economy calculations still work when only the ID is available.

---

## `tkinter` cannot be imported

A normal official Windows Python installation normally includes Tkinter.

If you installed a minimal or unusual Python distribution, install the standard Windows build from:

https://www.python.org/downloads/windows/

---

## Nothing happens when I change a filter

This is intentional.

Press:

```text
Apply
```

The program waits for you to apply the filter changes manually.

---

## Simulator results did not change

Check that:

1. you changed a **Proposed** value rather than only a Current value
2. you pressed **Run Simulation**
3. there is historical data for that game in the selected timeframe
4. the game was not excluded by the main filters

---

## No simulator commands appear

The command box only shows settings that are different between Current and Proposed.

If everything is unchanged, there is nothing to copy.

For Slot Machine changes, also make sure the required slot symbols were entered.

---

## The numbers look extreme

Try selecting a longer timeframe.

Very short periods can exaggerate:

- lucky streaks
- losing streaks
- one unusually active player
- one large purchase
- one admin transaction

Also check whether categories such as `add money`, `remove money`, or purchases should be excluded from the particular analysis you are trying to perform.

---

# Privacy

A `.dht` database may contain far more than the balance numbers shown in Economy Analytics.

It can contain:

- Discord user IDs
- usernames
- message contents
- channel information
- embeds
- timestamps
- other saved server history

Treat the database as private data.

It is strongly recommended that you **do not upload your real `.dht` database to GitHub**.

Add this to `.gitignore`:

```gitignore
*.dht
*.dht_downloads
__pycache__/
*.pyc
.vs/
```

That prevents normal Git workflows from accidentally adding the main DHT database, DHT companion download folders, Python cache files, and Visual Studio workspace files.

If your repository is public, inspect the files before every upload or commit.

The source code, README, icon, and packaged EXE can be shared separately from your private database.

---

# Updating the project from GitHub

If you originally used **Download ZIP**:

1. Open the GitHub repository again.
2. Click **Code**.
3. Click **Download ZIP**.
4. Extract the new version.
5. Copy your own `economy-stats.dht` into the new project folder.

Do not overwrite your database unless you intentionally want to replace it.

If you cloned the repository using Git, you can normally update it with:

```bash
git pull
```

from inside the repository folder.

---

# Quick setup summary

## If you received a packaged release

1. Download the Economy Analytics ZIP.
2. Extract the ZIP.
3. Put your `.dht` database beside `EconomyAnalytics.exe`.
4. Prefer the name `economy-stats.dht`.
5. Run `EconomyAnalytics.exe`.
6. If the app cannot choose the correct database automatically, select it with **Choose Database**.
7. Choose your timeframe.
8. Press **Apply**.
9. Explore Overview, Users, Activity Groups, Plots, and the other analysis pages.
10. Use Game Simulator before changing Discord economy settings.

## If you want to run or edit the source

1. Download and install Python.
2. Download and install Visual Studio Community.
3. Enable the **Python development** workload.
4. Download this repository using **Code > Download ZIP**, or clone it with Git.
5. Extract/open the repository.
6. Download Discord History Tracker from `https://dht.chylex.com/`.
7. Open an existing `.dht` database if you already have one, otherwise create one.
8. Track the channel containing the UnbelievaBoat `Balance updated` logs.
9. Let DHT collect the history you need.
10. Put the `.dht` file beside the Python source, or select it manually in the app.
11. Open the project folder in Visual Studio.
12. Run the main Python file.
13. Choose the analysis timeframe.
14. Press **Apply**.
15. Use **Activity Groups** for natural user-group comparisons.
16. Use **Plots** for visual comparisons and relationships.
17. Use **Game Simulator** and the activity-group optimizer to test balancing changes.
18. Copy Discord tables, explanation text, simulator commands, or plot images as needed.

---

# Disclaimer

This project is an independent analytics tool.

It is not affiliated with, endorsed by, or maintained by Discord, UnbelievaBoat, or Discord History Tracker.

Simulation, optimizer, activity, correlation, and 30-day results are estimates based on historical data and the assumptions implemented by the program.
