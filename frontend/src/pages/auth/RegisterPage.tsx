/**
 * Register Component
 * Multi-step registration with persona/onboarding
 */

import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import { useAuthStore } from '@/store/authStore';
import { toast } from 'react-toastify';
import { motion } from 'framer-motion';
import clsx from 'clsx';

const registerSchema = z.object({
  email: z.string().email('Invalid email address'),
  password: z.string().min(8, 'Password must be at least 8 characters'),
  password_confirm: z.string(),
  first_name: z.string().min(2, 'First name required'),
  last_name: z.string().min(2, 'Last name required'),
  phone_number: z.string().optional(),
  store_name: z.string().min(3, 'Store name required'),
  country: z.string().min(2, 'Country required'),
}).refine((data) => data.password === data.password_confirm, {
  message: "Passwords don't match",
  path: ["password_confirm"],
});

type RegisterFormData = z.infer<typeof registerSchema>;

const STEPS = ['Account', 'Store', 'Verification'];
const COUNTRIES = [
  { code: 'SA', name: '🇸🇦 Saudi Arabia' },
  { code: 'AE', name: '🇦🇪 United Arab Emirates' },
  { code: 'KW', name: '🇰🇼 Kuwait' },
  { code: 'QA', name: '🇶🇦 Qatar' },
  { code: 'OM', name: '🇴🇲 Oman' },
  { code: 'BH', name: '🇧🇭 Bahrain' },
];

export const RegisterPage: React.FC = () => {
  const navigate = useNavigate();
  const { register: registerUser, isLoading, error, clearError } = useAuthStore();
  const [step, setStep] = useState(0);
  const [agreeToTerms, setAgreeToTerms] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
    watch,
  } = useForm<RegisterFormData>({
    resolver: zodResolver(registerSchema),
    mode: 'onBlur',
  });

  const password = watch('password');

  const onSubmit = async (data: RegisterFormData) => {
    if (!agreeToTerms) {
      toast.error('Please agree to terms and conditions');
      return;
    }

    clearError();
    try {
      await registerUser({
        email: data.email,
        password: data.password,
        first_name: data.first_name,
        last_name: data.last_name,
        phone_number: data.phone_number,
      });
      toast.success('Registration successful!');
      navigate('/onboarding/store');
    } catch (err) {
      toast.error(error || 'Registration failed');
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100 py-12 px-4">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="w-full max-w-md"
      >
        <div className="bg-white rounded-lg shadow-xl p-8">
          {/* Header */}
          <div className="text-center mb-8">
            <h1 className="text-3xl font-bold text-gray-900">Create Account</h1>
            <p className="text-gray-600 mt-2">Step {step + 1} of {STEPS.length}</p>
          </div>

          {/* Progress Bar */}
          <div className="mb-8 flex gap-2">
            {STEPS.map((stepName, idx) => (
              <div
                key={idx}
                className={clsx(
                  'flex-1 h-2 rounded-full transition',
                  idx <= step ? 'bg-blue-600' : 'bg-gray-200'
                )}
              />
            ))}
          </div>

          {/* Error Alert */}
          {error && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg"
            >
              <p className="text-red-600 text-sm">{error}</p>
            </motion.div>
          )}

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
            {/* Step 1: Account */}
            {step === 0 && (
              <motion.div
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                className="space-y-4"
              >
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700">First Name</label>
                    <input
                      {...register('first_name')}
                      type="text"
                      placeholder="Ahmed"
                      className={clsx(
                        'mt-2 w-full px-4 py-2 border rounded-lg',
                        errors.first_name ? 'border-red-500' : 'border-gray-300'
                      )}
                    />
                    {errors.first_name && (
                      <p className="mt-1 text-xs text-red-600">{errors.first_name.message}</p>
                    )}
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Last Name</label>
                    <input
                      {...register('last_name')}
                      type="text"
                      placeholder="Ali"
                      className={clsx(
                        'mt-2 w-full px-4 py-2 border rounded-lg',
                        errors.last_name ? 'border-red-500' : 'border-gray-300'
                      )}
                    />
                    {errors.last_name && (
                      <p className="mt-1 text-xs text-red-600">{errors.last_name.message}</p>
                    )}
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700">Email</label>
                  <input
                    {...register('email')}
                    type="email"
                    placeholder="you@example.com"
                    className={clsx(
                      'mt-2 w-full px-4 py-2 border rounded-lg',
                      errors.email ? 'border-red-500' : 'border-gray-300'
                    )}
                  />
                  {errors.email && (
                    <p className="mt-1 text-xs text-red-600">{errors.email.message}</p>
                  )}
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700">Phone (Optional)</label>
                  <input
                    {...register('phone_number')}
                    type="tel"
                    placeholder="+966 XX XXX XXXX"
                    className="mt-2 w-full px-4 py-2 border rounded-lg border-gray-300"
                  />
                </div>
              </motion.div>
            )}

            {/* Step 2: Password */}
            {step === 1 && (
              <motion.div
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                className="space-y-4"
              >
                <div>
                  <label className="block text-sm font-medium text-gray-700">Password</label>
                  <input
                    {...register('password')}
                    type="password"
                    placeholder="••••••••"
                    className={clsx(
                      'mt-2 w-full px-4 py-2 border rounded-lg',
                      errors.password ? 'border-red-500' : 'border-gray-300'
                    )}
                  />
                  {errors.password && (
                    <p className="mt-1 text-xs text-red-600">{errors.password.message}</p>
                  )}
                  {password && password.length > 0 && (
                    <div className="mt-3 space-y-2">
                      <div className="text-xs">Strength:</div>
                      <div className="flex gap-1">
                        {[...Array(4)].map((_, i) => (
                          <div
                            key={i}
                            className={clsx(
                              'h-1 flex-1 rounded-full',
                              password.length > i * 2
                                ? 'bg-green-500'
                                : 'bg-gray-200'
                            )}
                          />
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700">Confirm Password</label>
                  <input
                    {...register('password_confirm')}
                    type="password"
                    placeholder="••••••••"
                    className={clsx(
                      'mt-2 w-full px-4 py-2 border rounded-lg',
                      errors.password_confirm ? 'border-red-500' : 'border-gray-300'
                    )}
                  />
                  {errors.password_confirm && (
                    <p className="mt-1 text-xs text-red-600">{errors.password_confirm.message}</p>
                  )}
                </div>
              </motion.div>
            )}

            {/* Step 3: Store Info */}
            {step === 2 && (
              <motion.div
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                className="space-y-4"
              >
                <div>
                  <label className="block text-sm font-medium text-gray-700">Store Name</label>
                  <input
                    {...register('store_name')}
                    type="text"
                    placeholder="My Awesome Store"
                    className={clsx(
                      'mt-2 w-full px-4 py-2 border rounded-lg',
                      errors.store_name ? 'border-red-500' : 'border-gray-300'
                    )}
                  />
                  {errors.store_name && (
                    <p className="mt-1 text-xs text-red-600">{errors.store_name.message}</p>
                  )}
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700">Country</label>
                  <select
                    {...register('country')}
                    className={clsx(
                      'mt-2 w-full px-4 py-2 border rounded-lg',
                      errors.country ? 'border-red-500' : 'border-gray-300'
                    )}
                  >
                    <option value="">Select country...</option>
                    {COUNTRIES.map((country) => (
                      <option key={country.code} value={country.code}>
                        {country.name}
                      </option>
                    ))}
                  </select>
                  {errors.country && (
                    <p className="mt-1 text-xs text-red-600">{errors.country.message}</p>
                  )}
                </div>

                <div className="flex gap-3 pt-4">
                  <label className="flex items-start cursor-pointer">
                    <input
                      type="checkbox"
                      checked={agreeToTerms}
                      onChange={(e) => setAgreeToTerms(e.target.checked)}
                      className="mt-1 w-4 h-4 rounded"
                    />
                    <span className="ml-2 text-sm text-gray-600">
                      I agree to{' '}
                      <a href="/terms" className="text-blue-600">
                        Terms & Conditions
                      </a>
                    </span>
                  </label>
                </div>
              </motion.div>
            )}

            {/* Navigation Buttons */}
            <div className="flex gap-3 pt-6">
              {step > 0 && (
                <button
                  type="button"
                  onClick={() => setStep(step - 1)}
                  className="flex-1 py-2 px-4 border border-gray-300 rounded-lg hover:bg-gray-50 transition"
                >
                  Back
                </button>
              )}
              <button
                type={step === STEPS.length - 1 ? 'submit' : 'button'}
                onClick={() => step < STEPS.length - 1 && setStep(step + 1)}
                disabled={isLoading}
                className={clsx(
                  'flex-1 py-2 px-4 rounded-lg font-medium transition',
                  isLoading
                    ? 'bg-blue-400 text-white cursor-not-allowed'
                    : 'bg-blue-600 text-white hover:bg-blue-700'
                )}
              >
                {isLoading ? 'Creating...' : step === STEPS.length - 1 ? 'Create Account' : 'Next'}
              </button>
            </div>

            <p className="text-center text-gray-600 text-sm">
              Already have an account?{' '}
              <a href="/login" className="text-blue-600 hover:text-blue-700 font-medium">
                Sign in
              </a>
            </p>
          </form>
        </div>
      </motion.div>
    </div>
  );
};

export default RegisterPage;
