'use client';

import * as React from 'react';
import { useFormContext, FieldPath, FieldValues, get } from 'react-hook-form';
import { cn } from '@/lib/utils';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';

// Form context provider
const Form = React.forwardRef<
  HTMLFormElement,
  React.FormHTMLAttributes<HTMLFormElement>
>(({ className, ...props }, ref) => (
  <form ref={ref} className={cn('space-y-4', className)} {...props} />
));
Form.displayName = 'Form';

// Form field wrapper with label and error
interface FormFieldProps<T extends FieldValues> {
  name: FieldPath<T>;
  label: string;
  description?: string;
  required?: boolean;
  children: React.ReactNode;
}

function FormField<T extends FieldValues>({
  name,
  label,
  description,
  required,
  children,
}: FormFieldProps<T>) {
  const { formState: { errors } } = useFormContext<T>();
  const error = get(errors, name);

  return (
    <div className="space-y-2">
      <Label htmlFor={name} className={cn(error && 'text-destructive')}>
        {label}
        {required && <span className="text-destructive ml-1">*</span>}
      </Label>
      {children}
      {description && !error && (
        <p className="text-xs text-muted-foreground">{description}</p>
      )}
      {error && (
        <p className="text-xs text-destructive">{error.message as string}</p>
      )}
    </div>
  );
}

// Pre-built form input with validation
interface FormInputProps<T extends FieldValues> {
  name: FieldPath<T>;
  label: string;
  description?: string;
  required?: boolean;
  type?: string;
  placeholder?: string;
  disabled?: boolean;
  className?: string;
}

function FormInput<T extends FieldValues>({
  name,
  label,
  description,
  required,
  type = 'text',
  placeholder,
  disabled,
  className,
}: FormInputProps<T>) {
  const { register, formState: { errors } } = useFormContext<T>();
  const error = get(errors, name);

  return (
    <FormField<T> name={name} label={label} description={description} required={required}>
      <Input
        id={name}
        type={type}
        placeholder={placeholder}
        disabled={disabled}
        className={cn(error && 'border-destructive', className)}
        {...register(name)}
      />
    </FormField>
  );
}

// Form textarea with validation
interface FormTextareaProps<T extends FieldValues> {
  name: FieldPath<T>;
  label: string;
  description?: string;
  required?: boolean;
  placeholder?: string;
  disabled?: boolean;
  rows?: number;
  className?: string;
}

function FormTextarea<T extends FieldValues>({
  name,
  label,
  description,
  required,
  placeholder,
  disabled,
  rows = 3,
  className,
}: FormTextareaProps<T>) {
  const { register, formState: { errors } } = useFormContext<T>();
  const error = get(errors, name);

  return (
    <FormField<T> name={name} label={label} description={description} required={required}>
      <textarea
        id={name}
        placeholder={placeholder}
        disabled={disabled}
        rows={rows}
        className={cn(
          'flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50',
          error && 'border-destructive',
          className
        )}
        {...register(name)}
      />
    </FormField>
  );
}

// Form select with validation
interface FormSelectProps<T extends FieldValues> {
  name: FieldPath<T>;
  label: string;
  description?: string;
  required?: boolean;
  disabled?: boolean;
  options: { value: string; label: string }[];
  placeholder?: string;
  className?: string;
}

function FormSelect<T extends FieldValues>({
  name,
  label,
  description,
  required,
  disabled,
  options,
  placeholder,
  className,
}: FormSelectProps<T>) {
  const { register, formState: { errors } } = useFormContext<T>();
  const error = get(errors, name);

  return (
    <FormField<T> name={name} label={label} description={description} required={required}>
      <select
        id={name}
        disabled={disabled}
        className={cn(
          'flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50',
          error && 'border-destructive',
          className
        )}
        {...register(name)}
      >
        {placeholder && (
          <option value="">{placeholder}</option>
        )}
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </FormField>
  );
}

// Form checkbox with validation
interface FormCheckboxProps<T extends FieldValues> {
  name: FieldPath<T>;
  label: string;
  description?: string;
  disabled?: boolean;
  className?: string;
}

function FormCheckbox<T extends FieldValues>({
  name,
  label,
  description,
  disabled,
  className,
}: FormCheckboxProps<T>) {
  const { register, formState: { errors } } = useFormContext<T>();
  const error = get(errors, name);

  return (
    <div className="space-y-2">
      <div className="flex items-center space-x-2">
        <input
          type="checkbox"
          id={name}
          disabled={disabled}
          className={cn(
            'h-4 w-4 rounded border border-input text-primary focus:ring-primary',
            error && 'border-destructive',
            className
          )}
          {...register(name)}
        />
        <Label htmlFor={name} className={cn('font-normal', error && 'text-destructive')}>
          {label}
        </Label>
      </div>
      {description && !error && (
        <p className="text-xs text-muted-foreground ml-6">{description}</p>
      )}
      {error && (
        <p className="text-xs text-destructive ml-6">{error.message as string}</p>
      )}
    </div>
  );
}

export { Form, FormField, FormInput, FormTextarea, FormSelect, FormCheckbox };
