import React from "react"
import { Button, Form, Input, InputNumber, Modal, Switch } from "antd"
import { LabelWithHelp } from "@/components/Common/LabelWithHelp"

type DictionaryFormModalProps = {
  title: string
  open: boolean
  onCancel: () => void
  form: any
  onFinish: (values: any) => void
  submitLabel: string
  submitLoading: boolean
  tokenBudgetHelp: string
  includeActiveField?: boolean
}

export const DictionaryFormModal: React.FC<DictionaryFormModalProps> = ({
  title,
  open,
  onCancel,
  form,
  onFinish,
  submitLabel,
  submitLoading,
  tokenBudgetHelp,
  includeActiveField = false
}) => {
  return (
    <Modal title={title} open={open} onCancel={onCancel} footer={null}>
      <Form layout="vertical" form={form} onFinish={onFinish}>
        <Form.Item name="name" label="Name" rules={[{ required: true }]}>
          <Input />
        </Form.Item>
        <Form.Item name="description" label="Description">
          <Input />
        </Form.Item>
        {includeActiveField ? (
          <Form.Item name="is_active" label="Active" valuePropName="checked">
            <Switch checkedChildren="On" unCheckedChildren="Off" />
          </Form.Item>
        ) : null}
        <Form.Item
          name="default_token_budget"
          label={(
            <LabelWithHelp
              label="Default Token Budget"
              help={tokenBudgetHelp}
            />
          )}
          rules={[{ type: "number", min: 1, message: "Must be at least 1 token." }]}
        >
          <InputNumber min={1} style={{ width: "100%" }} placeholder="Optional" />
        </Form.Item>
        <Button type="primary" htmlType="submit" loading={submitLoading} className="w-full">
          {submitLabel}
        </Button>
      </Form>
    </Modal>
  )
}
