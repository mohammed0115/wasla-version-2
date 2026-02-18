# WASLA Frontend - React TypeScript Application

## Overview

The WASLA frontend is a modern, responsive React application built with **TypeScript**, **Vite**, and **Tailwind CSS**. It provides a comprehensive user interface for the WASLA e-commerce SaaS platform.

**Tech Stack:**
- React 18.2 - UI library
- TypeScript 5.3 - Type safety
- Vite 5.0 - Build tool (ultra-fast)
- Tailwind CSS 3.3 - Styling
- React Router DOM 6.20 - Client-side routing
- Zustand 4.4 - State management
- React Query 3.39 - Server state management & data fetching
- Framer Motion 10.16 - Animations
- React Hook Form 7.48 - Form handling
- Zod 3.22 - Schema validation
- Axios 1.6 - HTTP client
- React Toastify 9.1 - Notifications
- Chart.js 4.4 - Charts and graphs

---

## Project Structure

```
frontend/
├── Dockerfile          # Docker containerization
├── package.json        # Dependencies and scripts
├── vite.config.ts      # Vite configuration (if exists)
├── tsconfig.json       # TypeScript configuration (if exists)
└── src/
    ├── components/     # Reusable UI components
    │   └── ErrorBoundary.tsx
    ├── pages/          # Page components (route-based)
    │   ├── admin/
    │   │   └── Dashboard.tsx
    │   └── auth/
    │       ├── LoginPage.tsx
    │       └── RegisterPage.tsx
    └── store/          # Global state management (Zustand)
        └── authStore.ts
```

---

## Architecture & Design Patterns

### 1. Component Architecture

**Functional Components with Hooks:**
- All components use modern React functional component pattern
- TypeScript for type safety
- React Hooks for state and side effects

**Component Hierarchy:**
```
App (Root)
├── ErrorBoundary
│   ├── LoginPage
│   ├── RegisterPage
│   ├── Dashboard
│   └── [Other protected pages]
└── [Global providers]
```

### 2. State Management - Zustand

**Authentication State (authStore.ts):**
```typescript
// Global auth state
- user: Current logged-in user
- accessToken: JWT access token
- refreshToken: JWT refresh token
- isAuthenticated: Auth status flag
- isLoading: Request loading state
- error: Error messages

// Auth actions
- login(email, password): Authenticate user
- register(data): Create new account
- logout(): Clear auth state
- refreshAccessToken(): Renew JWT token
- setTokens(): Set JWT tokens
- setUser(): Update user info
- clearError(): Clear error state
```

**Persistence:**
- Zustand with persist middleware
- Automatically saves to localStorage
- Tokens persist across page refreshes
- Auto-rehydrates on app load

### 3. Data Fetching - React Query

**Server State Management:**
- React Query for API data fetching
- Automatic caching and revalidation
- Request deduplication
- Background refetching
- Loading/error states

**Example (Dashboard):**
```typescript
const { data: metrics, isLoading } = useQuery(
  'admin-metrics',
  async () => axios.get(`${API_URL}/admin/metrics/`),
  { refetchInterval: 30000 } // Auto-refresh every 30s
);
```

---

## Key Components & Pages

### 1. LoginPage.tsx

**Purpose:** User authentication

**Features:**
- Email & password form validation
- Zod schema validation
- React Hook Form for form state
- Real-time error display
- Loading state indicator
- "Show/Hide Password" toggle
- Error notifications (toast)
- Animated UI (Framer Motion)
- Responsive design (Tailwind)

**Flow:**
```
User enters email/password
         ↓
Validation (Zod schema)
         ↓
API call: POST /api/auth/token/
         ↓
Success: Store tokens + user → Navigate to /dashboard
Fail: Display error toast
```

**API Integration:**
```
POST /api/auth/token/
{
  "email": "user@example.com",
  "password": "password123"
}

Response:
{
  "access": "JWT_TOKEN",
  "refresh": "REFRESH_TOKEN",
  "user": {
    "id": 1,
    "email": "user@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "role": "TENANT_OWNER"
  }
}
```

### 2. RegisterPage.tsx

**Purpose:** User account creation

**Features:**
- Multi-field form (email, password, name, phone)
- Form validation with Zod
- Password strength indicator
- Terms & conditions acceptance
- Loading state during registration
- Error handling and display
- Redirect to login on success

### 3. AdminDashboard.tsx

**Purpose:** Real-time analytics and business metrics

**Features:**
- Real-time KPI cards:
  - Revenue (today, this month)
  - Order metrics (total, pending)
  - Product count
  - New customers
- Statistical indicators (% change)
- Interactive charts:
  - Line chart: Revenue trend
  - Bar chart: Orders
  - Doughnut chart: Product breakdown
- Date range selector (7d, 30d, 90d)
- Auto-refresh every 30 seconds
- Responsive grid layout
- Smooth animations

**Data Structure:**
```typescript
interface Metrics {
  revenue_today: number;
  revenue_this_month: number;
  total_orders: number;
  pending_orders: number;
  active_products: number;
  new_customers_today: number;
}

interface ChartData {
  labels: string[];      // Dates or categories
  revenue: number[];     // Revenue per period
  orders: number[];      // Orders per period
  customers: number[];   // Customers per period
}
```

**API Calls:**
```
GET /api/admin/metrics/
  → Returns Metrics object

GET /api/admin/analytics/chart-data/?range=7d
  → Returns ChartData object
```

### 4. ErrorBoundary.tsx

**Purpose:** Catch React errors and prevent full app crash

**Features:**
- Error catching at component level
- Fallback UI with friendly message
- Error details display (dev mode)
- Refresh page button
- Error logging to console
- Sentry integration ready
- Animated error display

**How It Works:**
```
1. Child component throws error
         ↓
2. ErrorBoundary catches it (getDerivedStateFromError)
         ↓
3. componentDidCatch logs error details
         ↓
4. Render fallback UI instead of crash
         ↓
5. User can refresh page to recover
```

---

## Styling & UI/UX

### Tailwind CSS

**Utility-first CSS framework**
- Responsive design (mobile-first)
- Dark mode capable
- Custom theme colors
- Flexible spacing system

**Example Layout:**
```tsx
<div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100">
  <div className="w-full max-w-md bg-white rounded-lg shadow-xl p-8">
    {/* Content */}
  </div>
</div>
```

### Framer Motion

**Smooth animations and interactions**
- Page transitions
- Component entrance animations
- Hover effects
- Loading states

**Example:**
```tsx
<motion.div
  initial={{ opacity: 0, y: 20 }}
  animate={{ opacity: 1, y: 0 }}
  transition={{ duration: 0.5 }}
>
  {/* Animated content */}
</motion.div>
```

### Responsive Design

**Breakpoints:**
- Mobile: Default (< 640px)
- Tablet: 640px+
- Desktop: 1024px+

**Grid System:**
```tsx
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
  {/* 1 column on mobile, 2 on tablet, 4 on desktop */}
</div>
```

---

## Form Handling & Validation

### React Hook Form + Zod

**Validation Schema (Example):**
```typescript
const loginSchema = z.object({
  email: z.string().email('Invalid email'),
  password: z.string().min(6, 'Min 6 characters'),
});

type LoginFormData = z.infer<typeof loginSchema>;
```

**Form Integration:**
```typescript
const { register, handleSubmit, formState: { errors } } = useForm({
  resolver: zodResolver(loginSchema),
});

<input {...register('email')} />
{errors.email && <span>{errors.email.message}</span>}
```

**Benefits:**
✓ Type-safe form data  
✓ Built-in validation  
✓ Error messages  
✓ Minimal re-renders  
✓ Clean submission handling  

---

## API Integration

### Base Configuration

```typescript
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

// Axios instance
axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
```

### Common Endpoints Used

**Authentication:**
```
POST /auth/token/          → Login
POST /auth/register/       → Register
POST /auth/refresh/        → Refresh token
POST /auth/logout/         → Logout
GET  /auth/me/             → Get current user
```

**Dashboard:**
```
GET /admin/metrics/        → Real-time KPIs
GET /admin/analytics/chart-data/  → Chart data
```

**Error Handling:**
```typescript
try {
  const response = await axios.post(url, data);
} catch (error) {
  const errorMessage = error.response?.data?.detail || 'Request failed';
  toast.error(errorMessage);
}
```

---

## Routing

### React Router DOM

**Route Setup (typical):**
```typescript
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { LoginPage } from './pages/auth/LoginPage';
import { RegisterPage } from './pages/auth/RegisterPage';
import { AdminDashboard } from './pages/admin/Dashboard';
import ProtectedRoute from './components/ProtectedRoute';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route 
          path="/dashboard" 
          element={
            <ProtectedRoute>
              <AdminDashboard />
            </ProtectedRoute>
          } 
        />
      </Routes>
    </BrowserRouter>
  );
}
```

**Protected Routes:**
```typescript
const ProtectedRoute = ({ children }) => {
  const { isAuthenticated } = useAuthStore();
  
  if (!isAuthenticated) {
    return <Navigate to="/login" />;
  }
  
  return children;
};
```

---

## Development Workflow

### Commands

```bash
# Install dependencies
npm install

# Start dev server (hot reload)
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview

# Lint code
npm run lint

# Type check
npm run type-check
```

### Environment Variables

**.env.local (typical):**
```env
VITE_API_URL=http://localhost:8000/api
VITE_APP_NAME=WASLA
```

### Development Server

```bash
npm run dev

# Server runs at:
# http://localhost:5173
```

---

## Production Build

### Build Process

```bash
npm run build
```

**Output:**
- `dist/` folder with optimized bundles
- JavaScript minified and split by route
- CSS optimized
- Assets optimized

### Docker Deployment

```dockerfile
# Build stage
FROM node:18-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# Production stage
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

**Usage:**
```bash
# Build Docker image
docker build -t wasla-frontend .

# Run container
docker run -p 80:80 wasla-frontend
```

---

## Authentication Flow

### 1. User Login Flow

```
1. User enters email + password on LoginPage
   ↓
2. Form validates with Zod schema
   ↓
3. POST /api/auth/token/ with credentials
   ↓
4. Backend returns:
   - access token (JWT)
   - refresh token
   - user object
   ↓
5. Zustand store saves tokens to state + localStorage
   ↓
6. Axios default header updated with Bearer token
   ↓
7. Navigate to /dashboard (protected route)
```

### 2. Token Refresh

```
Access token expires (usually 15 minutes)
   ↓
API call returns 401 Unauthorized
   ↓
Call POST /api/auth/refresh/ with refreshToken
   ↓
Get new access token
   ↓
Retry original request with new token
```

### 3. Logout

```
User clicks logout
   ↓
Clear tokens from state + localStorage
   ↓
Clear Axios default headers
   ↓
Navigate to /login
```

---

## Performance Optimization

### Code Splitting

Vite automatically code-splits by route:
```
dist/
├── index.js          // Main bundle
├── login.js          # Route chunk
├── dashboard.js      # Route chunk
├── admin.js          # Route chunk
└── ...
```

### Lazy Loading

```typescript
import { lazy, Suspense } from 'react';

const Dashboard = lazy(() => import('./pages/Dashboard'));

<Suspense fallback={<Loading />}>
  <Dashboard />
</Suspense>
```

### Caching Strategies

**React Query:**
- Background refetching
- Stale-while-revalidate
- Request deduplication

**Browser:**
- Service Worker (PWA ready)
- IndexedDB for offline data
- Cache headers managed by server

---

## Error Handling

### Global Error Handling

```typescript
// API errors
axios.interceptors.response.use(
  response => response,
  error => {
    if (error.response?.status === 401) {
      // Token expired, refresh or logout
    }
    if (error.response?.status === 403) {
      // Permission denied
    }
    return Promise.reject(error);
  }
);
```

### User Feedback

**Toast Notifications:**
```typescript
toast.success('Operation successful!');
toast.error('Something went wrong');
toast.info('Information message');
toast.warning('Warning message');
```

**Error Boundaries:**
```typescript
<ErrorBoundary>
  <Dashboard />
</ErrorBoundary>
```

---

## Type Safety

### TypeScript Benefits

**Interfaces for API responses:**
```typescript
interface User {
  id: number;
  email: string;
  first_name: string;
  role: 'SUPER_ADMIN' | 'TENANT_OWNER' | 'STAFF';
}

interface Metrics {
  revenue_today: number;
  total_orders: number;
}
```

**Zustand store typing:**
```typescript
export interface AuthState {
  user: User | null;
  accessToken: string | null;
  login: (email: string, password: string) => Promise<void>;
}
```

**Component typing:**
```typescript
const LoginPage: React.FC = () => {
  // Type-safe component
};

const StatCard: React.FC<{ title: string; value: number }> = (props) => {
  // Props are type-checked
};
```

---

## Testing (Setup Ready)

### Test Structure

```
frontend/src/
├── components/
│   ├── ErrorBoundary.tsx
│   └── __tests__/
│       └── ErrorBoundary.test.tsx
├── pages/
│   ├── auth/
│   │   └── __tests__/
│       ├── LoginPage.test.tsx
│       └── RegisterPage.test.tsx
└── store/
    └── __tests__/
        └── authStore.test.ts
```

### Example Tests (to add)

```typescript
// LoginPage.test.tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { LoginPage } from '../LoginPage';

describe('LoginPage', () => {
  it('renders login form', () => {
    render(<LoginPage />);
    expect(screen.getByText('WASLA')).toBeInTheDocument();
  });

  it('submits form with valid data', async () => {
    // Test login flow
  });
});
```

---

## Browser Support

**Modern browsers only:**
- Chrome/Edge 90+
- Firefox 88+
- Safari 14+
- No IE11 support

---

## Key Features Implemented

✅ User authentication (login/register)  
✅ JWT token management  
✅ Protected routes  
✅ Real-time dashboard  
✅ Analytics charts  
✅ Form validation  
✅ Error boundaries  
✅ Toast notifications  
✅ Responsive design  
✅ TypeScript type safety  
✅ Framer Motion animations  
✅ React Query for data fetching  
✅ Zustand for state management  

---

## Features Ready for Implementation

⚠️ To add in future:
- [ ] Product listing page
- [ ] Order management
- [ ] Customer management
- [ ] Payment processing
- [ ] Inventory management
- [ ] Settings/preferences
- [ ] Multi-language support (i18n)
- [ ] Dark mode
- [ ] Mobile app (React Native)
- [ ] PWA features
- [ ] Unit & integration tests
- [ ] E2E tests (Cypress)
- [ ] CI/CD integration

---

## Development Guidelines

### Best Practices

1. **Component Organization:**
   - One component per file
   - Keep components small and focused
   - Lift state up when needed

2. **Props & Types:**
   - Always type props with interfaces
   - Avoid `any` type
   - Use discriminated unions for variant props

3. **Hooks:**
   - Custom hooks for reusable logic
   - useCallback for memoized functions
   - useMemo for expensive computations

4. **State Management:**
   - Zustand for global state
   - React hooks for local state
   - React Query for server state

5. **Performance:**
   - Code splitting by routes
   - Lazy loading components
   - Memoization where needed
   - Avoid prop drilling

6. **Styling:**
   - Utility-first with Tailwind
   - Mobile-first responsive design
   - Consistent spacing and colors
   - Semantic HTML

---

## Troubleshooting

### Common Issues

**CORS errors:**
```
Solution: Check backend CORS_ALLOWED_ORIGINS in Django settings
Backend should include your frontend URL:
CORS_ALLOWED_ORIGINS = ['http://localhost:5173', 'https://yourdomain.com']
```

**Token issues:**
```
Solution: Verify token in localStorage
Check Authorization header in network tab
Ensure refresh token endpoint works
```

**Type errors:**
```
Solution: Run `npm run type-check`
Update interfaces to match backend API
Use typescript-eslint plugin
```

**Build fails:**
```
Solution: npm install (fresh deps)
Clear node_modules & package-lock.json
Check Node version (18+)
```

---

## Resources

- [React Docs](https://react.dev)
- [TypeScript Handbook](https://www.typescriptlang.org/docs/)
- [Vite Guide](https://vitejs.dev/)
- [Tailwind CSS](https://tailwindcss.com)
- [React Router](https://reactrouter.com)
- [Zustand Docs](https://github.com/pmndrs/zustand)
- [React Query](https://tanstack.com/query)
- [Framer Motion](https://www.framer.com/motion/)

---

## Support & Questions

For issues or questions:
1. Check frontend console (F12 → Console)
2. Review network requests (F12 → Network)
3. See error boundary message
4. Check backend API responses
5. Review component TypeScript types
