# ⚡ GridWise — Premium AI Energy Optimization Platform

> **BUP CSE Fest 2026 Problem Statement Specification Standard**  
> An enterprise PERN-stack (PostgreSQL · Express · React · Node.js) platform that transforms natural language operator instructions into mathematically optimal 24-hour energy dispatch schedules.

[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Neon_Serverless-00e599?logo=postgresql)](https://neon.tech)
[![React](https://img.shields.io/badge/React_18-Vite_8-61dafb?logo=react)](https://vitejs.dev)
[![Express](https://img.shields.io/badge/Node.js-Express-white?logo=node.js)](https://expressjs.com)
[![TailwindCSS](https://img.shields.io/badge/Tailwind_v4-Modern_SaaS_Dark-38bdf8?logo=tailwindcss)](https://tailwindcss.com)

---

## 🚀 Key Highlights & BUP CSE Fest Compliance

* **POST `/optimize-energy` Compliance:** Strictly implements the BUP specification with `scenario_id`, `operator_notes` (1–3 strings), 24 `hours` (`hour`, `demand_kwh`, `solar_kwh`, `tariff_bdt_per_kwh`), and `battery` (`capacity_kwh`, `initial_energy_kwh`, `minimum_energy_kwh`, `max_charge_kwh_per_hour`, `max_discharge_kwh_per_hour`).
* **Exact Directive Interpretation Schema:** Every note produces exactly one entry (`note_index`, `applies`, `directive_type`, `structured_adjustment`, `explanation`) mapped to the 6 exact BUP directives:
  1. `solar_reduction` (`hours`, `factor`)
  2. `minimum_battery_reserve` (`hours`, `minimum_energy_kwh`)
  3. `no_charge_window` (`hours`)
  4. `no_discharge_window` (`hours`)
  5. `max_grid_window` (`hours`, `max_grid_kwh`)
  6. `no_op` (`null`)
* **Mathematical Schedule Validation:** 13-point mathematical validator verifying the exact balance equation $\text{grid} + \text{solar\_used} + \text{discharge} = \text{demand} + \text{charge}$, battery capacity, reserve limits, rate limits, non-negative grid import ($\text{grid\_kwh} \ge 0$), directive adherence, and end-of-day battery neutrality ($\text{final\_energy} == \text{initial\_energy}$).
* **End-of-Day Battery Neutrality:** 2-pass optimizer algorithm that reconciles battery state-of-charge so the final hour's energy equals the day's initial energy while minimizing total grid expenditure ($\sum \text{grid\_kwh} \times \text{tariff\_bdt\_per\_kwh}$).
* **Start-Inclusive, End-Exclusive Time Semantics:** e.g., "2 PM to 4 PM" maps to hours `[14, 15]`.
* **Required Terminology:** Employs `peak_grid_kwh` throughout the engine and contract.
* **Deterministic Fallback Engine:** Gracefully translates directives and executes optimization even if LLM API keys are absent or network requests time out.
* **Live Energy Flow Matrix:** Animated real-time routing showing solar-to-load, grid import, and battery charge/discharge with an interactive 24-hour scrubber.
* **Neon PostgreSQL Persistence:** Persists energy scenarios, operator notes, and 24-hour optimization plans to Neon Serverless PostgreSQL with automatic migrations.

---

## 🗂 Monorepo Architecture

```
root/
├── client/                     # React + Vite frontend
│   └── src/
│       ├── api/                # API clients (energy, auth)
│       ├── features/
│       │   ├── dashboard/      # Overview with KPIs, Flow matrix, Tariff chart
│       │   ├── energy/         # Spreadsheet editor, Battery sliders, Result page
│       │   ├── scenarios/      # PostgreSQL scenario library & presets
│       │   ├── history/        # Past optimization audit log
│       │   ├── analytics/      # Aggregate trends & impact charts
│       │   ├── settings/       # Preferences & diagnostics
│       │   ├── auth/           # Login & Registration
│       │   └── admin/          # Admin Control Center (RBAC)
│       ├── shared/             # Layout, EnergyFlow, BatteryMeter, Modals
│       ├── store/              # Zustand stores (useEnergyStore, useAuthStore)
│       └── router/             # Centralized route configuration
├── server/                     # Node.js + Express backend
│   └── src/
│       ├── core/
│       │   ├── app.js          # Express app & diagnostics health check
│       │   ├── db.js           # Neon PostgreSQL connection pool (SSL-ready)
│       │   ├── router.js       # Auto-mounting feature route loader
│       │   ├── auth/           # JWT auth service & RBAC middleware
│       │   ├── llm/            # LLM service (OpenAI/Gemini + Zod guardrails)
│       │   └── optimizer/      # 2-Pass dispatch, Directives, Validation, Costs
│       ├── features/           # Auto-mounted modules (/optimize-energy, /scenarios, /history, /analytics, /auth)
│       └── scripts/migrate.js  # Ordered PostgreSQL migration runner
├── migrations/                 # 5 SQL migrations (scenarios, notes, plans, users, tables)
├── docker-compose.yml          # Full multi-container Docker deployment
├── CONTRACT.md                 # Complete API Contract Specification
└── README.md
```

---

## ⚡ Quick Start

### 1. Prerequisites
- Node.js >= 18
- PostgreSQL (or Neon serverless connection string)
- npm >= 9

### 2. Configure Environment

Create `.env` at the root (or copy from `.env.example`):
```bash
# Server
PORT=5000
NODE_ENV=development

# Database (PostgreSQL / Neon Serverless)
DATABASE_URL=postgresql://username:password@your-db-host.neon.tech/neondb?sslmode=require

# LLM Configuration (Optional — uses deterministic fallback engine if omitted)
LLM_API_KEY=your_openai_or_gemini_api_key_here
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini

# JWT Authentication
JWT_SECRET=your_jwt_secret_key_here
ADMIN_EMAIL=admin@gridwise.io
ADMIN_PASSWORD=your_admin_password_here
```

### 3. Run Database Migrations

Applies all 5 migrations in order to PostgreSQL:
```bash
npm run migrate
```

### 4. Run Development Servers

```bash
# Concurrently start API (:5000) and React Frontend (:5173)
npm run dev
```

| Service | URL |
|---|---|
| ⚡ Web Application | [http://localhost:5173](http://localhost:5173) |
| 📡 API Server | [http://localhost:5000](http://localhost:5000) |
| 🔍 Diagnostics Health | [http://localhost:5000/health](http://localhost:5000/health) |

---

## 🔐 Administrator Account Setup

GridWise automatically seeds an initial administrator account upon startup based on the credentials defined in your `.env` file:

* **Email:** Configured via `ADMIN_EMAIL` (e.g., `admin@gridwise.io`)
* **Password:** Configured via `ADMIN_PASSWORD`
* **Role:** `admin` (Unlocks the Admin Control Center)

---

## 🧪 Running Unit & Integration Tests

```bash
node server/test/optimizer.test.js
```
Runs comprehensive verification covering:
- Baseline energy & cost calculations
- BUP directive schemas and constraint translation
- Unconstrained optimization cost savings
- Hourly plan schema verification (`grid_kwh`, `solar_used_kwh`, `battery_action`, `battery_kwh`, `battery_energy_after_kwh`)
- Exact energy balance: $\text{grid} + \text{solar\_used} + \text{discharge} = \text{demand} + \text{charge}$
- End-of-day battery neutrality: $\text{final\_energy} == \text{initial\_energy}$
- Directives replayed and verified on schedule
- 13-point schedule mathematical validation

---

## 📄 License
MIT © 2026 GridWise Platform Team
