/* @vitest-environment jsdom */
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { FormProvider, useForm } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import { Button } from './button';
import { Form, FormInput } from './form';

const schema = z.object({
  name: z.string().min(1, 'Name is required'),
});

type TestFormData = z.infer<typeof schema>;

function TestForm() {
  const form = useForm<TestFormData>({
    resolver: zodResolver(schema),
    defaultValues: {
      name: '',
    },
  });

  return (
    <FormProvider {...form}>
      <Form onSubmit={form.handleSubmit(() => {})}>
        <FormInput<TestFormData> name="name" label="Name" required />
        <Button type="submit">Submit</Button>
      </Form>
    </FormProvider>
  );
}

describe('FormInput accessibility', () => {
  it('links validation errors with aria attributes and alert role', async () => {
    const user = userEvent.setup();
    render(<TestForm />);

    const input = screen.getByRole('textbox', { name: /name/i });
    await user.click(screen.getByRole('button', { name: 'Submit' }));

    const error = await screen.findByRole('alert');
    expect(error.textContent).toContain('Name is required');
    expect(error.getAttribute('id')).toBe('name-error');
    expect(input.getAttribute('aria-invalid')).toBe('true');
    expect(input.getAttribute('aria-describedby')).toBe('name-error');
  });
});
