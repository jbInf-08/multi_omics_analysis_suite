/**
 * Form Components
 * ================
 *
 * Reusable form components with react-hook-form and zod validation.
 */

import React from 'react';
import {
  FormProvider,
  useFormContext,
  UseFormReturn,
  FieldValues,
  SubmitHandler,
} from 'react-hook-form';
import clsx from 'clsx';

// Form wrapper with context
interface FormProps<T extends FieldValues> {
  form: UseFormReturn<T>;
  onSubmit: SubmitHandler<T>;
  children: React.ReactNode;
  className?: string;
}

export function Form<T extends FieldValues>({
  form,
  onSubmit,
  children,
  className,
}: FormProps<T>) {
  return (
    <FormProvider {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className={className}>
        {children}
      </form>
    </FormProvider>
  );
}

// useZodForm lives in ./useZodForm so this module exports only components --
// see the note there.

// Form field wrapper
interface FormFieldProps {
  name: string;
  label?: string;
  description?: string;
  required?: boolean;
  children: React.ReactNode;
  className?: string;
}

export function FormField({
  name,
  label,
  description,
  required,
  children,
  className,
}: FormFieldProps) {
  const { formState: { errors } } = useFormContext();
  const error = errors[name];

  return (
    <div className={clsx('space-y-1', className)}>
      {label && (
        <label
          htmlFor={name}
          className="block text-sm font-medium text-gray-700"
        >
          {label}
          {required && <span className="text-red-500 ml-1">*</span>}
        </label>
      )}
      {children}
      {description && !error && (
        <p className="text-sm text-gray-500">{description}</p>
      )}
      {error && (
        <p className="text-sm text-red-600" role="alert">
          {error.message as string}
        </p>
      )}
    </div>
  );
}

// Input component
interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  name: string;
  label?: string;
  description?: string;
}

export function Input({
  name,
  label,
  description,
  className,
  ...props
}: InputProps) {
  const { register, formState: { errors } } = useFormContext();
  const error = errors[name];
  const invalid = Boolean(error);

  return (
    <FormField name={name} label={label} description={description} required={props.required}>
      <input
        id={name}
        {...register(name)}
        {...props}
        className={clsx(
          'block w-full rounded-md shadow-sm sm:text-sm transition-colors',
          'focus:ring-indigo-500 focus:border-indigo-500',
          error
            ? 'border-red-300 text-red-900 placeholder-red-300 focus:ring-red-500 focus:border-red-500'
            : 'border-gray-300',
          className
        )}
        {...(invalid ? { 'aria-invalid': 'true' as const } : {})}
        aria-describedby={error ? `${name}-error` : undefined}
      />
    </FormField>
  );
}

// Textarea component
interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  name: string;
  label?: string;
  description?: string;
}

export function Textarea({
  name,
  label,
  description,
  className,
  ...props
}: TextareaProps) {
  const { register, formState: { errors } } = useFormContext();
  const error = errors[name];
  const invalid = Boolean(error);

  return (
    <FormField name={name} label={label} description={description} required={props.required}>
      <textarea
        id={name}
        {...register(name)}
        {...props}
        className={clsx(
          'block w-full rounded-md shadow-sm sm:text-sm transition-colors',
          'focus:ring-indigo-500 focus:border-indigo-500',
          error
            ? 'border-red-300 text-red-900 placeholder-red-300'
            : 'border-gray-300',
          className
        )}
        {...(invalid ? { 'aria-invalid': 'true' as const } : {})}
      />
    </FormField>
  );
}

// Select component
interface SelectOption {
  value: string;
  label: string;
  disabled?: boolean;
}

interface SelectProps extends Omit<React.SelectHTMLAttributes<HTMLSelectElement>, 'children'> {
  name: string;
  label?: string;
  description?: string;
  options: SelectOption[];
  placeholder?: string;
}

export function Select({
  name,
  label,
  description,
  options,
  placeholder,
  className,
  ...props
}: SelectProps) {
  const { register, formState: { errors } } = useFormContext();
  const error = errors[name];
  const invalid = Boolean(error);

  return (
    <FormField name={name} label={label} description={description} required={props.required}>
      <select
        id={name}
        {...register(name)}
        {...props}
        className={clsx(
          'block w-full rounded-md shadow-sm sm:text-sm transition-colors',
          'focus:ring-indigo-500 focus:border-indigo-500',
          error
            ? 'border-red-300 text-red-900'
            : 'border-gray-300',
          className
        )}
        {...(invalid ? { 'aria-invalid': 'true' as const } : {})}
      >
        {placeholder && (
          <option value="" disabled>
            {placeholder}
          </option>
        )}
        {options.map((option) => (
          <option
            key={option.value}
            value={option.value}
            disabled={option.disabled}
          >
            {option.label}
          </option>
        ))}
      </select>
    </FormField>
  );
}

// Checkbox component
interface CheckboxProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'type'> {
  name: string;
  label: string;
  description?: string;
}

export function Checkbox({
  name,
  label,
  description,
  className,
  ...props
}: CheckboxProps) {
  const { register } = useFormContext();

  return (
    <div className={clsx('flex items-start', className)}>
      <div className="flex items-center h-5">
        <input
          id={name}
          type="checkbox"
          {...register(name)}
          {...props}
          className="h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
        />
      </div>
      <div className="ml-3">
        <label htmlFor={name} className="text-sm font-medium text-gray-700">
          {label}
        </label>
        {description && (
          <p className="text-sm text-gray-500">{description}</p>
        )}
      </div>
    </div>
  );
}

// Radio group component
interface RadioOption {
  value: string;
  label: string;
  description?: string;
  disabled?: boolean;
}

interface RadioGroupProps {
  name: string;
  label?: string;
  options: RadioOption[];
  className?: string;
}

export function RadioGroup({ name, label, options, className }: RadioGroupProps) {
  const { register, formState: { errors } } = useFormContext();
  const error = errors[name];

  return (
    <div className={className}>
      {label && (
        <label className="block text-sm font-medium text-gray-700 mb-2">
          {label}
        </label>
      )}
      <div className="space-y-2">
        {options.map((option) => (
          <div key={option.value} className="flex items-start">
            <div className="flex items-center h-5">
              <input
                id={`${name}-${option.value}`}
                type="radio"
                value={option.value}
                {...register(name)}
                disabled={option.disabled}
                className="h-4 w-4 border-gray-300 text-indigo-600 focus:ring-indigo-500"
              />
            </div>
            <div className="ml-3">
              <label
                htmlFor={`${name}-${option.value}`}
                className={clsx(
                  'text-sm font-medium',
                  option.disabled ? 'text-gray-400' : 'text-gray-700'
                )}
              >
                {option.label}
              </label>
              {option.description && (
                <p className="text-sm text-gray-500">{option.description}</p>
              )}
            </div>
          </div>
        ))}
      </div>
      {error && (
        <p className="mt-1 text-sm text-red-600">{error.message as string}</p>
      )}
    </div>
  );
}

// Multi-select with checkboxes
interface MultiSelectProps {
  name: string;
  label?: string;
  options: SelectOption[];
  className?: string;
}

export function MultiSelect({ name, label, options, className }: MultiSelectProps) {
  const { register, formState: { errors } } = useFormContext();
  const error = errors[name];

  return (
    <div className={className}>
      {label && (
        <label className="block text-sm font-medium text-gray-700 mb-2">
          {label}
        </label>
      )}
      <div className="space-y-2 max-h-48 overflow-y-auto border border-gray-300 rounded-md p-3">
        {options.map((option) => (
          <div key={option.value} className="flex items-center">
            <input
              id={`${name}-${option.value}`}
              type="checkbox"
              value={option.value}
              {...register(name)}
              disabled={option.disabled}
              className="h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
            />
            <label
              htmlFor={`${name}-${option.value}`}
              className={clsx(
                'ml-2 text-sm',
                option.disabled ? 'text-gray-400' : 'text-gray-700'
              )}
            >
              {option.label}
            </label>
          </div>
        ))}
      </div>
      {error && (
        <p className="mt-1 text-sm text-red-600">{error.message as string}</p>
      )}
    </div>
  );
}

// File input
interface FileInputProps {
  name: string;
  label?: string;
  description?: string;
  accept?: string;
  multiple?: boolean;
  className?: string;
}

export function FileInput({
  name,
  label,
  description,
  accept,
  multiple,
  className,
}: FileInputProps) {
  const { register, formState: { errors }, watch } = useFormContext();
  const error = errors[name];
  const files = watch(name);

  return (
    <FormField name={name} label={label} description={description}>
      <div
        className={clsx(
          'mt-1 flex justify-center px-6 pt-5 pb-6 border-2 border-dashed rounded-md',
          error ? 'border-red-300' : 'border-gray-300',
          className
        )}
      >
        <div className="space-y-1 text-center">
          <svg
            className="mx-auto h-12 w-12 text-gray-400"
            stroke="currentColor"
            fill="none"
            viewBox="0 0 48 48"
          >
            <path
              d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8m-12 4h.02"
              strokeWidth={2}
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          <div className="flex text-sm text-gray-600">
            <label
              htmlFor={name}
              className="relative cursor-pointer rounded-md font-medium text-indigo-600 hover:text-indigo-500 focus-within:outline-none"
            >
              <span>Upload a file</span>
              <input
                id={name}
                type="file"
                {...register(name)}
                accept={accept}
                multiple={multiple}
                className="sr-only"
              />
            </label>
            <p className="pl-1">or drag and drop</p>
          </div>
          <p className="text-xs text-gray-500">
            {accept || 'Any file type'}
          </p>
          {files && files.length > 0 && (
            <p className="text-sm text-green-600">
              {files.length} file(s) selected
            </p>
          )}
        </div>
      </div>
    </FormField>
  );
}

// Submit button
interface SubmitButtonProps {
  children: React.ReactNode;
  isLoading?: boolean;
  loadingText?: string;
  className?: string;
}

export function SubmitButton({
  children,
  isLoading,
  loadingText = 'Submitting...',
  className,
}: SubmitButtonProps) {
  return (
    <button
      type="submit"
      disabled={isLoading}
      className={clsx(
        'inline-flex justify-center items-center px-4 py-2 border border-transparent',
        'text-sm font-medium rounded-md shadow-sm text-white',
        'bg-indigo-600 hover:bg-indigo-700',
        'focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500',
        'disabled:opacity-50 disabled:cursor-not-allowed',
        'transition-colors',
        className
      )}
    >
      {isLoading ? (
        <>
          <svg
            className="animate-spin -ml-1 mr-2 h-4 w-4 text-white"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
            />
          </svg>
          {loadingText}
        </>
      ) : (
        children
      )}
    </button>
  );
}

export default Form;
