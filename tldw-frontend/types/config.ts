export type ConfigSource = 'env' | 'config' | 'yaml' | 'default';

export interface ConfigValue {
  value: unknown;
  source: ConfigSource;
  redacted: boolean;
}

export interface EffectiveConfigResponse {
  config_root: string;
  config_file?: string | null;
  prompts_dir?: string | null;
  module_yaml: Record<string, string | null>;
  values: Record<string, Record<string, ConfigValue>>;
}
