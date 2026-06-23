# Inline Coding Playground Overview

This document outlines the proposal, feasibility, and architectural choices for adding an inline code playground to the LMS platform. 

The goal of the playground is to allow students to write and execute code (specifically Python) directly inside the course or lesson page without leaving the browser, eliminating the friction of switching back and forth to an external IDE like VS Code.

---

## 1. Core Component Requirements

A functional inline playground consists of three visual and structural components:

```
+-----------------------------------------------------------+
|                      Header (Run Button)                  |
+-----------------------------+-----------------------------+
|                             |                             |
|                             |    Interactive Playground   |
|                             |                             |
|        Course Content       |    +-------------------+    |
|       (Lesson Outline       |    |    Code Editor    |    |
|        & Material)          |    +-------------------+    |
|                             |    |  Terminal Output  |    |
|                             |    +-------------------+    |
|                             |                             |
+-----------------------------+-----------------------------+
```

1. **Split-Screen Panel Layout**: A resizable container separating the course syllabus/lesson from the playground.
2. **Code Editor**: A syntax-highlighted text input supporting Python language formatting, auto-indentation, and basic autocompletion.
3. **Terminal Output**: A terminal-like terminal console displaying standard output (`stdout`), error messages (`stderr`), and handling interactive script inputs (`stdin`).

---

## 2. Technical Execution Options

There are three ways to execute user code in a web application:

| Feature / Detail | Option A: Client-Side WASM (Pyodide) | Option B: Remote Execution API | Option C: Custom Docker Containers |
| :--- | :--- | :--- | :--- |
| **Execution Location** | User's browser (WebAssembly) | Third-Party Sandboxed Servers | Private Cloud Servers |
| **Server Cost** | **$0** (Runs on client machine) | Low (Pay-per-request or subscription) | High (Constant server costs) |
| **Security Risk** | **None** (Fully isolated inside client browser) | None (Handled by the third-party API) | High (Requires intense system hardening) |
| **Setup Complexity** | Low-Medium | Low | High |
| **Offline Support** | Yes (after initial assets load) | No | No |
| **Capabilities** | Core Python + standard libraries + WASM-supported packages | Complete Python and OS commands | Complete OS terminal access (`bash`, `pip`) |
| **Ideal For** | Basic-to-advanced Python lessons, algorithms, and syntax | Simple multi-language setups | Full workspace/IDE replacements (e.g., Replit) |

---

## 3. Component Recommendation

For the **LMS AI Platform**, we recommend **Option A (Client-Side WASM using Pyodide)**.
* It eliminates hosting costs entirely, meaning the platform can scale to thousands of active learners without raising cloud server bills.
* It presents zero risk of remote code execution (RCE) attacks on the backend server.
* It responds instantly as it does not rely on round-trip API network requests.
