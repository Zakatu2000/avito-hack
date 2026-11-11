import { type InputHTMLAttributes, type TextareaHTMLAttributes, forwardRef } from 'react'

interface FieldBase {
  label?: string
  hint?: string
  error?: string
}

export interface InputProps extends InputHTMLAttributes<HTMLInputElement>, FieldBase {}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { label, hint, error, className, id, ...rest },
  ref,
) {
  const fieldId = id ?? rest.name
  return (
    <div className={`field ${error ? 'field--error' : ''} ${className ?? ''}`}>
      {label && (
        <label className="field__label" htmlFor={fieldId}>
          {label}
        </label>
      )}
      <input
        ref={ref}
        id={fieldId}
        className="field__control"
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? `${fieldId}-error` : hint ? `${fieldId}-hint` : undefined}
        {...rest}
      />
      {hint && !error && (
        <span className="field__hint" id={`${fieldId}-hint`}>
          {hint}
        </span>
      )}
      {error && (
        <span className="field__error" id={`${fieldId}-error`} role="alert">
          {error}
        </span>
      )}
    </div>
  )
})

export interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement>, FieldBase {}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(function Textarea(
  { label, hint, error, className, id, ...rest },
  ref,
) {
  const fieldId = id ?? rest.name
  return (
    <div className={`field ${error ? 'field--error' : ''} ${className ?? ''}`}>
      {label && (
        <label className="field__label" htmlFor={fieldId}>
          {label}
        </label>
      )}
      <textarea
        ref={ref}
        id={fieldId}
        className="field__control"
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? `${fieldId}-error` : undefined}
        {...rest}
      />
      {hint && !error && (
        <span className="field__hint" id={`${fieldId}-hint`}>
          {hint}
        </span>
      )}
      {error && (
        <span className="field__error" id={`${fieldId}-error`} role="alert">
          {error}
        </span>
      )}
    </div>
  )
})
