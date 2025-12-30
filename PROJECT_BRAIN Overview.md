# 🧠 PROJECT OVERVIEW – “BYP Ops System”

This is a complete **modern replacement for your legacy FileMaker Tour system**, built using:

- **FastAPI** backend (`main.py`, `routes/`, `schemas/`, `models/`, etc.)
- **SQLite for dev** → **Postgres for production**
- Designed to **fully replace FileMaker**, **automate Trello**, and **streamline audio/video/art order workflows**
- Code lives under: `C:\BYP_Ops_System\backend`

---

## ✅ CORE MODULES

Each module corresponds to a table (past or present) in FileMaker, but with a cleaner, normalized structure.

### 1. `Orders`
- Core of the system — represents a single production request (Radio, Video, Art, Other)
- Fields: `order_id`, `created_by`, `status`, `tour_id`, `lineup_id`, `media_type`, `sp_number`, etc.
- Linked to: `Tours`, `Lineups`, `SP_Master`
- Art orders do **not** use SP#s. They use a **date-based number** (`MMDDYY`), and revisions use `-R1`, `-R2`, etc.

### 2. `Tours`
- One-to-many with Orders
- Fields: `tour_id`, `artist`, `tour_name`, `announce_date`, `on_sale_date`, asset checkboxes

### 3. `Lineups`
- Optional; used if a Tour has multiple city/venue/date combinations
- Imported as CSV or manually entered

### 4. `SP_Master` *(Planned)*
- Will store SP#s for all Radio/Video/Other orders
- Ensures uniqueness across all modules
- Art excluded

### 5. `Companies` *(Planned)*
- Shared company table for both Orders and Tours
- Replaces separate company fields

---

## 📜 RULES & BEHAVIOR

### 🚫 Development Rules
- **NEVER** modify a single line of code unless explicitly instructed
- **NO multi-step instructions** — one step at a time
- **NO assumptions** — ask if unsure
- Treat everything from earlier versions as canon unless replaced
- NEVER rename files once working (rule #159)
- Scripts must be delivered in **FULL, SINGLE BLOCKS**, no splitting, no canvas
- Every update must be **version controlled and precise**

---

### 🎯 SP Numbering Rules
- Only Radio, Video, Other get SP#s from `SP_Master`
- **Revisions** = new SP# with `revision_of: SP123456`
- Art uses date code: `MMDDYY`, and revision adds `-R#`

---

### 🧱 Trello Integration
- Trello cards mirror orders
- One card per asset version
- Card titles follow: `Artist - AssetType - OptionalDesc (SB)`
- Trello automation includes:
  - Card creation
  - Checklists named after date (e.g., `122523`, or `122523-R2`)
  - Revision handling
  - Attachments, folder handling, and Gmail draft prep for approvals

---

## 🎯 END GOAL

> A **fully automated backend system** that replaces FileMaker for all Tour-related asset requests, including Radio, Video, Art, and Other. It will:
- Generate and manage SP numbers
- Track orders, tours, lineups, revisions, approvals
- Automate Trello integration (cards, checklists, approvals)
- Trigger Google Drive and Gmail actions
- Work via FastAPI + frontend or GUI tools (e.g., TourOpsCC, Trello Grabber, ReportGenny, etc.)
- Be modular, maintainable, and **100% aligned to your file structure, logic, and snarky standards**

---

## 🧠 MEMORY RULES FOR ME

- I must **remember everything** you confirm as final
- I must **NEVER forget file locations, structure, rules**
- When the thread gets too long, we reset and rebuild `PROJECT_BRAIN.md` to avoid confusion