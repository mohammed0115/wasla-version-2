/**
 * Admin Dashboard Component
 * Real-time metrics, charts, and KPIs
 */

import React, { useState, useEffect } from 'react';
import { useQuery } from 'react-query';
import { Line, Bar, Doughnut } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Tooltip,
  Legend,
  ArcElement,
} from 'chart.js';
import axios from 'axios';
import { motion } from 'framer-motion';
import clsx from 'clsx';
import { useAuthStore } from '@/store/authStore';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Tooltip,
  Legend,
  ArcElement
);

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

interface Metrics {
  revenue_today: number;
  revenue_this_month: number;
  total_orders: number;
  pending_orders: number;
  active_products: number;
  new_customers_today: number;
}

interface ChartData {
  labels: string[];
  revenue: number[];
  orders: number[];
  customers: number[];
}

const StatCard: React.FC<{
  title: string;
  value: string | number;
  change?: number;
  icon: string;
}> = ({ title, value, change, icon }) => (
  <motion.div
    whileHover={{ scale: 1.02 }}
    className="bg-white p-6 rounded-lg shadow-md hover:shadow-lg transition"
  >
    <div className="flex items-start justify-between">
      <div>
        <p className="text-gray-600 text-sm font-medium">{title}</p>
        <p className="text-3xl font-bold text-gray-900 mt-2">{value}</p>
        {change !== undefined && (
          <p className={clsx(
            'text-sm mt-2 font-medium',
            change >= 0 ? 'text-green-600' : 'text-red-600'
          )}>
            {change >= 0 ? '↑' : '↓'} {Math.abs(change)}% from yesterday
          </p>
        )}
      </div>
      <div className="text-4xl">{icon}</div>
    </div>
  </motion.div>
);

export const AdminDashboard: React.FC = () => {
  const { user } = useAuthStore();
  const [dateRange, setDateRange] = useState<'7d' | '30d' | '90d'>('7d');

  // Fetch metrics
  const { data: metrics, isLoading: metricsLoading } = useQuery<Metrics>(
    'admin-metrics',
    async () => {
      const response = await axios.get(`${API_URL}/admin/metrics/`, {
        headers: { Authorization: `Bearer ${useAuthStore((s) => s.accessToken)}` },
      });
      return response.data;
    },
    { refetchInterval: 30000 } // Refetch every 30 seconds
  );

  // Fetch chart data
  const { data: chartData, isLoading: chartLoading } = useQuery<ChartData>(
    ['admin-chart-data', dateRange],
    async () => {
      const response = await axios.get(`${API_URL}/admin/analytics/timeline/`, {
        params: { range: dateRange },
        headers: { Authorization: `Bearer ${useAuthStore((s) => s.accessToken)}` },
      });
      return response.data;
    }
  );

  // Fetch top products
  const { data: topProducts, isLoading: productsLoading } = useQuery<any[]>(
    'admin-top-products',
    async () => {
      const response = await axios.get(`${API_URL}/admin/analytics/top-products/`, {
        params: { limit: 5 },
        headers: { Authorization: `Bearer ${useAuthStore((s) => s.accessToken)}` },
      });
      return response.data;
    }
  );

  const revenueChartData = {
    labels: chartData?.labels || [],
    datasets: [
      {
        label: 'Revenue (SAR)',
        data: chartData?.revenue || [],
        borderColor: '#3b82f6',
        backgroundColor: 'rgba(59, 130, 246, 0.1)',
        tension: 0.4,
        fill: true,
      },
    ],
  };

  const ordersChartData = {
    labels: chartData?.labels || [],
    datasets: [
      {
        label: 'Orders',
        data: chartData?.orders || [],
        backgroundColor: ['#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899'],
      },
    ],
  };

  const paymentMethodsData = {
    labels: ['Tap', 'Stripe', 'PayPal', 'Wallet'],
    datasets: [
      {
        data: [35, 25, 25, 15],
        backgroundColor: ['#3b82f6', '#10b981', '#f59e0b', '#8b5cf6'],
      },
    ],
  };

  if (metricsLoading || chartLoading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-8"
        >
          <h1 className="text-4xl font-bold text-gray-900">Dashboard</h1>
          <p className="text-gray-600 mt-2">Welcome back, {user?.first_name}!</p>
        </motion.div>

        {/* Date Range Filter */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="mb-8 flex gap-3"
        >
          {['7d', '30d', '90d'].map((range) => (
            <button
              key={range}
              onClick={() => setDateRange(range as '7d' | '30d' | '90d')}
              className={clsx(
                'px-4 py-2 rounded-lg font-medium transition',
                dateRange === range
                  ? 'bg-blue-600 text-white'
                  : 'bg-white text-gray-700 border border-gray-200 hover:bg-gray-50'
              )}
            >
              Last {range === '7d' ? '7 days' : range === '30d' ? '30 days' : '90 days'}
            </button>
          ))}
        </motion.div>

        {/* KPI Cards */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ staggerChildren: 0.1 }}
          className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-8"
        >
          <StatCard
            title="Today's Revenue"
            value={`${metrics?.revenue_today?.toLocaleString()} SAR`}
            change={12}
            icon="💰"
          />
          <StatCard
            title="Month Revenue"
            value={`${metrics?.revenue_this_month?.toLocaleString()} SAR`}
            change={8}
            icon="📊"
          />
          <StatCard
            title="Total Orders"
            value={metrics?.total_orders || 0}
            change={5}
            icon="📦"
          />
          <StatCard
            title="Pending Orders"
            value={metrics?.pending_orders || 0}
            change={-2}
            icon="⏳"
          />
          <StatCard
            title="Active Products"
            value={metrics?.active_products || 0}
            icon="🛍️"
          />
          <StatCard
            title="New Customers"
            value={metrics?.new_customers_today || 0}
            change={15}
            icon="👥"
          />
        </motion.div>

        {/* Charts Row 1 */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8"
        >
          {/* Revenue Chart */}
          <div className="lg:col-span-2 bg-white p-6 rounded-lg shadow-md">
            <h2 className="text-lg font-bold text-gray-900 mb-4">Revenue Trend</h2>
            <Line
              data={revenueChartData}
              options={{
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                  legend: { display: false },
                },
                scales: {
                  y: {
                    ticks: {
                      callback: (value) => `${value} SAR`,
                    },
                  },
                },
              }}
            />
          </div>

          {/* Payment Methods */}
          <div className="bg-white p-6 rounded-lg shadow-md">
            <h2 className="text-lg font-bold text-gray-900 mb-4">Payment Methods</h2>
            <Doughnut
              data={paymentMethodsData}
              options={{
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                  legend: { position: 'bottom' },
                },
              }}
            />
          </div>
        </motion.div>

        {/* Charts Row 2 */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8"
        >
          {/* Orders Chart */}
          <div className="bg-white p-6 rounded-lg shadow-md">
            <h2 className="text-lg font-bold text-gray-900 mb-4">Orders by Status</h2>
            <Bar
              data={ordersChartData}
              options={{
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                  legend: { display: false },
                },
              }}
            />
          </div>

          {/* Top Products */}
          <div className="bg-white p-6 rounded-lg shadow-md">
            <h2 className="text-lg font-bold text-gray-900 mb-4">Top 5 Products</h2>
            {productsLoading ? (
              <div className="animate-pulse space-y-3">
                {[...Array(5)].map((_, i) => (
                  <div key={i} className="h-4 bg-gray-200 rounded w-3/4"></div>
                ))}
              </div>
            ) : (
              <div className="space-y-3">
                {topProducts?.map((product, idx) => (
                  <div key={idx} className="flex items-center justify-between p-3 bg-gray-50 rounded">
                    <div className="flex-1">
                      <p className="font-medium text-gray-900">{product.name}</p>
                      <p className="text-sm text-gray-600">{product.sales} sales</p>
                    </div>
                    <p className="font-bold text-blue-600">{product.revenue} SAR</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </motion.div>
      </div>
    </div>
  );
};

export default AdminDashboard;
