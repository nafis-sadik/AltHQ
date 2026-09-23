# AI Agent Instructions for Personal AI Agent Framework

## 1. Core Architectural Laws (The 3-Layer Rule & Vertical Slicing)
- **Vertical Slicing Mandate:** Every sprint or phase **must deliver a fully working vertical slice** touching all three layers simultaneously (`src/app`, `src/business`, and `src/core`). Never build an entire layer in isolation before moving to the next. Every feature increment must include its persistence, business logic, and UI routes together.
- **Layer 2 (Business Logic) is 100% Framework-Independent:** Never import Flask, FastAPI, SQLAlchemy, or web frameworks into `src/business (layer # 2)/`. It must communicate with storage solely through Layer 3 repository interfaces.
- **Layer 1 (Application):** Handles HTTP, routing, and UI views in `src/app (layer # 1)/`, delegating all execution flow and business logic to Layer 2.
- **Layer 3 (Persistence & Core):** Manages database connections, file handles, DTOs (`src/core (layer # 3)/dtos`), and repositories (`src/core (layer # 3)/repositories`) for SQLite, TinyDB, and other unmanaged resources.

## 2. Repository Preservation & Coding Style Rules
- **Preserve Existing Repositories:** The baseline repositories for SQLite, TinyDB, and storage are already fully implemented inside `src/core (layer # 3)/repositories/`. **Do not modify or rewrite them** unless an active bug is identified. Always reuse these existing repository implementations.
- **Style Consistency for New Repositories:** When creating new repositories or DTOs is strictly required, carefully inspect the existing codebase in `src/core (layer # 3)/` and match its exact coding style, naming conventions, structural patterns, and type hints.

## 3. Tech Stack & Implementation Guardrails
- **Frontend Stack:** Server-side rendered HTML templates styled with **Bootstrap 5** and interactive scripts powered by **jQuery**. No React, Vue, or Tailwind.
- **Database:** SQLite3 must always initialize with Write-Ahead Logging (`PRAGMA journal_mode=WAL;`) enabled to support background concurrency.

## 4. Sprint-Based Workflow
- We develop feature-wise using SRS Markdown files located in the `specs/` folder.
- When starting a task, read the corresponding spec file in `specs/` and adhere strictly to its boundaries. Do not write code for future phases prematurely.