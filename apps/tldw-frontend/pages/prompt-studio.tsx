import { RouteRedirect } from '@web/components/navigation/RouteRedirect';

export default function PromptStudioRedirectPage() {
  return (
    <RouteRedirect
      to="/prompts?tab=studio"
      title="Prompt Studio has moved"
      description="Prompt Studio is now part of the Prompts page."
    />
  );
}
