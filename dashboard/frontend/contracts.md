# Frontend Contracts — Dark Factory Mission Control

## Directory Structure

```
dashboard/frontend/
├── src/
│   ├── components/
│   │   ├── App.tsx              # Main shell/layout component
│   │   ├── Header.tsx           # 'Dark Factory — Mission Control' header
│   │   ├── AgentCards.tsx       # Placeholder for agent status cards
│   │   ├── TaskProgress.tsx     # Placeholder for task progress display
│   │   ├── LiveLog.tsx          # Placeholder for live log viewer
│   │   └── JobHistory.tsx       # Placeholder for job history table
│   ├── hooks/
│   │   └── (to be added in future tasks)
│   ├── types/
│   │   └── index.ts             # TypeScript interfaces
│   ├── api/
│   │   └── client.ts            # Typed fetch wrapper & endpoints
│   ├── App.css                  # App-level styles
│   └── main.tsx                 # React entry point
├── public/
│   └── (static assets)
├── index.html                   # HTML template
├── package.json                 # Dependencies & scripts
├── tsconfig.json                # TypeScript configuration
├── vite.config.ts               # Vite configuration with /api proxy
├── tailwind.config.ts           # Tailwind CSS config (dark mode default)
├── postcss.config.cjs           # PostCSS config for Tailwind
├── Makefile                     # Build commands
└── .gitignore                   # Node deps, build output, etc.
```

---

## Type Definitions

**File**: `src/types/index.ts`

### EventType
```typescript
enum EventType {
  AGENT_STARTED = "agent_started",
  AGENT_COMPLETED = "agent_completed",
  TASK_CREATED = "task_created",
  TASK_COMPLETED = "task_completed",
  TEST_PASSED = "test_passed",
  TEST_FAILED = "test_failed",
  LOG_OUTPUT = "log_output",
  ERROR = "error",
}
```

### Event
```typescript
interface Event {
  id: string;                    // UUID
  timestamp: string;             // ISO 8601 datetime
  type: EventType;               // Event type enum
  job_id: string;                // Parent job ID
  agent_name?: string;           // Agent that emitted event (optional)
  message: string;               // Human-readable message
  data?: Record<string, unknown>; // Additional context (optional)
}
```

### JobSummary
```typescript
interface JobSummary {
  id: string;                    // UUID
  issue_number: number;          // GitHub issue ID
  task_number: number;           // Task number within issue
  status: "pending" | "running" | "completed" | "failed"; // Job status
  created_at: string;            // ISO 8601 datetime
  started_at?: string;           // ISO 8601 datetime (optional)
  completed_at?: string;         // ISO 8601 datetime (optional)
  agent_name?: string;           // Current agent name (optional)
  progress_percent: number;      // 0-100
}
```

### JobDetail
```typescript
interface JobDetail extends JobSummary {
  description: string;           // Task description from spec
  events: Event[];               // All events for this job
  error_message?: string;        // Error details if failed (optional)
  approver_feedback?: string;    // Human feedback if blocked (optional)
}
```

---

## API Client Functions

**File**: `src/api/client.ts`

### getJobs()
```typescript
/**
 * Fetch all jobs (summaries only)
 * @returns Promise<JobSummary[]>
 */
function getJobs(): Promise<JobSummary[]>;
```

**Request**: `GET /api/v1/jobs`

**Response**: 
```json
{
  "jobs": [
    {
      "id": "uuid",
      "issue_number": 42,
      "task_number": 1,
      "status": "running",
      "created_at": "2026-04-05T10:00:00Z",
      "started_at": "2026-04-05T10:05:00Z",
      "agent_name": "generator",
      "progress_percent": 45
    }
  ]
}
```

### getJob(jobId: string)
```typescript
/**
 * Fetch a single job with full details and event history
 * @param jobId - UUID of the job
 * @returns Promise<JobDetail>
 */
function getJob(jobId: string): Promise<JobDetail>;
```

**Request**: `GET /api/v1/jobs/{jobId}`

**Response**:
```json
{
  "id": "uuid",
  "issue_number": 42,
  "task_number": 1,
  "status": "running",
  "created_at": "2026-04-05T10:00:00Z",
  "started_at": "2026-04-05T10:05:00Z",
  "agent_name": "generator",
  "progress_percent": 45,
  "description": "Scaffold React frontend...",
  "error_message": null,
  "approver_feedback": null,
  "events": [
    {
      "id": "uuid",
      "timestamp": "2026-04-05T10:00:00Z",
      "type": "task_created",
      "job_id": "uuid",
      "agent_name": null,
      "message": "Task created",
      "data": {}
    }
  ]
}
```

### getJobLog(jobId: string)
```typescript
/**
 * Fetch live event stream for a job (Server-Sent Events or polling)
 * @param jobId - UUID of the job
 * @returns Promise<Event[]> - Latest events
 */
function getJobLog(jobId: string): Promise<Event[]>;
```

**Request**: `GET /api/v1/jobs/{jobId}/log`

**Response**:
```json
{
  "events": [
    {
      "id": "uuid",
      "timestamp": "2026-04-05T10:05:12Z",
      "type": "log_output",
      "job_id": "uuid",
      "agent_name": "generator",
      "message": "Initializing Vite project...",
      "data": {}
    }
  ]
}
```

---

## Component Structure

**File**: `src/components/App.tsx`

### App Component (Root)
```typescript
/**
 * Main application shell with dark theme
 * - Header with 'Dark Factory — Mission Control' title
 * - Grid/flex layout with sections:
 *   - AgentCards: agent status overview
 *   - TaskProgress: current task progress bar
 *   - LiveLog: streaming event log (last 20 events)
 *   - JobHistory: recent jobs table
 * 
 * Rendered with Tailwind dark mode classes (dark:)
 */
export function App(): JSX.Element;
```

### Header Component
```typescript
/**
 * Fixed header with title and branding
 * - Text: 'Dark Factory — Mission Control'
 * - Dark background, light text
 * - Sticky positioning
 */
export function Header(): JSX.Element;
```

### AgentCards Component (Placeholder)
```typescript
/**
 * Grid of agent status cards
 * - Fields: agent name, status, current task
 * - Shows all 5 agents (generator, tester, reviewer, integrator, evaluator)
 * - Conditional styling: running=blue, idle=gray, error=red
 */
export function AgentCards(): JSX.Element;
```

### TaskProgress Component (Placeholder)
```typescript
/**
 * Current task progress display
 * - Progress bar (0-100%)
 * - Estimated time remaining
 * - Agent currently running
 */
export function TaskProgress(): JSX.Element;
```

### LiveLog Component (Placeholder)
```typescript
/**
 * Live event log viewer
 * - Scrollable list of last 20 events
 * - Event type badge (color-coded)
 * - Timestamp + message
 * - Auto-scroll to bottom on new event
 */
export function LiveLog(): JSX.Element;
```

### JobHistory Component (Placeholder)
```typescript
/**
 * Table of recent jobs
 * - Columns: Issue #, Task, Status, Started, Duration
 * - Clickable rows to view job detail
 * - Sort by created_at descending (newest first)
 */
export function JobHistory(): JSX.Element;
```

---

## Configuration Files

### tsconfig.json

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "strict": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "resolveJsonModule": true,
    "allowSyntheticDefaultImports": true,
    "esModuleInterop": true,
    "moduleResolution": "bundler"
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

### vite.config.ts

```typescript
/**
 * Vite configuration
 * - React plugin enabled
 * - TypeScript support
 * - Proxy: /api/* → http://localhost:8000
 * - Default entry: index.html
 */
```

**Proxy Rule**:
```
/api -> http://localhost:8000
```

### tailwind.config.ts

```typescript
/**
 * Tailwind CSS configuration
 * - Dark mode: 'class' or 'media'
 * - Dark mode is DEFAULT (apply dark: classes by default)
 * - Content paths: src/**/*.{js,jsx,ts,tsx}
 * - Theme: extend default Tailwind colors/spacing
 */
```

### postcss.config.cjs

```javascript
/**
 * PostCSS configuration for Tailwind
 * - Plugins: tailwindcss, autoprefixer
 */
```

### package.json

```json
{
  "name": "dark-factory-frontend",
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0"
  },
  "devDependencies": {
    "@types/react": "^18.2.0",
    "@types/react-dom": "^18.2.0",
    "@vitejs/plugin-react": "^4.2.0",
    "autoprefixer": "^10.4.0",
    "postcss": "^8.4.0",
    "tailwindcss": "^3.3.0",
    "typescript": "^5.3.0",
    "vite": "^5.0.0"
  }
}
```

### Makefile

```makefile
# Frontend build targets

.PHONY: install dev build clean

install:
	# Install npm dependencies (or npm ci for CI environments)

dev:
	# Start Vite dev server (http://localhost:5173)

build:
	# Compile TypeScript and bundle with Vite

clean:
	# Remove node_modules/, dist/, .vite/ directories
```

---

## Key Constraints

1. **TypeScript**: All files `.ts` or `.tsx`. No `.js`. Strict mode enabled.
2. **Dark Mode**: Tailwind dark mode is default — use `dark:` classes for dark-only styling, not light-only.
3. **API Proxy**: Vite dev server must proxy `/api/*` to `http://localhost:8000` so the backend doesn't need CORS headers during dev.
4. **Types**: `src/types/index.ts` is the single source of truth for API contracts. Component tests and API tests should import from there.
5. **No React Router**: Placeholder components only. No routing setup yet.
6. **No State Management**: Placeholder components are static/hardcoded. No Redux/Zustand yet.
7. **API Client**: Functions must be pure (no hooks, no side effects). Easy to test in isolation.

---

## Test Interface (for QA reference, not yet implemented)

- `getJobs()` returns `JobSummary[]` with 0+ items
- `getJob(jobId)` returns `JobDetail` with full event history
- `getJobLog(jobId)` returns latest `Event[]`
- Component rendering: App renders without crashing with mock data
- Vite build succeeds with 0 errors/warnings
- TypeScript strict mode passes with 0 errors

