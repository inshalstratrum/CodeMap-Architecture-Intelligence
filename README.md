# CodeMap — Semantic Architecture & Visual Intelligence

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![React 19](https://img.shields.io/badge/react-19.3.0-61dafb.svg)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/typescript-6.0+-3178c6.svg)](https://www.typescriptlang.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**CodeMap** is a visual architecture mapping and codebase intelligence platform designed for developers, non-programmers, and vibe-coders alike. It scans any project folder, parses real multi-language dependencies, generates interactive Mermaid architecture diagrams, and provides a dual-interface experience: a lightweight Python desktop GUI and a web-based React visualizer studio.

---

## 🌟 Key Features

### 1. Dual Interface Experience
- **Python Desktop GUI (`Tkinter`)**: Standalone, lightweight desktop interface built with pure Python. Features an interactive dependency graph canvas, zoom/pan controls, search filters, and an AI code explanation assistant.
- **Web Studio (`React 19 + Vite`)**: Modern web UI powered by `@xyflow/react`, Tailwind CSS, and TanStack Table. Renders interactive node-link network graphs, file hierarchy trees, and metrics tables in your browser.

### 2. Multi-Language AST Code Analysis
- Extracts real cross-file dependencies and imports across **Python**, **JavaScript**, **TypeScript**, **JSON**, **HTML**, **CSS**, and **Markdown**.
- Computes structural metrics: incoming/outgoing dependencies, export definitions, external third-party libraries, and file roles.

### 3. Visual Diagram Studio & Vault
- Automatically generates beginner-friendly Mermaid diagrams:
  - **🏗 System Architecture** (`flowchart TD`)
  - **🔄 Logic & Data Flow** (`flowchart LR`)
  - **⏱ Sequence & Interactions** (`sequenceDiagram`)
  - **📊 State & Lifecycle** (`stateDiagram-v2`)
  - **🌳 Dense Hierarchical Tree** (`flowchart TD`)
- Includes a permanent **Visuals Vault** that caches generated diagrams and plain-English architectural analogies.

### 4. Obsidian Vault Integration
- Exports your entire codebase structure as a network of bidirectionally linked markdown notes directly into an Obsidian vault.

### 5. Zero Required Dependencies for Core
- The core scanning and diagramming engine uses **only the Python standard library**. No pip packages are required to run the core analysis!

---

## 🚀 Quick Start

### Option A: Python Desktop Studio (Tkinter)

1. **Clone the repository:**
   ```bash
   git clone https://github.com/inshalstratrum/CodeMap-Architecture-Intelligence.git
   cd CodeMap-Architecture-Intelligence
   ```

2. **Launch the Desktop Application:**
   * **Windows:** Double-click `Launch_Tkinter_GUI.bat` or `Run CodeMap.bat`.
   * **Command line:**
     ```bash
     python codemap_app.py
     ```

3. **Analyze a Codebase:**
   - Enter or paste any folder path into the top bar.
   - Click **Scan**.
   - Explore the generated node tree, inspect file roles, and generate architecture diagrams.

---

### Option B: React Web Studio

1. **Install web dependencies:**
   ```bash
   cd visualizer-ui
   pnpm install
   # or: npm install
   ```

2. **Start the Web Visualizer:**
   * **Windows:** Double-click `Launch_React_Visualizer.bat` or `Run Visualizer.bat` from the root folder.
   * **Manual start:**
     - In Terminal 1 (Start the Python API Bridge):
       ```bash
       python codemap_api.py
       ```
     - In Terminal 2 (Start the React Dev Server):
       ```bash
       cd visualizer-ui
       pnpm run dev
       ```
3. Open your browser at `http://localhost:5173` (or the port displayed in your terminal).

---

## 📁 Project Architecture

```
CodeMap-Architecture-Intelligence/
├── codemap_core.py             # Pure Python AST parser & dependency engine
├── codemap_app.py              # Tkinter desktop GUI application
├── codemap_diagrams.py         # Mermaid diagram generator & canvas renderer
├── codemap_api.py              # REST API bridge for the React UI
├── codemap_chat.py             # AI code explanation assistant
├── codemap_react_bridge.py     # Synchronizer between Python & Web UI
├── test_diagram_verification.py # Automated test suite for diagram engines
├── visualizer-ui/              # Modern React 19 + TypeScript + Vite web studio
│   ├── src/                    # Components, graph nodes, and custom hooks
│   ├── package.json            # Node dependencies
│   └── vite.config.ts          # Vite build configuration
├── Launch_Tkinter_GUI.bat      # 1-Click desktop launcher
├── Launch_React_Visualizer.bat # 1-Click web studio launcher
├── requirements.txt            # Python requirements
└── LICENSE                     # MIT License
```

---

## 🧪 Testing & Verification

Run the automated verification suite to test diagram rendering and node extraction:

```bash
python test_diagram_verification.py
```

Expected output:
```text
=== Starting CodeMap Diagram & Visualizer Verification ===
✓ Modules codemap_core, codemap_diagrams, and codemap_app imported cleanly.
✓ Diagram prompts enforce 6-10 nodes, top-down flow, and flat subgraphs.
SUCCESS: Verified 11 diagrams across all modes without errors!
```

---

## 📄 License

This project is open-source and licensed under the [MIT License](LICENSE).
