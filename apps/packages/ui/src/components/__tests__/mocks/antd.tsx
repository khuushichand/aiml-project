export const createFormSelectInputNumberAntdMock = () => {
  const FormItem = ({ label, help, children }: any) => (
    <div>
      {label ? <label>{label}</label> : null}
      {children}
      {help ? <div>{help}</div> : null}
    </div>
  )
  const Form = ({ children }: any) => <div>{children}</div>
  Form.Item = FormItem

  const Select = ({ value, options = [], onChange, mode, ...rest }: any) => (
    <select
      data-testid={rest["data-testid"] || "ant-select"}
      multiple={mode === "multiple"}
      value={value ?? (mode === "multiple" ? [] : "")}
      onChange={(event) => {
        if (mode === "multiple") {
          const values = Array.from(event.currentTarget.selectedOptions).map(
            (option) => option.value
          )
          onChange?.(values)
          return
        }
        onChange?.(event.currentTarget.value)
      }}
    >
      {(options || []).map((option: any) => (
        <option key={String(option.value)} value={String(option.value)}>
          {String(option.label)}
        </option>
      ))}
    </select>
  )

  const Input = ({ value, onChange, onBlur, placeholder }: any) => (
    <input
      value={value ?? ""}
      placeholder={placeholder}
      onChange={(event) => onChange?.(event)}
      onBlur={onBlur}
    />
  )
  Input.TextArea = ({ value, onChange, onBlur, placeholder, disabled }: any) => (
    <textarea
      value={value ?? ""}
      placeholder={placeholder}
      disabled={disabled}
      onChange={(event) => onChange?.(event)}
      onBlur={onBlur}
    />
  )

  const InputNumber = ({ value, onChange, onBlur, disabled, ...rest }: any) => (
    <input
      type="number"
      data-testid={rest["data-testid"] || "ant-input-number"}
      value={value ?? ""}
      disabled={disabled}
      onChange={(event) => {
        const raw = event.currentTarget.value
        onChange?.(raw === "" ? null : Number(raw))
      }}
      onBlur={onBlur}
    />
  )

  return { Form, Select, Input, InputNumber }
}
