/**
 * useZodForm
 * ==========
 *
 * Lives outside Form.tsx so that module exports only components. React Fast
 * Refresh cannot update a module that mixes component and non-component
 * exports, and react-refresh/only-export-components flags it.
 */

import {
  useForm,
  FieldValues,
  type DefaultValues,
} from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { ZodSchema } from 'zod';

// Hook for creating forms with zod validation
export function useZodForm<T extends FieldValues>(
  schema: ZodSchema<T>,
  defaultValues?: Partial<T>
) {
  return useForm<T>({
    resolver: zodResolver(schema),
    defaultValues: defaultValues as DefaultValues<T> | undefined,
    mode: 'onBlur',
  });
}
