export type ConfigSource = 'env' | 'config' | 'yaml' | 'default';

export interface ConfigValue {
  value: string | number | boolean | null | Record<string, unknown>;
  source: ConfigSource;
  redacted: boolean;
}

export interface EffectiveConfigResponse {
  config_root: string;
  config_file: string;
  prompts_dir: string;
  module_yaml: Record<string, string | null>;
  values: Record<string, Record<string, ConfigValue>>;
}
