/**
 * Error Boundary Component
 * Catches React errors and displays fallback UI
 */

import React, { ReactNode, Component, ErrorInfo } from 'react';
import { motion } from 'framer-motion';

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Error caught by boundary:', error, errorInfo);
    // Log to error tracking service (Sentry, etc.)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen flex items-center justify-center bg-red-50 p-4">
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            className="bg-white rounded-lg shadow-lg p-8 max-w-md"
          >
            <div className="text-center">
              <div className="text-6xl mb-4">⚠️</div>
              <h1 className="text-2xl font-bold text-red-600 mb-2">Something went wrong</h1>
              <p className="text-gray-600 mb-4">
                {this.state.error?.message || 'An unexpected error occurred'}
              </p>
              <p className="text-sm text-gray-500 mb-8">
                Our team has been notified. Please try refreshing the page.
              </p>
              <button
                onClick={() => window.location.reload()}
                className="w-full py-2 px-4 bg-red-600 text-white rounded-lg hover:bg-red-700 transition"
              >
                Refresh Page
              </button>
            </div>
          </motion.div>
        </div>
      );
    }

    return this.props.children;
  }
}

// Not Found (404) Page
export const NotFoundPage: React.FC = () => (
  <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100 p-4">
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="text-center"
    >
      <div className="text-9xl font-bold text-blue-600 mb-4">404</div>
      <h1 className="text-3xl font-bold text-gray-900 mb-2">Page not found</h1>
      <p className="text-gray-600 mb-8">
        Sorry, we couldn't find the page you're looking for.
      </p>
      <a
        href="/dashboard"
        className="inline-block px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition"
      >
        Go to Dashboard
      </a>
    </motion.div>
  </div>
);

// Unauthorized (401) Page
export const UnauthorizedPage: React.FC = () => (
  <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-yellow-50 to-orange-100 p-4">
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="text-center max-w-md"
    >
      <div className="text-6xl mb-4">🔐</div>
      <h1 className="text-3xl font-bold text-gray-900 mb-2">Access Denied</h1>
      <p className="text-gray-600 mb-8">
        You don't have permission to access this page. Please log in with the correct account.
      </p>
      <a
        href="/login"
        className="inline-block px-6 py-3 bg-orange-600 text-white rounded-lg hover:bg-orange-700 transition"
      >
        Go to Login
      </a>
    </motion.div>
  </div>
);

// Server Error (500) Page
export const ServerErrorPage: React.FC = () => (
  <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-red-50 to-pink-100 p-4">
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="text-center max-w-md"
    >
      <div className="text-6xl mb-4">❌</div>
      <h1 className="text-3xl font-bold text-gray-900 mb-2">Server Error</h1>
      <p className="text-gray-600 mb-8">
        Something went wrong on our end. Our team has been notified.
      </p>
      <a
        href="/"
        className="inline-block px-6 py-3 bg-red-600 text-white rounded-lg hover:bg-red-700 transition"
      >
        Go Home
      </a>
    </motion.div>
  </div>
);

// Network Error Component
export const NetworkError: React.FC<{ onRetry: () => void }> = ({ onRetry }) => (
  <motion.div
    initial={{ opacity: 0 }}
    animate={{ opacity: 1 }}
    className="p-4 bg-red-50 border border-red-200 rounded-lg"
  >
    <div className="flex items-start gap-3">
      <span className="text-2xl">📡</span>
      <div className="flex-1">
        <h3 className="font-semibold text-red-800">Connection Error</h3>
        <p className="text-sm text-red-700 mt-1">
          Failed to connect to the server. Please check your internet connection.
        </p>
        <button
          onClick={onRetry}
          className="mt-3 px-4 py-2 bg-red-600 text-white text-sm rounded hover:bg-red-700 transition"
        >
          Retry
        </button>
      </div>
    </div>
  </motion.div>
);

// Toast Notification Component
export const Toast: React.FC<{
  message: string;
  type: 'success' | 'error' | 'info' | 'warning';
  onClose: () => void;
}> = ({ message, type, onClose }) => {
  const bgColor = {
    success: 'bg-green-50',
    error: 'bg-red-50',
    info: 'bg-blue-50',
    warning: 'bg-yellow-50',
  }[type];

  const borderColor = {
    success: 'border-green-200',
    error: 'border-red-200',
    info: 'border-blue-200',
    warning: 'border-yellow-200',
  }[type];

  const textColor = {
    success: 'text-green-700',
    error: 'text-red-700',
    info: 'text-blue-700',
    warning: 'text-yellow-700',
  }[type];

  const icon = {
    success: '✅',
    error: '❌',
    info: 'ℹ️',
    warning: '⚠️',
  }[type];

  return (
    <motion.div
      initial={{ opacity: 0, y: -20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      className={`${bgColor} border ${borderColor} rounded-lg p-4 flex gap-3 items-center`}
    >
      <span className="text-2xl">{icon}</span>
      <p className={`flex-1 ${textColor} font-medium`}>{message}</p>
      <button
        onClick={onClose}
        className="text-gray-400 hover:text-gray-600"
      >
        ✕
      </button>
    </motion.div>
  );
};

export default ErrorBoundary;
