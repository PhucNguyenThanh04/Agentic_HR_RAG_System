# Face Attendance Web Dashboard

Frontend React + TypeScript + Vite cho `FaceAttendanceManagementSystem`.

## Stack

- React
- TypeScript
- Vite
- React Router
- TanStack Query
- Axios
- React Hook Form
- Zod
- Zustand

## Env

Copy `.env.example` and set the API base URL:

```env
VITE_API_BASE_URL=/api/v1
```

Local development uses the Vite proxy to forward `/api` requests to `http://localhost:8000`.

## Scripts

```bash
npm install
npm run dev
npm run build
npm run lint
```

## Structure

Source code is feature-based under `src/features`, with shared layout/UI in `src/components`, API client in `src/lib`, auth store in `src/stores`, and routing in `src/app`.

Backend services are only consumed through API contracts; this frontend does not modify backend code.
